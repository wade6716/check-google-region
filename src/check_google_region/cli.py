"""Command line interface and orchestration logic for check-google-region.
"""

import argparse
import datetime
import os
import socket
import sys
import time
from typing import Optional

from .config import Config
from .detector import RegionDetector
from .notifier import Notifier
from .storage import RegionState, StateManager


def setup_console_encoding() -> None:
    """Ensure safe stdout encoding on Windows consoles."""
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(errors="replace")


def parse_args(args: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-google-region",
        description="监控 Google/YouTube IP 区域变更及送中 (CN) 状态检测工具",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="仅检测当前地区和公网 IP 并打印，不修改状态、不发送通知 (Dry Run)",
    )
    parser.add_argument(
        "-t",
        "--test-email",
        action="store_true",
        help="发送一封测试告警邮件，快速排查 SMTP 账号和授权码是否配置有效",
    )
    parser.add_argument(
        "-s",
        "--status",
        action="store_true",
        help="查看本地缓存的上次检测状态与最后更新时间",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="强制发送通知并刷新状态文件（无论地区是否发生变动）",
    )
    parser.add_argument(
        "-d",
        "--daemon",
        action="store_true",
        help="以常驻守护模式运行（支持 Docker 或无需 crontab 的环境）",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=600,
        help="守护模式下的检测周期秒数 (默认 600 秒 / 10 分钟)",
    )
    parser.add_argument(
        "-p",
        "--proxy",
        type=str,
        default=None,
        help="指定本次检测使用的代理地址 (例如 http://127.0.0.1:7890)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="跳过 SSL 证书合法性验证 (不推荐在生产使用)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出详细的调试日志",
    )

    return parser.parse_args(args)


def run_cycle(
    config: Config,
    storage: StateManager,
    detector: RegionDetector,
    notifier: Notifier,
    options: argparse.Namespace,
) -> int:
    """Run a single check and notify cycle."""
    result = detector.detect(fetch_ip=True)
    current_country = result.country
    if not current_country:
        print("[!] 未能获取到有效的国家代码，放弃本次对比以避免误报。")
        return 1

    last_state = storage.load()
    last_country = last_state.country if last_state else None

    now_iso = datetime.datetime.now().astimezone().isoformat()
    new_state = RegionState(
        country=current_country,
        ip=result.public_ip,
        updated_at=now_iso,
        hostname=socket.gethostname(),
    )

    time_tag = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{time_tag}] 上次记录: {last_country or '无'} | 当前检测: {current_country} (IP: {result.public_ip or '未知'})")

    # 首次运行初始化
    if last_country is None:
        print(f"[+] 首次运行，初始化记录当前地区为: {current_country}")
        storage.save(new_state)
        return 0

    # 检查是否变动或强制发送
    if current_country != last_country or options.force:
        # 防抖确认：如果不是强制模式，则复测一次以避免偶发波动
        if not options.force:
            is_confirmed = detector.verify_change(current_country, debounce_seconds=3.0)
            if not is_confirmed:
                print(f"[!] 二次复测结果不一致，疑似瞬时网络波动，放弃本次告警以防误报。")
                return 0

        print(f"[!] 发现地区变更: {last_country} -> {current_country}，正在发送告警...")
        notifier.send_alert(
            old_country=last_country,
            new_country=current_country,
            public_ip=result.public_ip,
            source=result.source,
        )
        storage.save(new_state)
    else:
        # 地区未变动，如有新 IP 且旧状态缺少 IP，平滑补充更新
        if result.public_ip and (not last_state.ip or not last_state.updated_at):
            storage.save(new_state)
        print(f"[OK] 地区未发生变化 ({current_country})。")

    return 0


def main(args: Optional[list] = None) -> int:
    setup_console_encoding()
    options = parse_args(args)

    config = Config.from_env()
    if options.proxy:
        config.proxy = options.proxy
    if options.insecure:
        config.insecure_ssl = True

    storage = StateManager(config.state_file)
    detector = RegionDetector(
        proxy=config.proxy,
        insecure_ssl=config.insecure_ssl,
        verbose=options.verbose,
    )
    notifier = Notifier(config, verbose=options.verbose)

    # 1. Action: 查看本地状态
    if options.status:
        state = storage.load()
        print(f"[*] 状态文件路径: {storage.state_file}")
        if state:
            print(f"* 记录地区: {state.country}")
            print(f"* 记录公网 IP: {state.ip or '未知'}")
            print(f"* 更新时间: {state.updated_at or '未知'}")
            print(f"* 记录主机名: {state.hostname or '未知'}")
        else:
            print("[!] 当前暂无历史状态记录。")
        return 0

    # 2. Action: 测试通知发送
    if options.test_email:
        print("[*] 正在准备发送测试告警通知...")
        result = detector.detect(fetch_ip=True)
        detected_country = result.country or "TEST"
        ok = notifier.send_alert(
            old_country="TEST",
            new_country=detected_country,
            public_ip=result.public_ip,
            source=result.source,
            is_test=True,
        )
        return 0 if ok else 1

    # 3. Action: Dry Run (--check)
    if options.check:
        print("[*] 正在检测当前网络出口的 Google 区域与公网 IP...")
        result = detector.detect(fetch_ip=True)
        print(f"* 检测国家代码: {result.country or '获取失败'}")
        print(f"* 检测途径来源: {result.source}")
        print(f"* 出口公网 IP : {result.public_ip or '获取失败'}")
        return 0 if result.country else 1

    # 4. Action: 常驻守护模式
    is_daemon = options.daemon or os.getenv("DAEMON_MODE", "false").lower() in ("true", "1", "yes")
    if is_daemon:
        interval = options.interval
        if os.getenv("INTERVAL"):
            try:
                interval = int(os.getenv("INTERVAL"))
            except ValueError:
                pass
        print(f"[*] 启动常驻守护模式，检测间隔: {interval} 秒 (按 Ctrl+C 退出)...")
        try:
            while True:
                run_cycle(config, storage, detector, notifier, options)
                time.sleep(interval)
        except (KeyboardInterrupt, SystemExit):
            print("\n[*] 收到停止信号，监控守护进程已安全退出。")
            return 0

    # 5. Standard action: 单次周期检测 (适合 Crontab)
    return run_cycle(config, storage, detector, notifier, options)
