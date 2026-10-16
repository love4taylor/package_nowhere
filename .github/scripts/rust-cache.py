#!/usr/bin/env python3
"""Cache Rust distribution installers while retaining the SDK's install rules."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


COMPONENTS = ("rustc-", "cargo-", "rust-std-", "llvm-tools-", "rust-src-")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, sort_keys=True) + "\n")


def configure_action(args):
    action = Path(args.action_directory)
    feed = Path(args.feed_directory)
    control = feed / ".ci"
    control.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, control / "rust-cache.py")
    write_json(control / "context.json", {"sdk": args.sdk, "arch": args.arch})
    entrypoint = action / "entrypoint.sh"
    source = entrypoint.read_text()
    anchor = 'group "make defconfig"\nmake defconfig\nendgroup\n'
    if source.count(anchor) != 1:
        raise ValueError("Official SDK entrypoint changed: cannot place Rust cache hook")
    action_file = action / "action.yml"
    action_source = action_file.read_text()
    cache_lines = (
        "        cache-to: type=gha,mode=max,scope=${{ env.CONTAINER }}-${{ env.ARCH }}\n",
        "        cache-from: type=gha,scope=${{ env.CONTAINER }}-${{ env.ARCH }}\n",
    )
    if any(action_source.count(line) != 1 for line in cache_lines):
        raise ValueError("Official SDK action cache settings changed")
    hook = (
        '\ngroup "prepare Rust toolchain cache"\n'
        'python3 /feed/.ci/rust-cache.py prepare --sdk-root "$PWD"\n'
        'endgroup\n'
    )
    entrypoint.write_text(source.replace(anchor, anchor + hook))
    for line in cache_lines:
        action_source = action_source.replace(line, "")
    action_file.write_text(action_source)
    print("Added Rust cache hook and disabled SDK Docker layer cache")


def prepare(args, control):
    sdk = Path(args.sdk_root).resolve()
    rust = sdk / "feeds/packages/lang/rust"
    recipe = rust / "Makefile"
    source = recipe.read_text()
    pattern = r"^define Host/Compile\n(.*?)^endef$"
    matches = list(re.finditer(pattern, source, re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        raise ValueError("Expected one Host/Compile in the SDK Rust recipe")
    body = matches[0].group(1).rstrip("\n")
    lines = body.splitlines()
    if not lines or any(not line.rstrip().endswith("\\") for line in lines[:-1]):
        raise ValueError("SDK Rust compilation is no longer a single continued command")
    inputs = {"namespace": json.loads((control / "context.json").read_text())}
    inputs["rust"] = {
        str(path.relative_to(rust)): digest(path)
        for path in sorted(rust.rglob("*")) if path.is_file()
    }
    sdk_files = [sdk / name for name in (
        ".config", "rules.mk", "include/host-build.mk", "include/package.mk",
    )]
    sdk_files += sorted((sdk / "staging_dir").glob("toolchain-*/info.mk"))
    sdk_files += sorted((sdk / "staging_dir").glob("toolchain-*/bin/*-gcc*"))
    inputs["sdk"] = {
        str(path.relative_to(sdk)): digest(path)
        for path in sdk_files if path.is_file()
    }
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    write_json(control / "active.json", {"fingerprint": fingerprint})
    write_json(control / "result.json", {"save": False})
    # Only the compile command is wrapped. Preparation, configure, stamps and
    # Host/Install remain the upstream SDK rules, including on a cache hit.
    command = f'$(PYTHON) "{control / "rust-cache.py"}"'
    build = '--build-directory "$(HOST_BUILD_DIR)"'
    replacement = (
        "define Host/Compile\n"
        f"\t@if {command} restore {build}; then \\\n"
        "\t\t:; \\\n"
        "\telse \\\n"
        f"{body} && \\\n"
        f"\t\t{command} store {build}; \\\n"
        "\tfi\nendef"
    )
    recipe.write_text(source[:matches[0].start()] + replacement + source[matches[0].end():])
    print(f"Rust toolchain fingerprint: {fingerprint}")


def check_components(names):
    if any(not any(name.startswith(prefix) for name in names) for prefix in COMPONENTS):
        raise ValueError("Rust distribution installers are incomplete")


def restore(args, control):
    cache = control.parent / ".rust-cache"
    expected = json.loads((control / "active.json").read_text())["fingerprint"]
    try:
        manifest = json.loads((cache / "manifest.json").read_text())
        if not isinstance(manifest, dict):
            raise ValueError("Invalid cache manifest")
        if manifest["fingerprint"] != expected:
            raise ValueError("SDK configuration or Rust build rules changed")
        archives = manifest["archives"]
        if not isinstance(archives, dict):
            raise ValueError("Invalid installer manifest")
        check_components(archives)
        if set(path.name for path in cache.iterdir()) != set(archives) | {"manifest.json"}:
            raise ValueError("Unexpected or missing cache files")
        for name, checksum in archives.items():
            if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.tar\.gz", name):
                raise ValueError("Invalid installer filename")
            path = cache / name
            if path.is_symlink() or path.stat().st_size == 0 or digest(path) != checksum:
                raise ValueError(f"Invalid installer: {name}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Rust toolchain cache miss: {error}")
        return 1
    destination = Path(args.build_directory) / "build/dist"
    destination.mkdir(parents=True, exist_ok=True)
    for name in archives:
        shutil.copyfile(cache / name, destination / name)
    print(f"Rust toolchain cache hit: restored {len(archives)} installers")
    return 0


def store(args, control):
    source = Path(args.build_directory) / "build/dist"
    archives = sorted(source.glob("*.tar.gz"))
    check_components([path.name for path in archives])
    cache = control.parent / ".rust-cache"
    active = json.loads((control / "active.json").read_text())
    with tempfile.TemporaryDirectory(prefix=".rust-cache-", dir=control.parent) as temporary:
        staged = Path(temporary)
        checksums = {}
        for path in archives:
            if path.is_symlink() or path.stat().st_size == 0:
                raise ValueError(f"Empty or invalid Rust installer: {path}")
            target = staged / path.name
            shutil.copyfile(path, target)
            checksums[path.name] = digest(target)
        write_json(staged / "manifest.json", {**active, "archives": checksums})
        if cache.exists():
            shutil.rmtree(cache)
        staged.rename(cache)
    write_json(control / "result.json", {"save": True})
    print(f"Cached {len(archives)} Rust distribution installers")


def result(args):
    state = Path(args.feed_directory) / ".ci/result.json"
    save = state.is_file() and json.loads(state.read_text()).get("save") is True
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"save={str(save).lower()}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    action = commands.add_parser("action")
    action.add_argument("--action-directory", required=True)
    action.add_argument("--feed-directory", required=True)
    action.add_argument("--sdk", required=True)
    action.add_argument("--arch", required=True)
    initializer = commands.add_parser("prepare")
    initializer.add_argument("--sdk-root", required=True)
    for name in ("restore", "store"):
        command = commands.add_parser(name)
        command.add_argument("--build-directory", required=True)
    status = commands.add_parser("result")
    status.add_argument("--feed-directory", required=True)
    args = parser.parse_args()
    control = Path(__file__).resolve().parent
    if args.command == "action":
        configure_action(args)
    elif args.command == "prepare":
        prepare(args, control)
    elif args.command == "restore":
        raise SystemExit(restore(args, control))
    elif args.command == "store":
        store(args, control)
    else:
        result(args)


if __name__ == "__main__":
    main()
