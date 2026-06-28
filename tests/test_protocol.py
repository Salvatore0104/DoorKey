import json

import pytest

from hr6107.protocol import (
    AudioPacket,
    CALL_END_HEX,
    CALL_START_HEX,
    ControlFrame,
    ProtocolProfile,
    VideoPacket,
)


def test_known_call_frames():
    start = ControlFrame.parse(bytes.fromhex(CALL_START_HEX))
    end = ControlFrame.parse(bytes.fromhex(CALL_END_HEX))
    assert start.kind == "call_start"
    assert start.declared_length == 30
    assert end.kind == "call_end"
    assert end.declared_length == 26


@pytest.mark.parametrize("raw", [b"", b"\xff\xfe\x00\x00", b"\xff\xff\x00\x04\x01"])
def test_control_frame_rejects_invalid_data(raw):
    with pytest.raises(ValueError):
        ControlFrame.parse(raw)


def test_media_private_headers():
    video = VideoPacket.parse(bytes(range(25)) + b"\x00\x00\x00\x01\x67")
    audio = AudioPacket.parse(bytes(range(20)) + b"\xff" * 512)
    assert len(video.header) == 25
    assert video.annex_b.startswith(b"\x00\x00\x00\x01")
    assert len(audio.header) == 20
    assert len(audio.pcmu) == 512


def test_unverified_profile_never_returns_command(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps({"verified": False, "commands": {"unlock": CALL_START_HEX}}),
        encoding="utf-8",
    )
    profile = ProtocolProfile.load(path)
    assert not profile.command_available("unlock")
    with pytest.raises(RuntimeError, match="not verified"):
        profile.command("unlock")


def test_verified_501_commands_are_well_formed():
    profile = ProtocolProfile.load(__import__("pathlib").Path("protocol_profile.json"))
    for name in ("call_ack", "answer", "hangup", "unlock"):
        frame = ControlFrame.parse(profile.command(name))
        assert frame.kind == "unknown"
        assert profile.command(name)[21:23] == bytes.fromhex("0501")
        assert profile.command(name)[23:27] == bytes([172, 30, 2, 47])
