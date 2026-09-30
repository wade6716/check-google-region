"""Check Google / YouTube IP region and send email alerts on changes.

Public exports:
- main(): CLI entrypoint
- get_current_google_region(): Legacy compatible helper
- send_alert_email(): Legacy compatible helper
- RegionDetector: Detector class
- Notifier: Notification dispatcher
- StateManager: State persistence manager
- Config: Configuration holder
"""

from typing import Optional

from .cli import main, setup_console_encoding
from .config import Config
from .detector import DetectionResult, RegionDetector
from .notifier import Notifier
from .storage import RegionState, StateManager

__all__ = [
    "main",
    "get_current_google_region",
    "send_alert_email",
    "RegionDetector",
    "Notifier",
    "StateManager",
    "RegionState",
    "Config",
    "DetectionResult",
]


def get_current_google_region(proxy: Optional[str] = None) -> Optional[str]:
    """Legacy compatibility function for detecting current Google region."""
    detector = RegionDetector(proxy=proxy)
    result = detector.detect(fetch_ip=False)
    return result.country


def send_alert_email(old_country: Optional[str], new_country: str) -> bool:
    """Legacy compatibility function for sending email alert."""
    config = Config.from_env()
    notifier = Notifier(config)
    detector = RegionDetector(proxy=config.proxy)
    ip = detector.get_public_ip()
    return notifier.send_alert(
        old_country=old_country,
        new_country=new_country,
        public_ip=ip,
    )


if __name__ == "__main__":
    setup_console_encoding()
    raise SystemExit(main())
