<p align="center">
  <img src="https://raw.githubusercontent.com/NodePassProject/Nowhere/v3.0.1/assets/nowhere.png" width="420" alt="Nowhere Logo">
</p>

# Nowhere for OpenWrt

为 OpenWrt 提供 [Nowhere](https://github.com/NodePassProject/Nowhere) 软件包构建定义，支持 UCI 配置与 procd 多实例管理。一个 Rust 程序提供 SOCKS5 入口、TLS/QUIC 中继和远程出口。

[下载](#下载) · [安装](#安装) · [配置服务](#配置服务) · [多个实例](#多个实例) · [升级](#升级) · [排错](#排错) · [自行编译](#自行编译)

| 项目 | 说明 |
|---|---|
| 上游版本 | [v3.0.1](https://github.com/NodePassProject/Nowhere/releases/tag/v3.0.1) |
| 软件包版本 | `3.0.1`，发布修订 `1` |
| 适用系统 | OpenWrt 及满足相同包格式、目标 ABI 和运行库要求的兼容系统 |
| 包格式 | 由目标 SDK 决定：APK（`apk`）或 IPK（`opkg`） |
| 仓库协议 | [GPL-3.0-only](LICENSE)，与[上游声明](https://github.com/NodePassProject/Nowhere/blob/v3.0.1/Cargo.toml)一致 |

安装时需匹配目标架构和运行库 ABI，不能仅凭 APK、IPK 扩展名判断兼容性。

## 功能

| 角色 | 用途 |
|---|---|
| **Vector** | 提供本地 SOCKS5 入口，通过 TLS 或 QUIC 连接 Portal |
| **Portal** | 接收连接，使用直接出口、SOCKS5 上游或远程 Egress 转发 |
| **Egress** | 主动通过 QUIC 向 Portal 注册，在出口主机上解析域名和连接目标 |

软件包包含 `/usr/bin/nowhere`、`/etc/config/nowhere` 和 `/etc/init.d/nowhere`。服务支持多个独立实例、异常退出后重启、标准输出日志及 UCI 重载；WAN 接口事件会触发服务重启。

## 下载

在仓库的 Releases 页面选择设备对应的架构和包格式：

| APK 架构 | IPK 架构 |
|---|---|
| `aarch64_cortex-a53` | `aarch64_cortex-a53` |
| `aarch64_cortex-a72` | `aarch64_cortex-a72` |
| `aarch64_cortex-a76` | `aarch64_cortex-a76` |
| `aarch64_generic` | `aarch64_generic` |
| `x86_64` | `x86_64` |
| `riscv64_generic` | `riscv64_riscv64` |

APK 使用 OpenWrt 25.12.5 SDK 构建，IPK 使用 OpenWrt 24.10.7 SDK 构建；RISC-V 架构名称采用各 SDK 的命名。其他系统需确认 ABI 和运行库兼容，或[自行编译](#自行编译)。

附件名包含 Nowhere 版本、软件包修订和目标架构，例如：

```text
nowhere-3.0.1-r1-aarch64_cortex-a53.apk
nowhere_3.0.1-r1_aarch64_cortex-a53.ipk
```

下载所需软件包和 `SHA256SUMS` 后，可在下载目录校验：

```sh
sha256sum --ignore-missing -c SHA256SUMS
```

## 安装

将下载或自行编译的软件包上传到路由器，按设备实际使用的包管理器选择一种安装方式：

以下统一使用文件名匹配模式，要求 `/tmp/` 中对应格式的待安装 Nowhere 包仅有一个。

**APK / apk：**

```sh
apk add --allow-untrusted /tmp/nowhere-*.apk
```

**IPK / opkg：**

```sh
opkg install /tmp/nowhere_*.ipk
```

安装后检查版本：

```sh
nowhere --version
```

版本输出应包含 `nowhere-v3.0.1`，架构信息随目标平台变化。已有软件包会升级，`/etc/config/nowhere` 被登记为保留配置文件。

> [!NOTE]
> 默认 Portal、Vector 和 Egress 实例均未启用。配置中的 `REPLACE_WITH_GENERATED_KEY` 是占位符，启用前需要替换。

## 配置服务

### 1. 准备密钥与证书信任

在任一节点生成共享密钥，并在参与连接的节点使用相同值：

```sh
nowhere generate-key
```

密钥必须恰好包含 **32 个小写十六进制字符**。

Vector 和 Egress 默认验证系统 CA 与主机名。如果 Portal 使用默认生成的证书，可读取其 SHA-256 指纹：

```sh
nowhere fingerprint 'nowhere://KEY@relay.example:2000?morph=1'
```

将结果与可信渠道取得的 Portal 启动日志核对，再填入客户端的 `pin=` 参数。该命令通过 TCP/TLS 获取证书，因此 Portal 在此端口需要提供 TLS 监听。

### 2. 启用所需角色

以下示例中的 `KEY`、`PIN`、`relay.example` 分别替换为实际密钥、核对过的 64 位小写十六进制证书指纹和 Portal 地址。

**Vector：本地 SOCKS5 入口**

在路由器上执行：

```sh
uci set nowhere.vector.url='vector://KEY@relay.example/udp:2000?in=127.0.0.1:1080&pin=PIN'
uci set nowhere.vector.enabled='1'
uci commit nowhere
/etc/init.d/nowhere enable
/etc/init.d/nowhere restart
```

该实例使用 QUIC 连接 Portal。应用程序的 SOCKS5 代理地址设为 `127.0.0.1:1080`；此地址仅供路由器本机访问。

**Portal：直接出口**

在作为中继的设备上执行：

```sh
uci set nowhere.portal.url='portal://KEY@*:2000'
uci set nowhere.portal.enabled='1'
uci commit nowhere
/etc/init.d/nowhere enable
/etc/init.d/nowhere restart
```

默认同时监听 TCP/TLS 和 UDP/QUIC 的 2000 端口，出口为 `out=direct`。根据连接来源配置防火墙放行规则；本包不会自动修改防火墙。

**Egress：远程出口**

在 Portal 上将 URL 改为：

```text
portal://KEY@*:2000?out=egress
```

在远程出口设备上启用 Egress：

```sh
uci set nowhere.egress.url='egress://KEY@relay.example/udp:2000?pin=PIN'
uci set nowhere.egress.enabled='1'
uci commit nowhere
/etc/init.d/nowhere enable
/etc/init.d/nowhere restart
```

Egress 主动连接 Portal，无需在出口主机开放入站中继端口。每个 Portal 接受一个注册的 Egress；Egress 断开时会自动重连，Portal 不会回退到直接出口。

### 3. 查看运行状态

```sh
nowhere status
logread -e nowhere
```

`nowhere status` 显示本机实例、监听端点、TCP/UDP 流量及活动 Flow 数。没有运行中的实例时显示 `IDLE`。

### UCI 参数

每个实例使用一个 `config instance '名称'` 段落：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `option enabled` | `0` | `1` 启用，`0` 禁用 |
| `option url` | 各角色的占位 URL | 完整的 `portal://`、`vector://` 或 `egress://` URL |
| `option user` | 空 | 留空使用服务默认账户；也可指定现有用户 |
| `option group` | 空 | 留空使用服务默认组；也可指定现有组 |
| `list env` | 示例为 `NOW_TRANSPORT_MEMORY_PROFILE=throughput` | 可重复添加 `NAME=VALUE` 环境变量 |

修改后执行 `uci commit nowhere` 和 `/etc/init.d/nowhere restart`。URL、密钥及环境变量的完整约束见 [上游配置参考](https://github.com/NodePassProject/Nowhere/blob/v3.0.1/docs/configuration.md)。

## 多个实例

可运行多个 Vector，也可以混合运行三种角色。为每个实例设置不同的名称，并避免本地监听地址和端口冲突。例如在 `/etc/config/nowhere` 中添加：

```uci
config instance 'vector_a'
	option enabled '1'
	option url 'vector://KEY_A@relay-a.example/udp:2000?in=127.0.0.1:1080&pin=PIN_A'
	list env 'NOW_TRANSPORT_MEMORY_PROFILE=balanced'

config instance 'vector_b'
	option enabled '1'
	option url 'vector://KEY_B@relay-b.example/tcp:2000?in=127.0.0.1:1081&pin=PIN_B'
	list env 'NOW_TRANSPORT_MEMORY_PROFILE=balanced'
```

替换密钥、指纹和地址后重启服务。procd 会分别管理两个进程，应用程序可选择 1080 或 1081 端口作为 SOCKS5 入口。

`NOW_TRANSPORT_MEMORY_PROFILE` 支持 `memory`、`balanced`、`throughput`，用于选择 QUIC 窗口大小；这些窗口设置并非进程内存总上限。

## 升级

升级前备份配置：

```sh
cp -p /etc/config/nowhere /root/nowhere.config.bak
```

按[安装](#安装)中的对应包管理器命令安装新版本，然后重启服务并检查状态：

```sh
/etc/init.d/nowhere restart
nowhere --version
nowhere status
```

| 起始版本 | 迁移说明 |
|---|---|
| v3.0.0 | URL、共享密钥和 telemetry 格式保持兼容。TCP Morph Prelude 默认从 `full8` 改为 `fade`；已有 `full8`、`low7` 设置仍有效 |
| v2.x | NW2 与 NW3 不兼容，同一路径上的节点必须同步升级。将 Vector 的 `socks=` 改为 `in=`，重新核对密钥、传输路径及 Portal `out=` 设置 |

> [!IMPORTANT]
> 保留旧 UCI 配置不会自动迁移 v2 URL。v3 已移除 TLS Mux、`up`/`down` 分流、会话配对、`next` 链式转发和 TUI；请按上游配置参考重新配置。

如需保留 v3.0.0 的 TCP Morph 默认行为，在相应实例中添加：

```uci
list env 'NOW_MORPH_TCP_PRELUDE=full8'
```

Morph 默认启用，连接双方需保持一致。显式关闭时在双方 URL 中设置 `morph=0`。

## 排错

| 现象 | 检查方式 |
|---|---|
| 安装失败或程序无法执行 | 核对发行版、固件版本、目标架构及包格式是否一致 |
| 状态显示 `IDLE` | 检查实例的 `enabled`、URL 占位符是否替换，以及服务是否启动 |
| 配置错误或反复重启 | 查看 `logread -e nowhere`，检查密钥格式、Vector `in=` 和本地端口冲突 |
| TLS 验证失败 | 核对主机名、系统时间、CA 或 `pin=`；通过可信渠道重新确认指纹 |
| QUIC 无法连接 | 检查 `/udp:端口`、Portal UDP 监听及防火墙放行规则 |
| Egress 模式无法转发 | 确认 Portal 使用 `out=egress`、具有 QUIC 监听，且 Egress 已连接 |

可在 Vector 所在设备上验证一次真实 TCP Flow 的建立：

```sh
nowhere probe 'vector://KEY@relay.example/udp:2000?pin=PIN' 'example.com:443'
```

`probe` 无需 `in=`，只验证连接建立，不发送目标应用数据。更多说明见 [运维指南](https://github.com/NodePassProject/Nowhere/blob/v3.0.1/docs/operations.md) 和 [协议文档](https://github.com/NodePassProject/Nowhere/blob/v3.0.1/docs/protocol.md)。

## 自行编译

### 准备 SDK

使用 x86_64 Linux 构建机，从 [OpenWrt 下载站](https://downloads.openwrt.org/releases/) 选择目标设备对应的 SDK，并安装该 SDK 要求的主机依赖。目标架构、运行库 ABI 和打包机制需要与固件匹配。

将本仓库放在 SDK 之外，在 SDK 根目录中执行。示例中的 `/path/to/` 均需替换为实际路径：

```sh
cd /path/to/sdk
./scripts/feeds update -a
./scripts/feeds install rust
ln -s /path/to/nowhere package/nowhere
make menuconfig
```

在 `Network → Web Servers/Proxies → nowhere` 中选择 `<M>`，保存配置。
SDK 的 Rust feed 提供编译规则，构建时需要对应的 Rust 主机工具链及目标标准库；使用外部预编译工具链时，应与 SDK feed 的版本和目标保持一致。

### 构建软件包

在 SDK 根目录执行：

```sh
umask 022
make defconfig
make package/nowhere/compile -j8 V=s
```

产物通常位于 `bin/packages/<目标架构>/base/`，格式及文件名由目标 SDK 决定：

| SDK 打包机制 | 文件名匹配模式 | 安装工具 |
|---|---|---|
| APK | `nowhere-*.apk` | `apk` |
| IPK | `nowhere_*.ipk` | `opkg` |

两种格式来自各自 SDK 的打包流程，不能通过改扩展名互换。编译失败时可使用 `-j1 V=s` 重试，查看首个错误。
