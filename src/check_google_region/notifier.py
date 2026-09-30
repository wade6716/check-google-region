"""Notification delivery manager for check-google-region.

Features:
- Port-adaptive SMTP: 465 SSL, 587/25 STARTTLS
- HTML & Plain text dual-format email alerts
- Enriched alert metadata: Public IP, Timestamp, Hostname, Detection source
- Optional Telegram Bot and Custom Webhook notifications
- Test alert utility for CLI verification
"""

import datetime
import json
import smtplib
import socket
import ssl
import urllib.request
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .config import Config


class Notifier:
    def __init__(self, config: Config, verbose: bool = False):
        self.config = config
        self.verbose = verbose

    def send_alert(
        self,
        old_country: Optional[str],
        new_country: str,
        public_ip: Optional[str] = None,
        source: str = "YouTube",
        is_test: bool = False,
    ) -> bool:
        """Dispatch alerts to configured channels (Email, Telegram, Webhook)."""
        hostname = socket.gethostname()
        now_str = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        ip_display = public_ip or "未知 / 未能获取"

        is_sent_to_cn = (new_country == "CN")

        if is_test:
            subject = f"【测试】Google 区域检测通知测试 - {hostname}"
            header_title = "Google 区域监控 - 测试通知"
            summary_desc = "这是一封由 --test-email 触发的测试通知，说明您的通知通道配置有效。"
        elif is_sent_to_cn:
            subject = f"【紧急告警】服务器 IP 被 Google 标记为中国区 (CN)！ - {hostname}"
            header_title = "⚠️ 紧急告警：Google 区域送中 (CN)！"
            summary_desc = "警告：检测到服务器 IP 已被 Google / YouTube 判定为中国大陆地区，请及时排查网络或更换分流出口。"
        else:
            subject = f"【通知】Google 归属地区变更: {old_country or '未知'} -> {new_country} - {hostname}"
            header_title = "Google 归属地区变更通知"
            summary_desc = "通知：服务器对外访问 Google 时识别的国家/地区已发生变更。"

        # Plaintext body
        text_content = (
            f"{header_title}\n"
            f"{'=' * 40}\n"
            f"{summary_desc}\n\n"
            f"- 服务器主机名: {hostname}\n"
            f"- 服务器公网 IP: {ip_display}\n"
            f"- 历史判定地区: {old_country or '未知 (初次)'}\n"
            f"- 最新判定地区: {new_country}\n"
            f"- 判定来源端点: {source}\n"
            f"- 检测时间戳: {now_str}\n"
            f"{'=' * 40}\n"
        )

        # HTML body
        badge_color = "#e53e3e" if is_sent_to_cn else "#3182ce"
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7fafc; color: #2d3748; padding: 20px; }}
  .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
  .header {{ background-color: {badge_color}; color: #ffffff; padding: 16px 24px; font-size: 18px; font-weight: bold; }}
  .body {{ padding: 24px; }}
  .desc {{ margin-bottom: 20px; font-size: 15px; line-height: 1.6; color: #4a5568; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #edf2f7; font-size: 14px; }}
  td.label {{ width: 130px; color: #718096; font-weight: 600; }}
  td.value {{ color: #1a202c; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 13px; }}
  .tag-old {{ background-color: #edf2f7; color: #4a5568; }}
  .tag-new {{ background-color: {'#fed7d7; color: #9b2c2c;' if is_sent_to_cn else '#c6f6d5; color: #22543d;'} }}
  .footer {{ background-color: #f7fafc; border-top: 1px solid #e2e8f0; padding: 12px 24px; font-size: 12px; color: #a0aec0; text-align: center; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">{header_title}</div>
    <div class="body">
      <div class="desc">{summary_desc}</div>
      <table>
        <tr><td class="label">服务器主机名</td><td class="value"><code>{hostname}</code></td></tr>
        <tr><td class="label">服务器公网 IP</td><td class="value"><code>{ip_display}</code></td></tr>
        <tr><td class="label">地区变更</td><td class="value"><span class="tag tag-old">{old_country or '未知'}</span> ➔ <span class="tag tag-new">{new_country}</span></td></tr>
        <tr><td class="label">判定来源</td><td class="value">{source}</td></tr>
        <tr><td class="label">检测时间</td><td class="value">{now_str}</td></tr>
      </table>
    </div>
    <div class="footer">由 check-google-region 自动监控发送</div>
  </div>
</body>
</html>
"""

        success = True

        # 1. Send Email
        if self._is_email_configured():
            if is_test:
                print(f"[*] 正在尝试连接 {self.config.smtp_server}:{self.config.smtp_port} 发送测试邮件...")
            mail_ok = self._send_email(subject, text_content, html_content)
            success = success and mail_ok
        else:
            if is_test:
                print("[!] 尚未配置有效的发件人或接收人邮箱，请先在 .env 或环境变量中配置 SMTP_USER 和 RECEIVER_EMAIL。")
                success = False
            elif self.verbose:
                print("[*] 未配置有效的 SMTP 发件人或接收人，跳过邮件发送。")

        # 2. Send Telegram (if configured)
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            tg_text = f"*{header_title}*\n{summary_desc}\n\n*主机名*: `{hostname}`\n*IP*: `{ip_display}`\n*变更*: `{old_country or '未知'}` -> `{new_country}`\n*时间*: `{now_str}`"
            tg_ok = self._send_telegram(tg_text)
            success = success and tg_ok

        # 3. Send Webhook (if configured)
        if self.config.webhook_url:
            webhook_payload = {
                "title": header_title,
                "summary": summary_desc,
                "hostname": hostname,
                "ip": public_ip,
                "old_country": old_country,
                "new_country": new_country,
                "timestamp": now_str,
                "is_sent_to_cn": is_sent_to_cn,
            }
            webhook_ok = self._send_webhook(webhook_payload)
            success = success and webhook_ok

        return success

    def _is_email_configured(self) -> bool:
        """Check if SMTP credentials appear configured."""
        return (
            bool(self.config.smtp_server)
            and bool(self.config.smtp_user)
            and self.config.smtp_user != "your_email@qq.com"
            and bool(self.config.receiver_email)
            and self.config.receiver_email != "target@example.com"
        )

    def _send_email(self, subject: str, text_content: str, html_content: str) -> bool:
        """Send adaptive SSL / STARTTLS email."""
        msg = MIMEMultipart("alternative")
        msg["From"] = Header(f"Google Region Monitor <{self.config.smtp_user}>", "utf-8")
        msg["To"] = Header(self.config.receiver_email, "utf-8")
        msg["Subject"] = Header(subject, "utf-8")

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        server_host = self.config.smtp_server
        server_port = self.config.smtp_port

        try:
            if server_port == 465:
                # Direct SSL
                context = ssl.create_default_context()
                if self.config.insecure_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE

                with smtplib.SMTP_SSL(server_host, server_port, context=context, timeout=15) as server:
                    server.login(self.config.smtp_user, self.config.smtp_pass)
                    server.sendmail(self.config.smtp_user, [self.config.receiver_email], msg.as_string())
            else:
                # STARTTLS (e.g. 587 or 25)
                context = ssl.create_default_context()
                if self.config.insecure_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE

                with smtplib.SMTP(server_host, server_port, timeout=15) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(self.config.smtp_user, self.config.smtp_pass)
                    server.sendmail(self.config.smtp_user, [self.config.receiver_email], msg.as_string())

            print(f"[OK] 报警邮件已成功发送至 {self.config.receiver_email}")
            return True
        except Exception as e:
            print(f"[!] 邮件发送失败: {e}")
            return False

    def _send_telegram(self, text: str) -> bool:
        """Send message via Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        data = json.dumps({
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"[OK] Telegram 告警推送成功")
                    return True
        except Exception as e:
            print(f"[!] Telegram 推送失败: {e}")
        return False

    def _send_webhook(self, payload: dict) -> bool:
        """Send payload via generic Webhook."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.config.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    print(f"[OK] Webhook 告警推送成功")
                    return True
        except Exception as e:
            print(f"[!] Webhook 推送失败: {e}")
        return False
