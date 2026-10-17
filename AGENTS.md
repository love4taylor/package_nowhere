# 仓库工作指南

## 项目范围

本仓库为上游 [NodePassProject/Nowhere](https://github.com/NodePassProject/Nowhere) 提供 OpenWrt 软件包定义，使用 SDK 的 Rust feed、UCI 和 procd。这里维护打包与服务管理，不维护上游 Rust 源码。

| 文件 | 职责 |
|---|---|
| `Makefile` | 上游版本、源码 SHA-256、依赖、编译与安装规则 |
| `files/nowhere.config` | 默认关闭的 Portal、Vector、Egress 示例 |
| `files/nowhere.init` | procd 多实例、环境变量、重启和重载逻辑 |
| `.github/workflows/build.yml` | 编译测试、产物上传和 tag 发布 |
| `.github/scripts/ci.py` | 构建矩阵、版本校验、产物命名和 Release 完整性检查 |
| `.github/scripts/rust-cache.py` | 官方 SDK Action 的缓存接入、Rust 分发包恢复和校验 |
| `.gitignore` | SDK、源码下载、编译产物、缓存和本地配置的忽略规则 |
| `LICENSE` | GNU GPLv3 许可证全文；本仓库采用 `GPL-3.0-only` |
| `README.md` | 面向使用者的下载、安装、配置、升级、排错与自行编译说明 |

上游源码由 SDK 下载并展开到构建目录；分析源码时使用临时目录或远程文件，不把上游仓库或源码副本放进本仓库。不要提交 SDK、APK、IPK 或生成的索引。

## 许可证维护

本仓库的打包代码、服务脚本、CI 辅助代码和文档采用 `GPL-3.0-only`，根目录 `LICENSE` 使用 GNU 官方 GPLv3 全文。保留上游及第三方的版权和许可声明，不把上游的作者署名当成本仓库打包代码的作者署名。

Makefile 的 `PKG_LICENSE` 描述上游软件的许可证，当前同为 `GPL-3.0-only`。`PKG_LICENSE_FILES:=LICENSE` 指向 SDK 展开的上游源码中的许可证文件，与本仓库根目录的 `LICENSE` 分别维护。更新上游版本时核对许可证声明是否变化。

## 文档边界

README 保留使用者需要的信息，包括软件包架构、格式和 ABI 兼容要求。版本维护、tag、CI 内部实现与检查步骤放在本文件。

公开仓库只描述通用的软件包流程。个人路径、设备地址、认证信息、特定固件项目的构建脚本及私人设备的集成部署流程不得写入仓库文件。示例使用 `/path/to/`、`relay.example` 和密钥占位符。

## 开发环境与编译

本地语法和元数据检查需要 POSIX shell、Python 3；CI 辅助脚本只依赖 Python 标准库。工作流检查使用 `actionlint`。完整编译需要 x86_64 Linux、匹配目标的 OpenWrt SDK、SDK 主机依赖及 `packages` feed 的 Rust 构建规则。

SDK 初始化和包链接步骤见 README 的“自行编译”。从 SDK 根目录运行：

```sh
umask 022
make defconfig
make package/nowhere/compile -j8 V=s
```

失败时用 `make package/nowhere/compile -j1 V=s` 定位首个错误。产物通常位于 `bin/packages/<架构>/<feed>/`。本地以链接方式引入时通常为 `base`，CI 的 feed 名为 `nowhere_ci`。

`Makefile` 使用 `RustBinPackage` 和 `BuildPackage`，包格式由 SDK 决定。保留 `rust/host` 构建依赖、`RUST_ARCH_DEPENDS` 和 `ca-bundle`；SDK 还会自动补入运行库依赖。APK、IPK 不可通过修改扩展名互换。

## 版本与源码更新

| 变更 | 处理方式 |
|---|---|
| 跟进上游版本 | 更新 `PKG_VERSION`、`PKG_HASH`，将 `PKG_RELEASE` 重置为 `1` |
| 修改打包规则、默认配置或服务行为 | 保留上游版本，递增 `PKG_RELEASE` |
| 仅修改文档或 CI | 无需单独递增软件包修订，除非改变生成的软件包 |

核对上游 release 和配置兼容性，用 `PKG_SOURCE_URL` 对应的源码压缩包计算 SHA-256。不要用 Git commit 的哈希代替压缩包校验值，也不要跳过哈希校验。Cargo 使用上游锁定的依赖。

`ci.py` 要求 Makefile 中 `PKG_VERSION:=X.Y.Z` 和 `PKG_RELEASE:=N` 各出现一次，版本为三段数字，修订为正整数；保持这两个字段为直接赋值。

### Tag 约定

发布 tag 为 `v${PKG_VERSION}-r${PKG_RELEASE}`，例如 `v3.0.1-r1`。CI 会在编译前校验 tag 与其对应提交中的 Makefile 一致。

用户要求发布时，在对应变更提交并推送后执行以下命令；示例版本需按实际值替换：

```sh
git tag v3.0.1-r1
git push origin v3.0.1-r1
```

未获得用户发布指令时，不自行推送 tag 或发布 Release。

## CI 与产物约定

使用官方 [openwrt/gh-action-sdk](https://github.com/openwrt/gh-action-sdk) 和 `ghcr.io/openwrt/sdk`，Action 按固定 commit 检出到临时 `.ci/sdk-action/`，接入 Rust 缓存后以本地 Action 执行。SDK 版本与矩阵以 `.github/scripts/ci.py` 为准，当前为 OpenWrt 24.10.7 / IPK 和 25.12.5 / APK，共 12 组。

前五组架构在两种格式下相同：`aarch64_cortex-a53`、`aarch64_cortex-a72`、`aarch64_cortex-a76`、`aarch64_generic`、`x86_64`。RISC-V 在 IPK SDK 中为 `riscv64_riscv64`，在 APK SDK 中为 `riscv64_generic`。调整 SDK 时重新核对官方架构和容器标签，并同步 README 的兼容信息。

| 触发方式 | 行为 |
|---|---|
| 分支 push 或 PR 修改 `Makefile`、`files/**`、`patches/**`、`src/**`、工作流或 CI 脚本 | 编译测试并上传 artifacts，不发布 Release |
| 仅修改 README、AGENTS.md 或 `.gitignore` | 不自动构建 |
| `workflow_dispatch` | 编译测试，不发布 Release，包括手动选择 tag 的情况 |
| push 匹配 `v*-r*` 的 tag | 严格校验版本，全部矩阵成功后发布 Release |

工作流将包文件复制到临时 `feed/nowhere/`，因为官方 Action 需要一个包含子包的 feed。临时 feed 的 Git index 用于补丁刷新检查；init 脚本单独做语法检查，禁用 Action 的自动 shfmt 检查。

`INDEX` 保持为 `0`。只发布 Nowhere 包及 `SHA256SUMS`，不生成软件源索引。任务与附件名称按架构和包格式区分，不加入 OpenWrt 版本。附件示例：

```text
nowhere-3.0.1-r1-aarch64_cortex-a53.apk
nowhere_3.0.1-r1_aarch64_cortex-a53.ipk
```

`collect` 要求每个矩阵恰好生成一个非空 Nowhere 包，防止 Action 跳过不支持的架构却返回成功。`release` 要求全部 12 个预期包齐全且没有额外文件，然后生成校验和与发布说明。保留这些检查和 Release 对整个 build job 的依赖。

### Rust 工具链缓存

使用 GitHub 官方 `actions/cache/restore` 与 `actions/cache/save`，仅缓存 Rust 构建产生的分发安装包，包括 rustc、Cargo、目标标准库、LLVM tools 和 Rust 源码组件。不要缓存整个 SDK 或庞大的 Rust/LLVM 中间构建目录。

关闭 `docker/setup-qemu-action` 的 `cache-image`，保留 QEMU 安装但不缓存 `tonistiigi/binfmt` 镜像。GitHub 默认会清理连续 7 天未被访问的缓存，计时依据为缓存访问时间；提交代码本身不会续期。

缓存按运行平台、SDK、架构和缓存脚本版本隔离。恢复后再次比较 SDK 配置、工具链信息、GCC 文件与 Rust feed 规则的指纹，并逐个校验安装包 SHA-256；不匹配或损坏时重新编译。Nowhere 自身版本和打包文件不直接参与缓存键。将 Rust feed 的 `--dist-compression-formats=gz` 改为 `xz`，追加 `--set=dist.compression-profile=best`（xz level 9），并将安装循环改为解包 `.tar.xz`。缓存原样保存和恢复这些 xz 分发包，不再转换格式。官方 `actions/cache` 不提供关闭压缩的参数；保存步骤使用 `ZSTD_CLEVEL=1`，降低已压缩 xz 文件的外层 zstd 压缩开销。

接入代码包装 Rust 的 `Host/Compile`，并调整分发格式和对应的安装解包命令；保留 SDK 原有的准备、配置及 stamp 规则，安装仍由上游安装脚本完成。上游规则结构变化时应重新核对。缓存命中时复制分发包后继续安装，未命中时在源码编译成功后导出。Rust 编译完成后，即使后续 Nowhere 编译失败，也可保存工具链缓存；命中时不重复上传。每个 SDK/架构组合使用稳定的单一缓存键，不把运行编号加入键，避免每次运行复制一份工具链。官方 Action 的 Docker/BuildKit 层缓存已关闭，避免无关镜像层占用仓库缓存配额。缓存是加速手段，其保留时间受 GitHub 缓存容量和清理策略约束。

确认未命中或校验失败后，先通过 GitHub REST API 删除同一运行平台、SDK 和架构前缀下的全部旧缓存（含不同 ref 和脚本版本），再清理本地旧副本并开始编译。命中时不删除；其他 SDK/架构不受影响。缓存清理失败则停止本次编译，避免在旧缓存仍占用空间时继续生成新副本。对应 build job 需要 `actions: write`，同一 SDK/架构通过 job concurrency 串行执行，避免不同分支或 tag 相互清理正在生成的缓存。PR 只恢复缓存和验证编译，不传清理令牌、不删除或保存远端缓存。本地运行只清理本地副本。删除后若编译失败，旧缓存不会恢复。

## 检查与验证

从仓库根目录执行基础检查：

```sh
sh -n files/nowhere.init
python3 .github/scripts/ci.py --help
ci_output="$(mktemp)"
GITHUB_OUTPUT="$ci_output" GITHUB_REF_TYPE=branch GITHUB_REF_NAME=local \
  python3 .github/scripts/ci.py metadata
cat "$ci_output"
rm -f "$ci_output"
```

安装 `actionlint` 后，修改工作流时运行：

```sh
actionlint .github/workflows/build.yml
```

本仓库没有独立的单元测试套件。按改动验证实际行为：修改 `ci.py` 时检查正确与错误 tag、12 组矩阵、缺失/空/重复产物，以及 Release 完整性与 SHA-256；临时测试数据放在仓库外。

修改 `rust-cache.py` 时，通过 GNU make 实际执行包装后的 `Host/Compile`，验证首次编译保存、命中跳过编译和清理、指纹变化和损坏回退，以及先清理后编译的顺序。验证分页删除范围、API 失败阻止编译、PR 不写远端缓存，以及编译失败的退出状态。核对官方 Action 接入位置及 Rust 安装规则保持完整。

修改 Makefile 或运行文件后，使用相应 SDK 编译并检查包内的 `/usr/bin/nowhere`、`/etc/config/nowhere`、`/etc/init.d/nowhere` 与依赖元数据。没有运行完整矩阵时，明确报告已验证范围，不把静态检查视为跨架构编译成功。

## 代码与服务约定

Makefile 命令和服务脚本沿用 Tab 缩进，Python 使用四空格。`ci.py` 保持标准库实现；维护矩阵和附件命名时同步收集、发布校验和文档。

服务脚本保持 OpenWrt `/etc/rc.common` 与 procd 用法，使用 UCI 辅助函数读取配置，避免 Bash 专用语法、`eval` 或拼接 shell 命令。保留多实例、每实例环境变量、用户/组、日志、重启与重载支持。

默认实例保持关闭，密钥使用占位符，`/etc/config/nowhere` 保持登记为配置文件。不要把真实密钥、证书私钥或设备配置作为示例提交；保留证书验证和可信指纹核对说明。
