"""State persistence management for check-google-region with Dual-Stack (IPv4 / IPv6) support.

Provides atomic file writing and backward-compatible JSON/plaintext state loading.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class StackState:
    country: Optional[str] = None
    ip: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StackState":
        return cls(
            country=data.get("country"),
            ip=data.get("ip"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class RegionState:
    ipv4: StackState = field(default_factory=StackState)
    ipv6: StackState = field(default_factory=StackState)
    hostname: Optional[str] = None

    # Backward compatibility properties
    @property
    def country(self) -> Optional[str]:
        return self.ipv4.country

    @property
    def ip(self) -> Optional[str]:
        return self.ipv4.ip

    @property
    def updated_at(self) -> Optional[str]:
        return self.ipv4.updated_at

    def to_dict(self) -> dict:
        return {
            "ipv4": self.ipv4.to_dict(),
            "ipv6": self.ipv6.to_dict(),
            "hostname": self.hostname,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RegionState":
        if "ipv4" in data or "ipv6" in data:
            return cls(
                ipv4=StackState.from_dict(data.get("ipv4", {})),
                ipv6=StackState.from_dict(data.get("ipv6", {})),
                hostname=data.get("hostname"),
            )
        # Legacy single-stack format migration
        return cls(
            ipv4=StackState(
                country=data.get("country"),
                ip=data.get("ip"),
                updated_at=data.get("updated_at"),
            ),
            ipv6=StackState(),
            hostname=data.get("hostname"),
        )


class StateManager:
    def __init__(self, state_file: str):
        self.state_file = os.path.abspath(state_file)

    def load(self) -> Optional[RegionState]:
        """Load state from state_file with fallback to legacy single-stack and plaintext formats."""
        target_path = self.state_file

        # Check if json state file exists
        if not os.path.exists(target_path):
            legacy_txt = os.path.splitext(target_path)[0] + ".txt"
            if os.path.exists(legacy_txt):
                target_path = legacy_txt
            else:
                return None

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return None

            # Try parsing as JSON first
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    return RegionState.from_dict(data)
            except json.JSONDecodeError:
                pass

            # Fallback: treat as plain country code (e.g. "US")
            clean_country = content.splitlines()[0].strip().upper()
            if len(clean_country) == 2 and clean_country.isalpha():
                return RegionState(
                    ipv4=StackState(country=clean_country),
                    ipv6=StackState(),
                )

        except Exception as e:
            print(f"[!] 读取状态文件失败 ({target_path}): {e}")

        return None

    def save(self, state: RegionState) -> bool:
        """Atomically save state to file using temporary file replacement."""
        state_dir = os.path.dirname(self.state_file)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)

        tmp_file = f"{self.state_file}.tmp.{os.getpid()}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_file, self.state_file)
            return True
        except Exception as e:
            print(f"[!] 保存状态文件失败: {e}")
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            return False
