"""Detection engine for Google/YouTube region and public IP with Dual-Stack (IPv4 / IPv6) support.

Features:
- Independent IPv4 and IPv6 detection
- YouTube Premium country code detection with China lockout (送中) detection
- Google redirect fallback & cross-verification
- Public IP address lookup for IPv4 and IPv6
- Proxy support
- Safe SSL defaults with optional bypass
"""

import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Tuple


@contextmanager
def force_ip_family(family: int):
    """Context manager to force DNS resolution to a specific address family (AF_INET or AF_INET6)."""
    orig_getaddrinfo = socket.getaddrinfo

    def filtered_getaddrinfo(host, port, family_arg=0, *args, **kwargs):
        return orig_getaddrinfo(host, port, family, *args, **kwargs)

    socket.getaddrinfo = filtered_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = orig_getaddrinfo


@dataclass
class StackResult:
    family: str  # "IPv4" or "IPv6"
    available: bool = False
    country: Optional[str] = None
    public_ip: Optional[str] = None
    source: str = "none"
    error: Optional[str] = None


@dataclass
class DualStackResult:
    ipv4: StackResult
    ipv6: StackResult


# Backward compatibility alias
DetectionResult = StackResult


class RegionDetector:
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, proxy: Optional[str] = None, insecure_ssl: bool = False, verbose: bool = False):
        self.proxy = proxy
        self.insecure_ssl = insecure_ssl
        self.verbose = verbose

    def _build_opener(self) -> urllib.request.OpenerDirector:
        """Construct opener with optional proxy and SSL context."""
        handlers = []

        if self.proxy:
            handlers.append(
                urllib.request.ProxyHandler({
                    "http": self.proxy,
                    "https": self.proxy,
                })
            )

        if self.insecure_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        else:
            ctx = ssl.create_default_context()
            handlers.append(urllib.request.HTTPSHandler(context=ctx))

        return urllib.request.build_opener(*handlers)

    def get_public_ip(self, family: int = socket.AF_INET, timeout: int = 5) -> Optional[str]:
        """Fetch current egress public IP for specified IP family."""
        if family == socket.AF_INET6:
            endpoints = [
                ("https://api6.ipify.org", r"^([0-9a-fA-F:.]+)$"),
                ("https://v6.ident.me", r"^([0-9a-fA-F:.]+)$"),
                ("https://ipv6.icanhazip.com", r"^([0-9a-fA-F:.]+)$"),
            ]
        else:
            endpoints = [
                ("https://api4.ipify.org", r"^([0-9a-fA-F:.]+)$"),
                ("https://cloudflare.com/cdn-cgi/trace", r"ip=([0-9a-fA-F:.]+)"),
                ("https://api.ipify.org", r"^([0-9a-fA-F:.]+)$"),
                ("https://checkip.amazonaws.com", r"^([0-9a-fA-F:.]+)$"),
            ]

        opener = self._build_opener()
        with force_ip_family(family):
            for url, pattern in endpoints:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": self.DEFAULT_UA})
                    with opener.open(req, timeout=timeout) as resp:
                        body = resp.read().decode("utf-8", errors="ignore").strip()
                        match = re.search(pattern, body, re.MULTILINE)
                        if match:
                            ip = match.group(1).strip()
                            if self.verbose:
                                print(f"[*] 获取到公网 IP ({'IPv6' if family == socket.AF_INET6 else 'IPv4'}): {ip} (来自 {url})")
                            return ip
                except Exception as e:
                    if self.verbose:
                        print(f"[*] 从 {url} 获取 IP 失败: {e}")
                    continue

        return None

    def parse_youtube_premium_html(self, html: str) -> Tuple[Optional[str], str]:
        """Parse YouTube Premium HTML to detect country and check for China lockout (送中).
        
        Returns: (country_code, source_description)
        """
        # 1. 核心送中特征拦截：页面包含 www.google.cn 或 google.cn
        if "www.google.cn" in html or "google.cn" in html:
            return "CN", "YouTube Premium (CN Lockout)"

        # 2. 检查是否提示当前国家不支持 Premium (Premium is not available in your country)
        is_not_available = bool(re.search(r"Premium is not available in your country", html, re.I))

        # 3. 提取显式国家代码字段 (优先 countryCode，次优先 INNERTUBE_CONTEXT_GL)
        match_cc = re.search(r'"countryCode":"([A-Z]{2})"', html)
        if match_cc:
            return match_cc.group(1), "YouTube Premium"

        match_inner_gl = re.search(r'"INNERTUBE_CONTEXT_GL":"([A-Z]{2})"', html)
        if match_inner_gl and not is_not_available:
            return match_inner_gl.group(1), "YouTube Premium"

        # 4. 检查是否有 ad-free / try it free 等服务正常开放标识
        has_service_available = bool(re.search(r"ad-free|ad free|try it free|1-month free", html, re.I))

        # 5. 兜底 GL 字段：仅在服务可用且未提示不可用时采信
        match_gl = re.search(r'"GL":"([A-Z]{2})"', html)
        if match_gl and has_service_available and not is_not_available:
            return match_gl.group(1), "YouTube Premium"

        return None, "none"

    def get_google_region(self, family: int = socket.AF_INET, timeout: int = 10) -> Tuple[Optional[str], str]:
        """Detect country code recognized by Google / YouTube for specific IP family with cross-verification.
        Returns: (country_code, detection_source)
        """
        opener = self._build_opener()
        headers = {
            "User-Agent": self.DEFAULT_UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": "CONSENT=YES+cb.20220301-11-p0.en+FX+700; PREF=hl=en&tz=UTC",
        }

        with force_ip_family(family):
            yt_country: Optional[str] = None
            yt_source: str = "none"

            # 1. Primary: YouTube Premium
            try:
                req = urllib.request.Request("https://www.youtube.com/premium", headers=headers)
                with opener.open(req, timeout=timeout) as response:
                    html = response.read().decode("utf-8", errors="ignore")
                    yt_country, yt_source = self.parse_youtube_premium_html(html)
                    # 如果明确判定为 CN 送中，立即返回
                    if yt_country == "CN":
                        return "CN", yt_source
            except Exception as e:
                if self.verbose:
                    print(f"[!] ({'IPv6' if family == socket.AF_INET6 else 'IPv4'}) 请求 YouTube 异常: {e}")

            # 2. 交叉验证与兜底：检查 Google.com 是否重定向至 google.com.hk (送中特征)
            google_is_cn = False
            try:
                req_google = urllib.request.Request("https://www.google.com", headers=headers)
                with opener.open(req_google, timeout=timeout) as resp:
                    final_url = resp.geturl()
                    if "google.com.hk" in final_url or "google.cn" in final_url:
                        google_is_cn = True
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location", "")
                if "google.com.hk" in loc or "google.cn" in loc:
                    google_is_cn = True
            except Exception as e:
                if self.verbose:
                    print(f"[!] ({'IPv6' if family == socket.AF_INET6 else 'IPv4'}) 请求 Google 异常: {e}")

            # 交叉纠偏：如果 Google.com 重定向到了 google.com.hk，代表在 Google 体系中已全面送中！
            if google_is_cn:
                return "CN", "Google Redirect (HK/CN)"

            # 如果 YouTube 成功检测出正常国家且 Google 未重定向至 HK/CN，返回 YouTube 结果
            if yt_country and yt_country != "CN":
                return yt_country, yt_source

            # 3. Fallback: Google Services Sitemap
            try:
                req_sitemap = urllib.request.Request("https://www.google.com/services/sitemap.xml", headers=headers)
                with opener.open(req_sitemap, timeout=timeout) as resp:
                    final_url = resp.geturl()
                    if "google.com.hk" in final_url or "google.cn" in final_url:
                        return "CN", "Google Services (HK/CN)"
            except Exception:
                pass

        return None, "none"

    def detect_stack(self, family: int = socket.AF_INET, fetch_ip: bool = True) -> StackResult:
        """Run detection for a specific IP stack (AF_INET or AF_INET6)."""
        family_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
        public_ip = self.get_public_ip(family=family) if fetch_ip else None
        country, source = self.get_google_region(family=family)

        available = bool(country or public_ip)
        return StackResult(
            family=family_name,
            available=available,
            country=country,
            public_ip=public_ip,
            source=source,
        )

    def detect(self, fetch_ip: bool = True) -> StackResult:
        """Legacy default single-stack detection (IPv4)."""
        return self.detect_stack(family=socket.AF_INET, fetch_ip=fetch_ip)

    def detect_dual_stack(self, fetch_ip: bool = True) -> DualStackResult:
        """Run dual-stack detection for both IPv4 and IPv6."""
        v4_res = self.detect_stack(family=socket.AF_INET, fetch_ip=fetch_ip)
        v6_res = self.detect_stack(family=socket.AF_INET6, fetch_ip=fetch_ip)
        return DualStackResult(ipv4=v4_res, ipv6=v6_res)

    def verify_change(
        self,
        expected_country: str,
        family: int = socket.AF_INET,
        debounce_seconds: float = 3.0,
    ) -> bool:
        """Debounce verification: wait a moment and re-test to prevent flapping."""
        family_name = "IPv6" if family == socket.AF_INET6 else "IPv4"
        if self.verbose:
            print(f"[*] 发现 {family_name} 变动，等待 {debounce_seconds} 秒后进行二次复测防抖...")
        time.sleep(debounce_seconds)
        recheck_country, _ = self.get_google_region(family=family)
        return recheck_country == expected_country
