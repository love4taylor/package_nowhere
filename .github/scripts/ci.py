#!/usr/bin/env python3
"""Validate package versions, collect SDK output and prepare release assets."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil


SDKS = (("24.10.7", "ipk"), ("25.12.5", "apk"))
ARCHES = (
    "aarch64_cortex-a53",
    "aarch64_cortex-a72",
    "aarch64_cortex-a76",
    "aarch64_generic",
    "x86_64",
    "riscv64_riscv64",
)


def matrix():
    return [
        {
            "sdk": sdk,
            "format": package_format,
            "arch": (
                "riscv64_generic"
                if package_format == "apk" and arch == "riscv64_riscv64"
                else arch
            ),
        }
        for sdk, package_format in SDKS
        for arch in ARCHES
    ]


def version():
    recipe = Path("Makefile").read_text()
    values = {}
    for key in ("PKG_VERSION", "PKG_RELEASE"):
        matches = re.findall(rf"^{key}:=(\S+)\s*$", recipe, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one literal {key} in Makefile")
        values[key] = matches[0]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", values["PKG_VERSION"]):
        raise ValueError("PKG_VERSION must use X.Y.Z")
    if not re.fullmatch(r"[1-9][0-9]*", values["PKG_RELEASE"]):
        raise ValueError("PKG_RELEASE must be a positive integer")
    return f'{values["PKG_VERSION"]}-r{values["PKG_RELEASE"]}'


def metadata():
    package_version = version()
    tag = f"v{package_version}"
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        actual = os.environ.get("GITHUB_REF_NAME")
        if actual != tag:
            raise ValueError(f"Tag {actual!r} does not match Makefile: expected {tag}")
    outputs = {"version": package_version, "tag": tag, "matrix": json.dumps({"include": matrix()})}
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        for key, value in outputs.items():
            output.write(f"{key}={value}\n")
    print(f"Validated {tag}; {len(matrix())} SDK builds")


def asset_name(package_version, arch, package_format):
    if package_format == "apk":
        return f"nowhere-{package_version}-{arch}.apk"
    return f"nowhere_{package_version}_{arch}.ipk"


def collect(args):
    # A successful action may have skipped an unsupported package. Require the
    # actual Nowhere output, and collect no dependencies or repository indexes.
    root = Path(args.root) / "bin/packages" / args.arch
    pattern = "nowhere-*.apk" if args.format == "apk" else "nowhere_*.ipk"
    candidates = sorted(root.rglob(pattern))
    if len(candidates) != 1:
        raise ValueError(f"Expected one {pattern} for {args.arch}, found {len(candidates)}")
    source = candidates[0]
    if source.stat().st_size == 0:
        raise ValueError(f"Empty package: {source}")
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / asset_name(version(), args.arch, args.format)
    shutil.copyfile(source, target)
    print(f"Collected {target}")


def release(args):
    package_version = version()
    directory = Path(args.directory)
    expected = {
        asset_name(package_version, item["arch"], item["format"])
        for item in matrix()
    }
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != expected:
        raise ValueError(
            f"Release assets differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    checksums = []
    for name in sorted(expected):
        path = directory / name
        if path.stat().st_size == 0:
            raise ValueError(f"Empty release asset: {name}")
        checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n")
    (directory / "SHA256SUMS").write_text("".join(checksums))
    rows = "\n".join(
        f'| {item["arch"]} | {item["format"].upper()} | OpenWrt {item["sdk"]} SDK |'
        for item in matrix()
    )
    Path(args.notes).write_text(
        f"Nowhere **{package_version}** 的 OpenWrt 软件包。\n\n"
        "根据设备的包管理器和目标架构选择附件；使用 `SHA256SUMS` 校验下载文件。\n\n"
        "| 目标架构 | 格式 | 构建环境 |\n|---|---|---|\n"
        f"{rows}\n\n"
        "APK 使用 `apk` 安装，IPK 使用 `opkg` 安装。文件名中的版本是 Nowhere "
        "软件包版本；安装时仍需匹配目标系统的 ABI 和运行库。\n\n"
        "默认实例未启用，配置方式见仓库 README。\n"
    )
    print(f"Validated {len(expected)} release packages; SHA256SUMS generated")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("metadata")
    collector = commands.add_parser("collect")
    collector.add_argument("--root", required=True)
    collector.add_argument("--arch", required=True)
    collector.add_argument("--format", choices=("apk", "ipk"), required=True)
    collector.add_argument("--destination", required=True)
    publisher = commands.add_parser("release")
    publisher.add_argument("--directory", required=True)
    publisher.add_argument("--notes", required=True)
    args = parser.parse_args()
    if args.command == "metadata":
        metadata()
    elif args.command == "collect":
        collect(args)
    else:
        release(args)


if __name__ == "__main__":
    main()
