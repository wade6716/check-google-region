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
  <b>Ultra-lightweight, reliable monitor for Google/YouTube geolocation changes and China (CN) IP lockouts.</b><br>
  Zero Dependencies · Adaptive Email (SSL/STARTTLS) · Docker Ready · Debounce Verification · Daemon Mode
</p>

<p align="center">
  <a href="README.md">简体中文</a> | <a href="README_EN.md">English</a>
</p>

---

## ✨ Features

- 🛡️ **Accurate Detection with Fallback**: Queries YouTube Premium endpoints for `countryCode`/`GL` tokens, with automatic fallback to Google search redirects.
- 🔍 **Public IP Association**: Automatically resolves and records current egress public IP alongside region changes for fast VPS/proxy troubleshooting.
- ⏱️ **Debounce Verification**: Double-checks after a 3-second delay upon detecting a change to eliminate false alerts caused by transient network jitter.
- ✉️ **Adaptive SMTP Emailing**:
  - Port `465`: Direct `SMTP_SSL` (e.g. QQ, 163);
  - Port `587` / `25`: Automatically upgraded via `STARTTLS` (compatible with Gmail, Outlook, Amazon SES).
- 🎨 **Responsive HTML & Plaintext Alerts**: Clean, responsive HTML notification cards paired with readable plaintext summaries, containing hostnames, public IP, timestamps, and detection source.
- 📲 **Multi-Channel Push**: Extensible support for Telegram Bot and generic Webhooks (Discord, Slack, Feishu, DingTalk, Bark).
- 💾 **Atomic File I/O & Backward Compatibility**: Employs atomic temp-file swapping (`os.replace`) to guard against corruption, while seamlessly migrating legacy plain-text state files.
- 🚀 **Versatile Deployment**: Single-run CLI for Crontab, native `--daemon` loop, lightweight Docker (< 40MB), and Systemd service templates.
- 🪶 **Zero External Dependencies**: Built entirely with Python 3's standard library.

---

## 🖥️ Quick Start

### 1. Run with `uv`
```bash
# Check current region and egress IP (Dry Run)
uv run check-google-region --check

# View cached state
uv run check-google-region --status

# Test notification channel
uv run check-google-region --test-email
```

### 2. Install via `pip`
```bash
pip install check-google-region

# View help
check-google-region --help
```

---

## 🛠️ CLI Options

```text
Usage: check-google-region [OPTIONS]

Options:
  -c, --check          Detect and print current region & public IP without saving or alerting (Dry Run)
  -t, --test-email     Send a test notification to verify SMTP / Webhook setup
  -s, --status         Inspect locally cached status and last check time
  -f, --force          Force alert notification and state refresh regardless of changes
  -d, --daemon         Run continuously in daemon mode (ideal for Docker / standalone VPS)
  -i, --interval SEC   Interval between checks in daemon mode (default: 600s / 10m)
  -p, --proxy URL      Specify proxy URL for detection (e.g. http://127.0.0.1:7890)
  --insecure           Bypass SSL certificate verification
  -v, --verbose        Enable verbose debug logging
  -h, --help           Show help message and exit
```

---

## ⚙️ Configuration

Create a `.env` file in the working directory (see [.env.example](.env.example)) or configure via environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `STATE_FILE` | Linux: `/var/tmp/last_google_country.json`<br>Windows: `%TEMP%\last_google_country.json` | Path to persistent state file |
| `SMTP_SERVER` | `smtp.qq.com` | SMTP server address |
| `SMTP_PORT` | `465` | SMTP port (465 SSL, 587 STARTTLS) |
| `SMTP_USER` | `your_email@qq.com` | Sender email address |
| `SMTP_PASS` | `your_smtp_auth_token` | SMTP password or app-specific password |
| `RECEIVER_EMAIL` | `target@example.com` | Destination alert email address |
| `HTTP_PROXY` | `None` | Proxy URL (e.g. `http://127.0.0.1:7890`) |
| `INSECURE_SSL` | `false` | Disable SSL certificate verification if `true` |
| `TELEGRAM_BOT_TOKEN` | `None` | Telegram Bot token (optional) |
| `TELEGRAM_CHAT_ID` | `None` | Telegram Chat ID (optional) |
| `WEBHOOK_URL` | `None` | Generic JSON Webhook URL (optional) |
| `DAEMON_MODE` | `false` | Run continuously in daemon mode |
| `INTERVAL` | `600` | Loop interval in seconds for daemon mode |

---

## 🚢 Deployment Guides

### Option 1: Docker Compose (Recommended)

Run as an isolated, persistent container without needing local Python or cron configurations:

```yaml
services:
  check-google-region:
    build: .
    container_name: check-google-region
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - region_data:/var/tmp

volumes:
  region_data:
```

```bash
docker compose up -d
```

### Option 2: Linux Crontab

```cron
# Run every 10 minutes
*/10 * * * * cd /opt/check_google_region && /opt/check_google_region/.venv/bin/check-google-region >> /var/log/check_google_region.log 2>&1
```

### Option 3: Systemd Service

Copy [deploy/check-google-region.service](deploy/check-google-region.service) to `/etc/systemd/system/`:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now check-google-region
sudo journalctl -u check-google-region -f
```

---

## 🧪 Testing

Run the included unit test suite:

```bash
python -m unittest discover tests -v
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Contributions and PRs are welcome!
