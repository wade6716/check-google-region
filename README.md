# check-google-region

<p align="center">
  <a href="https://github.com/wade6716/check-google-region/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/wade6716/check-google-region/ci.yml?branch=main&label=CI&logo=github" alt="CI Status">
  </a>
  <a href="https://pypi.org/project/check-google-region/">
    <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg?logo=python" alt="Python Versions">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
  </a>
  <a href="https://github.com/wade6716/check-google-region/releases">
    <img src="https://img.shields.io/github/v/release/wade6716/check-google-region?color=orange" alt="Release">
  </a>
</p>

<p align="center">
  <b>极轻量、高可靠的服务器出口 Google / YouTube 地区判定变动与“送中 (CN)”告警监控工具。</b><br>
  零第三方依赖（纯 Python 标准库） · 邮件自适应 (SSL/STARTTLS) · Docker 容器化 · 抖动防误报 · 守护模式
</p>

<p align="center">
  <a href="README.md">简体中文</a> | <a href="README_EN.md">English</a>
</p>

---

## ✨ 核心亮点

- 🌐 **IPv4 / IPv6 双栈独立探测**：分别独立检测 IPv4 和 IPv6 的出口公网 IP 与 Google 判定区域，精准定位究竟是哪个栈被送中，彻底告别单栈混淆。
- 🛡️ **精准判定与多重兜底**：优先通过 YouTube Premium 页面解析国家代码（`countryCode`/`GL`），若遇限流自动回退至 Google 重定向端点判定。
- 🔍 **公网 IP 自动关联**：告警与状态记录自动关联当前出口的公网 IP，在维护多台 VPS 或弹性 IP 时定位一目了然。
- ⏱️ **防抖二次复测机制 (Debounce)**：初次检测到地区变更时，默认在 3 秒后发起二次探测确认，确认变动才触发告警，避免偶发网络波动导致垃圾邮件轰炸。
- ✉️ **邮件协议全端口自适应**：
  - `465` 端口：自动采用直接 `SMTP_SSL`（如 QQ / 163 邮箱）；
  - `587` / `25` 端口：自动升级 `STARTTLS`（完美兼容 Gmail、Outlook 等主流服务商）。
- 🎨 **精美响应式 HTML 告警**：告警邮件同时提供精美高亮 HTML 卡片与纯文本摘要，包含公网 IP、主机名、检测途径及精确时间戳。
- 📲 **多渠道通知扩展**：除邮件外，支持可选的 Telegram Bot 与通用 Webhook（企业微信 / 飞书 / Bark / Discord 等）。
- 💾 **原子写入与旧版平滑兼容**：临时文件 + `os.replace` 原子替换，避免服务器断电损坏缓存；自动识别并升级旧版纯文本缓存。
- 🚀 **丰富部署形态**：支持 **单次执行 (Crontab)**、**内置守护常驻模式 (`--daemon`)**、**Docker / Docker Compose** 及 **Systemd**。
- 🪶 **零第三方依赖**：纯 Python 3 标准库实现，轻量纯净，无需编译 C 扩展。

---

## 🖥️ 快速上手

### 1. 使用 uv 直接运行
```bash
# 仅检测当前地区和公网 IP (Dry Run，不发信、不保存)
uv run check-google-region --check

# 查看当前本地记录的状态
uv run check-google-region --status

# 测试发信通道是否正常
uv run check-google-region --test-email
```

### 2. 使用 pip 安装使用
```bash
pip install check-google-region

# 查看帮助
check-google-region --help
```

---

## 🛠️ CLI 命令行参数全览

```text
用法: check-google-region [选项]

选项:
  -c, --check          仅检测当前地区和公网 IP 并打印，不修改状态、不发送通知 (Dry Run)
  -4, --ipv4-only      仅检测 IPv4 栈
  -6, --ipv6-only      仅检测 IPv6 栈
  -t, --test-email     发送一封测试告警邮件，快速排查 SMTP 账号和授权码是否配置有效
  -s, --status         查看本地缓存的上次检测状态与最后更新时间
  -f, --force          强制发送通知并刷新状态文件（无论地区是否发生变动）
  -d, --daemon         以常驻守护模式运行（支持 Docker 或无需 crontab 的环境）
  -i, --interval SEC   守护模式下的检测周期秒数 (默认 3600 秒 / 1 小时，支持环境变量 CHECK_INTERVAL / INTERVAL)
  -p, --proxy URL      指定本次检测使用的代理地址 (例如 http://127.0.0.1:7890)
  --insecure           跳过 SSL 证书合法性验证 (默认进行安全校验)
  -v, --verbose        输出详细的网络请求与调试日志
  -h, --help           显示帮助信息
```

---

## ⚙️ 配置说明

在项目同级目录创建 `.env` 文件（可参考 [.env.example](.env.example)），或通过系统环境变量配置：

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `STATE_FILE` | Linux: `/var/tmp/last_google_country.json`<br>Windows: `%TEMP%\last_google_country.json` | 状态缓存文件路径 |
| `SMTP_SERVER` | `smtp.qq.com` | SMTP 服务器地址 |
| `SMTP_PORT` | `465` | SMTP 端口 (465 SSL, 587 STARTTLS) |
| `SMTP_USER` | `your_email@qq.com` | 发件人邮箱 |
| `SMTP_PASS` | `your_smtp_auth_token` | 邮箱授权码/密码 |
| `RECEIVER_EMAIL` | `target@example.com` | 接收报警通知的邮箱 |
| `HTTP_PROXY` | `None` | HTTP/HTTPS 代理地址 (如 `http://127.0.0.1:7890`) |
| `INSECURE_SSL` | `false` | 是否跳过 SSL 证书校验 |
| `TELEGRAM_BOT_TOKEN` | `None` | Telegram Bot Token（可选） |
| `TELEGRAM_CHAT_ID` | `None` | Telegram Chat ID（可选） |
| `WEBHOOK_URL` | `None` | 通用 Webhook URL（可选，支持飞书/企微/Bark/Discord） |
| `DAEMON_MODE` | `false` | 是否默认以常驻守护模式运行 |
| `CHECK_INTERVAL` / `INTERVAL` | `3600` | 守护模式运行周期 (秒)，默认 1 小时 |

---

## 🚢 部署方式推荐

### 方式 1：Docker 一键运行 (推荐)

无需在宿主机安装任何 Python 环境，直接拉取预构建的多架构镜像（支持 AMD64 / ARM64）：

> 💡 **提示**：若需要完整检测宿主机的 IPv6 双栈，建议加上 `--net=host`（或在 compose 中启用 `network_mode: "host"`）。

```bash
docker run -d \
  --name check-google-region \
  --restart unless-stopped \
  --net=host \
  --env-file .env \
  -v region_data:/var/tmp \
  ghcr.io/wade6716/check-google-region:latest
```

或使用 Docker Compose 启动：

```bash
docker compose up -d
```

### 方式 2：Linux Crontab 定时任务

适合习惯使用系统原生计划任务的 VPS：

```cron
# 每 10 分钟检测一次
*/10 * * * * cd /opt/check_google_region && /opt/check_google_region/.venv/bin/check-google-region >> /var/log/check_google_region.log 2>&1
```

### 方式 3：Systemd 系统守护进程

复制模版文件 [deploy/check-google-region.service](deploy/check-google-region.service) 至 `/etc/systemd/system/`：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now check-google-region
sudo journalctl -u check-google-region -f
```

---

## 🧪 单元测试

项目内置完整的单元测试集（纯标准库 `unittest`）：

```bash
python -m unittest discover tests -v
```

---

## 📄 开源许可

本项目基于 [MIT License](LICENSE) 开源。欢迎提交 PR 和 Issue！
