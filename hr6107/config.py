from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    device_ip: str = "172.30.2.47"
    listen_ip: str = "0.0.0.0"
    door_ip: str = "172.30.2.36"
    control_port: int = 46752
    audio_port: int = 46753
    video_port: int = 46754
    web_host: str = "127.0.0.1"
    web_port: int = 8088
    unlock_cooldown_seconds: float = 10.0
    ring_timeout_seconds: float = 30.0
    auth_required: bool = False
    unlock_idle_enabled: bool = False
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent

    @property
    def profile_path(self) -> Path:
        return self.base_dir / "protocol_profile.json"

    @property
    def token_path(self) -> Path:
        return self.data_dir / ".hr6107_api_token"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "hr6107_service.jsonl"

    def api_token(self) -> str:
        configured = os.getenv("HR6107_API_TOKEN")
        if configured:
            return configured
        if self.token_path.exists():
            return self.token_path.read_text(encoding="utf-8").strip()
        token = secrets.token_urlsafe(32)
        self.token_path.write_text(token, encoding="utf-8")
        return token


def load_settings() -> Settings:
    auth_value = os.getenv("HR6107_AUTH_REQUIRED", "0").strip().lower()
    unlock_idle_value = os.getenv("HR6107_UNLOCK_IDLE_ENABLED", "0").strip().lower()
    return Settings(
        device_ip=os.getenv("HR6107_DEVICE_IP", "172.30.2.47"),
        listen_ip=os.getenv("HR6107_LISTEN_IP", "0.0.0.0"),
        door_ip=os.getenv("HR6107_DOOR_IP", "172.30.2.36"),
        web_host=os.getenv("HR6107_WEB_HOST", "127.0.0.1"),
        web_port=int(os.getenv("HR6107_WEB_PORT", "8088")),
        data_dir=Path(os.getenv("HR6107_DATA_DIR", str(Path(__file__).resolve().parent.parent))),
        auth_required=auth_value in {"1", "true", "yes", "on"},
        unlock_idle_enabled=unlock_idle_value in {"1", "true", "yes", "on"},
    )
