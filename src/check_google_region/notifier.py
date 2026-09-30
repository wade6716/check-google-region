"""Notification delivery manager for check-google-region with Dual-Stack (IPv4 / IPv6) alerts.

Features:
- Dual-Stack aware alerting (distinctly flags IPv4 vs IPv6 changes)
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

    def send_stack_alert(
        self,
        stack_name: str,
        old_country: Optional[str],
        new_country: str,
        public_ip: Optional[str] = None,
        source: str = "YouTube Premium",
        is_test: bool = False,
        dual_status: Optional[dict] = None,
    ) -> bool:
        """Dispatch dual-stack alerts to configured channels (Email, Telegram, Webhook)."""
        hostname = socket.gethostname()
        now_str = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        ip_display = public_ip or "未知 / 未能获取"

        is_sent_to_cn = (new_country == "CN")

        if is_test:
            subject = f"【测试】Google 区域检测通知测试 ({stack_name}) - {hostname}"
            header_title = f"Google 区域监控 - 测试通知 ({stack_name})"
            summary_desc = "这是一封由 --test-email 触发的测试通知，说明您的通知通道配置有效。"
        elif is_sent_to_cn:
            subject = f"【紧急告警】服务器 {stack_name} 被 Google 标记为中国区 (CN)！ - {hostname}"
            header_title = f"⚠️ 紧急告警：Google 区域送中 ({stack_name})！"
            summary_desc = f"警告：检测到服务器 {stack_name} 出口已被 Google / YouTube 判定为中国大陆地区，请及时排查网络或更换分流出口。"
        else:
            subject = f"【通知】Google 归属地区变更 ({stack_name}): {old_country or '未知'} -> {new_country} - {hostname}"
            header_title = f"Google 归属地区变更通知 ({stack_name})"
            summary_desc = f"通知：服务器 {stack_name} 对外访问 Google 时识别的国家/地区已发生变更。"

        # Plaintext body
        text_lines = [
            header_title,
            "=" * 40,
            summary_desc,
            "",
            f"- 服务器主机名: {hostname}",
            f"- 触发协议栈: {stack_name}",
            f"- 发生变动 IP: {ip_display}",
            f"- 历史判定地区: {old_country or '未知 (初次)'}",
            f"- 最新判定地区: {new_country}",
            f"- 判定来源端点: {source}",
            f"- 检测时间戳: {now_str}",
        ]

        if dual_status:
            text_lines.append("")
            text_lines.append("【双栈状态总览】")
            v4_info = dual_status.get("ipv4", {})
            v6_info = dual_status.get("ipv6", {})
            text_lines.append(f"- IPv4: {v4_info.get('country', '不可达')} ({v4_info.get('ip', '无 IP')})")
            text_lines.append(f"- IPv6: {v6_info.get('country', '不可达/未启用')} ({v6_info.get('ip', '无 IP')})")

        text_lines.append("=" * 40)
        text_content = "\n".join(text_lines)

        # HTML body
        badge_color = "#e53e3e" if is_sent_to_cn else "#3182ce"

        dual_html_rows = ""
        if dual_status:
            v4_info = dual_status.get("ipv4", {})
            v6_info = dual_status.get("ipv6", {})
            dual_html_rows = f"""
            <tr><td colspan="2" style="background:#f7fafc;font-weight:bold;padding:8px 12px;color:#4a5568;">当前双栈状态总览</td></tr>
            <tr><td class="label">IPv4 状态</td><td class="value">地区: <b>{v4_info.get('country', '不可达')}</b> (<code>{v4_info.get('ip', '无 IP')}</code>)</td></tr>
            <tr><td class="label">IPv6 状态</td><td class="value">地区: <b>{v6_info.get('country', '不可达/未配置')}</b> (<code>{v6_info.get('ip', '无 IP')}</code>)</td></tr>
            """

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
        <tr><td class="label">报警协议栈</td><td class="value"><span class="tag" style="background:#edf2f7;">{stack_name}</span></td></tr>
        <tr><td class="label">变动公网 IP</td><td class="value"><code>{ip_display}</code></td></tr>
        <tr><td class="label">地区变更</td><td class="value"><span class="tag tag-old">{old_country or '未知'}</span> ➔ <span class="tag tag-new">{new_country}</span></td></tr>
        <tr><td class="label">判定来源</td><td class="value">{source}</td></tr>
        <tr><td class="label">检测时间</td><td class="value">{now_str}</td></tr>
        {dual_html_rows}
      </table>
    </div>
    <div class="footer">由 check-google-region 双栈监控自动发送</div>
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
            tg_text = f"*{header_title}*\n{summary_desc}\n\n*主机名*: `{hostname}`\n*协议栈*: `{stack_name}`\n*IP*: `{ip_display}`\n*变更*: `{old_country or '未知'}` -> `{new_country}`\n*时间*: `{now_str}`"
            tg_ok = self._send_telegram(tg_text)
            success = success and tg_ok

        # 3. Send Webhook (if configured)
        if self.config.webhook_url:
            webhook_payload = {
                "title": header_title,
                "summary": summary_desc,
                "hostname": hostname,
                "stack": stack_name,
                "ip": public_ip,
                "old_country": old_country,
                "new_country": new_country,
                "timestamp": now_str,
                "is_sent_to_cn": is_sent_to_cn,
                "dual_status": dual_status,
            }
            webhook_ok = self._send_webhook(webhook_payload)
            success = success and webhook_ok

        return success

    def send_alert(
        self,
        old_country: Optional[str],
        new_country: str,
        public_ip: Optional[str] = None,
        source: str = "YouTube Premium",
        is_test: bool = False,
    ) -> bool:
        """Legacy compatibility wrapper for single stack alert."""
        return self.send_stack_alert(
            stack_name="IPv4",
            old_country=old_country,
            new_country=new_country,
            public_ip=public_ip,
            source=source,
            is_test=is_test,
        )

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
                    print("[OK] Telegram 告警推送成功")
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
                    print("[OK] Webhook 告警推送成功")
                    return True
        except Exception as e:
            print(f"[!] Webhook 推送失败: {e}")
        return False
