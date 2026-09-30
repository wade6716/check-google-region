"""Detection engine for Google/YouTube region and public IP.

Features:
- YouTube Premium country code detection
- Google redirect fallback
- Public IP address lookup
- Proxy support
- Safe SSL defaults with optional bypass
"""

import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class DetectionResult:
    country: Optional[str]
    public_ip: Optional[str] = None
    source: str = "unknown"
    error: Optional[str] = None


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

    def get_public_ip(self, timeout: int = 5) -> Optional[str]:
        """Fetch current egress public IP from reliable services."""
        endpoints = [
            ("https://cloudflare.com/cdn-cgi/trace", r"ip=([0-9a-fA-F:.]+)"),
            ("https://api.ipify.org", r"^([0-9a-fA-F:.]+)$"),
            ("https://checkip.amazonaws.com", r"^([0-9a-fA-F:.]+)$"),
        ]

        opener = self._build_opener()
        for url, pattern in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.DEFAULT_UA})
                with opener.open(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8", errors="ignore").strip()
                    match = re.search(pattern, body, re.MULTILINE)
                    if match:
                        ip = match.group(1).strip()
                        if self.verbose:
                            print(f"[*] 获取到公网 IP: {ip} (来自 {url})")
                        return ip
            except Exception as e:
                if self.verbose:
                    print(f"[*] 从 {url} 获取 IP 失败: {e}")
                continue

        return None

    def get_google_region(self, timeout: int = 10) -> Tuple[Optional[str], str]:
        """Detect country code recognized by Google / YouTube.
        Returns: (country_code, detection_source)
        """
        opener = self._build_opener()
        headers = {
            "User-Agent": self.DEFAULT_UA,
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 1. Primary: YouTube Premium
        try:
            req = urllib.request.Request("https://www.youtube.com/premium", headers=headers)
            with opener.open(req, timeout=timeout) as response:
                html = response.read().decode("utf-8", errors="ignore")
                match = re.search(r'"(countryCode|GL)":"([A-Z]{2})"', html)
                if match:
                    code = match.group(2)
                    return code, "YouTube Premium"
        except Exception as e:
            if self.verbose:
                print(f"[!] 请求 YouTube 异常: {e}")

        # 2. Fallback: Google.com redirect to Google HK (CN)
        try:
            req_google = urllib.request.Request("https://www.google.com", headers=headers)
            with opener.open(req_google, timeout=timeout) as resp:
                final_url = resp.geturl()
                if "google.com.hk" in final_url:
                    return "CN", "Google Redirect (HK/CN)"
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location", "")
            if "google.com.hk" in loc:
                return "CN", "Google Redirect (HK/CN)"
        except Exception as e:
            if self.verbose:
                print(f"[!] 请求 Google 异常: {e}")

        # 3. Fallback: Google Services Sitemap or News
        try:
            req_sitemap = urllib.request.Request("https://www.google.com/services/sitemap.xml", headers=headers)
            with opener.open(req_sitemap, timeout=timeout) as resp:
                final_url = resp.geturl()
                if "google.com.hk" in final_url:
                    return "CN", "Google Services (HK/CN)"
        except Exception:
            pass

        return None, "none"

    def detect(self, fetch_ip: bool = True) -> DetectionResult:
        """Run full detection for country and public IP."""
        country, source = self.get_google_region()
        public_ip = self.get_public_ip() if fetch_ip else None

        return DetectionResult(
            country=country,
            public_ip=public_ip,
            source=source,
        )

    def verify_change(self, expected_country: str, debounce_seconds: float = 3.0) -> bool:
        """Debounce verification: wait a moment and re-test to prevent flapping."""
        if self.verbose:
            print(f"[*] 发现变动，等待 {debounce_seconds} 秒后进行二次复测防抖...")
        time.sleep(debounce_seconds)
        recheck_country, _ = self.get_google_region()
        return recheck_country == expected_country
