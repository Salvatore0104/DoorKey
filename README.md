# 海尔 HR-6107 门禁系统 — 软件终端与 HA 集成

将损坏的海尔 HR-6107 室内终端替换为运行在 PC / 嵌入式设备上的软件终端，复现来电监听、视频、对讲、开门等核心功能，并接入 Home Assistant。

> **项目背景**：住宅使用的海尔 HR-6107 可视对讲门禁终端，5楼设备主板损坏导致以太网物理链路无法建立。本方案用一台运行 Python 服务的设备替换该终端，使用原固定 IP `172.30.2.47`（房号 501）冒充终端身份，监听门口机 `172.30.2.36` 的呼叫和音视频流。

---

## 目录

- [系统架构](#系统架构)
- [协议分析](#协议分析)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [安全门控](#安全门控)
- [Home Assistant 集成](#home-assistant-集成)
- [抓包与协议分析工具](#抓包与协议分析工具)
- [已知问题与限制](#已知问题与限制)
- [网络隔离要求](#网络隔离要求)
- [后续计划](#后续计划)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    门禁专网 172.30.2.0/24                     │
│                                                              │
│   ┌──────────────┐    TCP 46752 (控制)     ┌──────────────┐ │
│   │  门口机       │ ──────────────────────▶ │  软件终端     │ │
│   │ 172.30.2.36  │    UDP 46754 (视频H.264) │ 172.30.2.47  │ │
│   │              │ ◀────────────────────── │  (501房号)   │ │
│   │              │    UDP 46753 (音频G.711) │              │ │
│   └──────────────┘                         └──────┬───────┘ │
└─────────────────────────────────────────────────────────────┘
                                                    │
                                          HTTP/WebSocket/WebRTC
                                                    │
                                    ┌───────────────┴───────────────┐
                                    │                               │
                              ┌─────▼─────┐                  ┌──────▼──────┐
                              │  浏览器    │                  │ Home Assistant│
                              │ 可视对讲页 │                  │  自定义组件  │
                              └───────────┘                  └─────────────┘
```

### 组件说明

| 组件 | 作用 |
|------|------|
| `hr6107/` | Python 异步软件终端，监听 TCP/UDP、管理状态机、提供 HTTP API |
| `haier_dashboard_v2.html` | WebRTC 可视对讲网页，支持视频、双向音频、来电通知 |
| `custom_components/haier_hr6107/` | Home Assistant 自定义集成 |
| `tools/` | 901 双向协议抓包与分析工具 |
| `protocol_profile.json` | 协议安全门控，控制命令是否启用 |

---

## 协议分析

海尔 HR-6107 使用**私有协议**，不是标准 SIP/RTSP/ONVIF。通过多轮抓包逆向得到以下结论：

### 网络端口

| 端口 | 协议 | 用途 |
|------|------|------|
| TCP 46752 | 海尔私有控制 | 呼叫开始/结束、接听、挂断、开门 |
| UDP 46753 | 海尔私有音频 | G.711 μ-law, 8kHz, 单声道, 每包20字节私有头 |
| UDP 46754 | 海尔私有视频 | H.264 Baseline, 352×240, 25fps, 每包25字节私有头 |
| UDP 7083 | 海尔设备发现 | `UDISCOVERY_PAD` 私有发现协议 |

### 控制帧格式

```
FFFF + 大端长度(2B) + 全零保留区 + 终端房号 + 终端IP + 命令码 + FE
```

已验证的控制命令（见 `protocol_profile.json`）：

| 命令 | 十六进制尾码 | 说明 |
|------|-------------|------|
| call_ack | `000f0101` | 来电确认（终端→门口机） |
| answer | `0005` | 接听 |
| hangup | `0006` | 挂断 |
| unlock | `0003` | 开门（通话中有效） |
| reject_or_cancel | `0008` | 拒接/取消 |

### 通话状态机

```
IDLE → RINGING → CONNECTING → ACTIVE → ENDING → IDLE
                                                    ↑
                                          ERROR ────┘
```

### 音视频编码

- **视频**：H.264 Baseline，352×240，25fps，UDP 分片传输，每包前 25 字节私有头
- **音频**：G.711 μ-law（PCMU），8kHz 单声道，每包 512 字节 PCM + 20 字节私有头
- **封装**：非标准 RTP，海尔私有分片协议

> 详细抓包分析记录见 [`HR-6107_抓包分析与HA接入记录.md`](HR-6107_抓包分析与HA接入记录.md)

---

## 项目结构

```
绿城海尔门禁系统/
├── hr6107/                          # Python 软件终端核心
│   ├── app.py                       # FastAPI 应用，HTTP/WebSocket/WebRTC API
│   ├── controller.py                # 终端控制器，状态机 + 控制命令发送
│   ├── protocol.py                  # 海尔私有协议解析（控制帧/音频包/视频包）
│   ├── media.py                     # MediaHub，音视频解码与 WebRTC 轨道
│   ├── webrtc.py                    # WebRTC 管理器，浏览器媒体交互
│   ├── state.py                     # 通话状态机
│   ├── events.py                    # 事件总线 + 结构化日志
│   └── config.py                    # 配置（IP/端口/认证）
├── custom_components/haier_hr6107/  # Home Assistant 自定义集成
│   ├── __init__.py
│   ├── api.py                       # HA→软件终端 HTTP 客户端
│   ├── coordinator.py               # 数据更新协调器
│   ├── binary_sensor.py             # 来电二元传感器
│   ├── sensor.py                    # 通话/服务状态传感器
│   ├── button.py                    # 开门按钮实体
│   ├── config_flow.py               # 配置向导
│   └── manifest.json
├── tools/                           # 抓包与分析工具
│   ├── capture_901.py               # 901 双向抓包采集
│   ├── analyze_901.py               # 抓包分析（方向验证/命令推导）
│   └── README.md
├── tests/                           # 安全性测试
│   └── test_security.py
├── captures/                        # 抓包证据文件
├── protocol_profile.json            # 协议安全门控（关键配置）
├── haier_dashboard_v2.html          # WebRTC 可视对讲网页
├── run_hr6107.py                    # 启动入口
├── start_hr6107.ps1                 # Windows 启动脚本
├── stop_hr6107.ps1                  # Windows 停止脚本
├── requirements.txt                 # Python 依赖
└── HR-6107_抓包分析与HA接入记录.md    # 完整逆向分析文档
```

---

## 快速开始

### 环境要求

- Python 3.11+
- Windows / Linux / macOS
- 一块网卡配置为门禁网段 IP `172.30.2.47/24`（或通过环境变量自定义）
- 网络可达门口机 `172.30.2.36`

### MT300N-V2 双网部署要点

- 家庭侧通过 Wi-Fi 中继获得固定 DHCP 租约；门禁侧 WAN 使用终端身份地址 `172.30.2.47/24`，不配置网关或 DNS。
- 家庭网主机添加静态路由：`172.30.2.0/24` 经 MT300N-V2 的家庭侧地址。
- 防火墙将家庭侧 `wwan` 与门禁侧物理 `wan` 分离，仅放行指定服务主机。
- 部分 MT300N-V2 固件会把经中继转发的单播帧保留为二层广播，需要在 `apcli0` ingress 将目标门禁网段的 `pkttype` 修正为 `host`。
- 路由器管理地址、家庭侧 MAC 和实际内网 IP 属于本地部署秘密，不应提交到公开仓库。

### 安装

```bash
git clone https://github.com/Salvatore0104/DoorKey.git
cd DoorKey
pip install -r requirements.txt
```

### Windows 启动

将网卡静态 IP 设为 `172.30.2.47`，子网掩码 `255.255.255.0`（无需网关），然后：

```powershell
.\start_hr6107.ps1
```

打开 `http://127.0.0.1:8088/`。

- 如果启用了认证（`HR6107_AUTH_REQUIRED=1`），使用 `.hr6107_api_token` 文件中的令牌登录
- 默认本地访问无需认证

### 停止服务

```powershell
.\stop_hr6107.ps1
```

### 手动启动

```bash
python run_hr6107.py
```

### 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HR6107_DEVICE_IP` | `172.30.2.47` | 软件终端监听 IP |
| `HR6107_DOOR_IP` | `172.30.2.36` | 门口机 IP |
| `HR6107_WEB_HOST` | `127.0.0.1` | Web 服务绑定地址 |
| `HR6107_WEB_PORT` | `8088` | Web 服务端口 |
| `HR6107_AUTH_REQUIRED` | `0` | 是否启用令牌认证 |
| `HR6107_API_TOKEN` | (自动生成) | 自定义访问令牌 |

---

## 配置说明

### `protocol_profile.json`

**这是整个系统的安全门控文件。** 控制命令（接听/挂断/开门）和上行音频是否启用，完全取决于此文件中的 `verified` 字段。

```json
{
  "version": 2,
  "verified": true,
  "commands": {
    "call_ack": "ffff001c...",
    "answer":   "ffff001a...0005fe",
    "hangup":   "ffff001a...0006fe",
    "unlock":   "ffff001a...0003fe",
    "reject_or_cancel": "ffff001a...0008fe"
  },
  "audio_tx": {
    "verified": false,
    "header_template_hex": null,
    "sequence_offset": 0,
    "packet_samples": 512,
    "sample_rate": 8000,
    "codec": "pcmu"
  }
}
```

- `verified: true` — 控制命令已通过 901 双向抓包验证，可安全发送
- `audio_tx.verified: false` — 上行音频头尚未完整逆向，浏览器麦克风暂不发送

---

## 安全门控

系统采用**默认禁用**策略，避免发送未验证的协议报文：

1. **`protocol_profile.json` 是唯一开关** — 所有控制命令和上行音频的启用都依赖此文件的 `verified` 字段
2. **不猜测、不重放** — 如果某项命令未验证，对应的 API 端点和 UI 按钮会直接禁用，不会发送任何猜测报文
3. **固定目标** — 后端不接受目标 IP、房号或原始十六进制报文作为参数，门口机 IP 在配置中固定
4. **限频保护** — 开门命令有 10 秒冷却时间，防止误触
5. **审计日志** — 所有控制命令的发送都会记录到 `hr6107_service.jsonl`

### 验证流程

启用新命令必须遵循以下流程（详见 `tools/README.md`）：

1. 使用交换机端口镜像或网络 TAP 获取真正的双向抓包
2. 每项操作重复 3 次，保存为独立 pcapng
3. 运行 `python tools/analyze_901.py <capture.pcapng>`
4. 确认报告 `bidirectional: true` 且 TCP 载荷字段在 3 次样本中一致
5. 人工填写 `protocol_profile.json` 并设置 `verified: true`

---

## Home Assistant 集成

### 安装

将 `custom_components/haier_hr6107` 复制到 HA 配置目录的 `custom_components/` 下，重启 HA。

在「设备与服务」中搜索添加 **Haier HR-6107**：

- **服务地址**：运行软件终端的家庭网地址，如 `http://192.168.1.20:8088`
- **令牌**：取自软件终端目录的 `.hr6107_api_token`

### 提供的实体

| 实体 | 类型 | 说明 |
|------|------|------|
| 来电 | binary_sensor | 门口机来电状态 |
| 通话状态 | sensor | IDLE/RINGING/ACTIVE 等 |
| 服务状态 | sensor | 监听在线/离线 |
| 开门 | button | 发送开门命令（10秒限频，需协议验证） |

### Lovelace 嵌入可视对讲页面

```yaml
type: iframe
url: http://192.168.1.20:8088/
aspect_ratio: 70%
```

---

## 抓包与协议分析工具

### 采集 901 双向数据

```powershell
# 列出网卡
python tools/capture_901.py --list

# 开始采集（替换为实际网卡编号）
python tools/capture_901.py --interface 4
```

采集时按动作输入标记：`ring`、`answer`、`unlock`、`hangup`、`monitor_start`、`monitor_stop`。

### 分析抓包

```powershell
python tools/analyze_901.py captures/901_bidirectional.pcapng
```

输出报告包含：
- 方向验证（`terminal_to_door_seen` / `door_to_terminal_seen` / `bidirectional`）
- 所有 TCP 46752 控制载荷
- UDP 46753/46754 媒体统计
- 动作时间窗口内的候选报文

> ⚠️ 只有 `bidirectional: true` 的抓包才能用于命令推导。普通旁路抓包只能看到广播和部分下行流量。

---

## 已知问题与限制

### 1. 上行音频（终端听不见客户机语音）

`protocol_profile.json` 中 `audio_tx.verified: false`，导致浏览器麦克风采集的音频不发送。
上行音频 UDP 46753 的 20 字节私有头尚未完整逆向。`captures/901_upstream_direction_check.pcapng`
已抓到 87 个上行音频包，待逆向还原后即可启用。

### 2. 空闲开门不生效

开门命令 `0003fe` 在**通话中发送有效**，但空闲状态下门口机不响应网络开门命令。
抓包 `901_idle_unlock_1` 证实：空闲时终端发送开门命令后门口机零响应。
实体开门键在空闲时可能走排线直连电控锁，不经过网络。

### 3. 视频偶发解码损坏

UDP 分片在抓包丢包或交换机转发异常时可能出现花屏，属于传输层问题，非协议解析问题。

### 4. 单向抓包局限

大部分历史抓包为旁路抓包，只能看到门口机→终端的下行流量。上行控制命令的完整验证
需要交换机端口镜像或网络 TAP。

---

## 网络隔离要求

> ⚠️ **安全警告**：门禁专网与家庭 LAN 不可直接二层桥接。

- 软件终端设备的门禁网卡只配置门禁网段 IP，**不设默认网关**，不开启 IP 转发
- Web 服务绑定 `127.0.0.1` 或家庭网侧网卡 IP，不在门禁网卡上暴露
- 不将门禁、摄像头或代理端口映射到公网
- 手机远程访问应通过 Home Assistant 官方远程访问或家庭 VPN
- 测试只针对本人住宅终端及本人发起的呼叫

---

## 后续计划

- [ ] 逆向上行音频 20 字节私有头，启用双向对讲
- [ ] 评估空闲开门的协议可行性（可能需要前置会话命令）
- [ ] 86 底盒嵌入式设备部署方案（树莓派 Zero 2W / ESP32-S3）
- [ ] RTSP 转发（通过 go2rtc / MediaMTX 将私有 H.264 转为标准 RTSP）
- [ ] MQTT 事件桥接（将来电/通话状态发布为 MQTT 消息）

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+ / FastAPI / uvicorn |
| 实时通信 | WebSockets / aiortc (WebRTC) |
| 媒体处理 | PyAV (FFmpeg) / audioop |
| 前端 | 原生 HTML/CSS/JS + WebRTC API |
| HA 集成 | Home Assistant Custom Component (local_polling) |
| 协议分析 | tshark / Wireshark / 自定义 Python 脚本 |

## License

本项目仅供个人住宅门禁系统的合法替换和研究使用。请遵守当地法律法规，不得用于
未授权访问他人门禁系统或采集他人音视频数据。
