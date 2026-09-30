"""Command line interface and orchestration logic for check-google-region with Dual-Stack (IPv4 / IPv6) support.
"""

import argparse
import datetime
import os
import socket
import sys
import time
from typing import Optional

from .config import Config
from .detector import DualStackResult, RegionDetector, StackResult
from .notifier import Notifier
from .storage import RegionState, StackState, StateManager


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
        description="监控 Google/YouTube IP 区域变更及送中 (CN) 状态检测工具 (支持 IPv4 / IPv6 双栈独立探测)",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="仅检测当前地区和公网 IP 并打印，不修改状态、不发送通知 (Dry Run)",
    )
    parser.add_argument(
        "-4",
        "--ipv4-only",
        action="store_true",
        help="仅检测 IPv4 栈",
    )
    parser.add_argument(
        "-6",
        "--ipv6-only",
        action="store_true",
        help="仅检测 IPv6 栈",
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
        default=None,
        help="守护模式下的检测周期秒数 (默认 3600 秒 / 1 小时，也支持环境变量 CHECK_INTERVAL / INTERVAL)",
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


def print_stack_check(res: StackResult) -> None:
    print(f"\n[{res.family} 栈]")
    if res.available:
        print(f"* 状态: 正常可达")
        print(f"* 检测国家代码: {res.country or '未知'}")
        print(f"* 出口公网 IP : {res.public_ip or '未能获取'}")
        print(f"* 判定来源端点: {res.source}")
    else:
        print(f"* 状态: 未配置 / 不可达")


def run_cycle(
    config: Config,
    storage: StateManager,
    detector: RegionDetector,
    notifier: Notifier,
    options: argparse.Namespace,
) -> int:
    """Run a single check and notify cycle with dual-stack support."""
    time_tag = datetime.datetime.now().strftime("%H:%M:%S")
    now_iso = datetime.datetime.now().astimezone().isoformat()
    last_state = storage.load() or RegionState(hostname=socket.gethostname())

    check_v4 = not options.ipv6_only
    check_v6 = not options.ipv4_only

    v4_res = detector.detect_stack(family=socket.AF_INET, fetch_ip=True) if check_v4 else StackResult(family="IPv4")
    v6_res = detector.detect_stack(family=socket.AF_INET6, fetch_ip=True) if check_v6 else StackResult(family="IPv6")

    dual_summary = {
        "ipv4": {
            "country": v4_res.country if v4_res.available else "不可达",
            "ip": v4_res.public_ip if v4_res.available else "无",
        },
        "ipv6": {
            "country": v6_res.country if v6_res.available else "不可达/未配置",
            "ip": v6_res.public_ip if v6_res.available else "无",
        },
    }

    # 打印简报
    v4_disp = f"{v4_res.country or '不可达'} ({v4_res.public_ip or '无IP'})" if check_v4 else "跳过"
    v6_disp = f"{v6_res.country or '不可达'} ({v6_res.public_ip or '无IP'})" if check_v6 else "跳过"
    print(f"[{time_tag}] 检测完成 | IPv4: {v4_disp} | IPv6: {v6_disp}")

    new_state = RegionState(
        ipv4=StackState(
            country=v4_res.country if v4_res.available else last_state.ipv4.country,
            ip=v4_res.public_ip if v4_res.available else last_state.ipv4.ip,
            updated_at=now_iso if v4_res.available else last_state.ipv4.updated_at,
        ),
        ipv6=StackState(
            country=v6_res.country if v6_res.available else last_state.ipv6.country,
            ip=v6_res.public_ip if v6_res.available else last_state.ipv6.ip,
            updated_at=now_iso if v6_res.available else last_state.ipv6.updated_at,
        ),
        hostname=socket.gethostname(),
    )

    state_changed = False

    # 1. 检查 IPv4
    if check_v4 and v4_res.available:
        old_v4 = last_state.ipv4.country
        new_v4 = v4_res.country
        if old_v4 is None:
            print(f"[+] 首次记录 IPv4 地区: {new_v4}")
            state_changed = True
        elif new_v4 != old_v4 or options.force:
            # 防抖
            if not options.force:
                if not detector.verify_change(new_v4, family=socket.AF_INET):
                    print("[!] IPv4 二次复测不一致，疑似网络波动，放弃告警。")
                else:
                    print(f"[!] 发现 IPv4 地区变更: {old_v4} -> {new_v4}，发送告警...")
                    notifier.send_stack_alert(
                        stack_name="IPv4",
                        old_country=old_v4,
                        new_country=new_v4,
                        public_ip=v4_res.public_ip,
                        source=v4_res.source,
                        dual_status=dual_summary,
                    )
                    state_changed = True
            else:
                notifier.send_stack_alert(
                    stack_name="IPv4",
                    old_country=old_v4,
                    new_country=new_v4,
                    public_ip=v4_res.public_ip,
                    source=v4_res.source,
                    dual_status=dual_summary,
                )
                state_changed = True

    # 2. 检查 IPv6
    if check_v6 and v6_res.available:
        old_v6 = last_state.ipv6.country
        new_v6 = v6_res.country
        if old_v6 is None:
            print(f"[+] 首次记录 IPv6 地区: {new_v6}")
            state_changed = True
        elif new_v6 != old_v6 or options.force:
            # 防抖
            if not options.force:
                if not detector.verify_change(new_v6, family=socket.AF_INET6):
                    print("[!] IPv6 二次复测不一致，疑似网络波动，放弃告警。")
                else:
                    print(f"[!] 发现 IPv6 地区变更: {old_v6} -> {new_v6}，发送告警...")
                    notifier.send_stack_alert(
                        stack_name="IPv6",
                        old_country=old_v6,
                        new_country=new_v6,
                        public_ip=v6_res.public_ip,
                        source=v6_res.source,
                        dual_status=dual_summary,
                    )
                    state_changed = True
            else:
                notifier.send_stack_alert(
                    stack_name="IPv6",
                    old_country=old_v6,
                    new_country=new_v6,
                    public_ip=v6_res.public_ip,
                    source=v6_res.source,
                    dual_status=dual_summary,
                )
                state_changed = True

    # 保存最新状态
    storage.save(new_state)

    if not state_changed:
        print("[OK] 双栈地区均未发生变动。")

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
            print(f"- 服务器主机名: {state.hostname or '未知'}")
            print("\n[IPv4 记录]")
            print(f"* 记录地区: {state.ipv4.country or '无'}")
            print(f"* 记录 IP  : {state.ipv4.ip or '无'}")
            print(f"* 更新时间: {state.ipv4.updated_at or '无'}")
            print("\n[IPv6 记录]")
            print(f"* 记录地区: {state.ipv6.country or '无/未配置'}")
            print(f"* 记录 IP  : {state.ipv6.ip or '无'}")
            print(f"* 更新时间: {state.ipv6.updated_at or '无'}")
        else:
            print("[!] 当前暂无历史状态记录。")
        return 0

    # 2. Action: 测试通知发送
    if options.test_email:
        print("[*] 正在准备发送测试告警通知...")
        v4_res = detector.detect_stack(family=socket.AF_INET, fetch_ip=True)
        v6_res = detector.detect_stack(family=socket.AF_INET6, fetch_ip=True)

        primary = v4_res if v4_res.available else v6_res
        detected_country = primary.country or "TEST"

        dual_summary = {
            "ipv4": {"country": v4_res.country or "不可达", "ip": v4_res.public_ip or "无"},
            "ipv6": {"country": v6_res.country or "不可达/未配置", "ip": v6_res.public_ip or "无"},
        }

        ok = notifier.send_stack_alert(
            stack_name="双栈测试",
            old_country="TEST",
            new_country=detected_country,
            public_ip=primary.public_ip,
            source=primary.source,
            is_test=True,
            dual_status=dual_summary,
        )
        return 0 if ok else 1

    # 3. Action: Dry Run (--check)
    if options.check:
        print("[*] 正在检测当前网络出口的 Google 区域与公网 IP (双栈独立探测)...")
        if not options.ipv6_only:
            v4_res = detector.detect_stack(family=socket.AF_INET, fetch_ip=True)
            print_stack_check(v4_res)
        if not options.ipv4_only:
            v6_res = detector.detect_stack(family=socket.AF_INET6, fetch_ip=True)
            print_stack_check(v6_res)
        return 0

    # 4. Action: 常驻守护模式
    is_daemon = options.daemon or config.daemon_mode
    if is_daemon:
        interval = options.interval if options.interval is not None else config.interval
        print(f"[*] 启动常驻双栈守护模式，检测间隔: {interval} 秒 (按 Ctrl+C 退出)...")
        try:
            while True:
                run_cycle(config, storage, detector, notifier, options)
                time.sleep(interval)
        except (KeyboardInterrupt, SystemExit):
            print("\n[*] 收到停止信号，监控守护进程已安全退出。")
            return 0

    # 5. Standard action: 单次周期检测 (适合 Crontab)
    return run_cycle(config, storage, detector, notifier, options)
