import asyncio
import json

import pytest

from hr6107.config import Settings
from hr6107.controller import TerminalController
from hr6107.events import EventBus
from hr6107.media import MediaHub
from hr6107.protocol import ProtocolProfile


def test_unlock_is_profile_gated_before_network_access(tmp_path):
    profile = ProtocolProfile({"verified": False, "commands": {"unlock": None}})
    controller = TerminalController(
        Settings(base_dir=tmp_path),
        profile,
        EventBus(tmp_path / "events.jsonl"),
        MediaHub(),
    )
    with pytest.raises(RuntimeError, match="not verified"):
        asyncio.run(controller.unlock("test"))
    assert controller.last_unlock_at == 0


def test_default_profile_contains_no_active_control_payloads():
    payload = json.loads(open("protocol_profile.json", encoding="utf-8").read())
    assert payload["verified"] is True
    assert payload["commands"]["unlock"].endswith("0003fe")
    assert payload["commands"]["answer"].endswith("0005fe")
    assert payload["commands"]["hangup"].endswith("0006fe")
    assert payload["commands"]["monitor_start"] is None
    assert payload["audio_tx"]["verified"] is False
