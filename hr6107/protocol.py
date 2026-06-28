from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CALL_START_HEX = "ffff001e00000000000000000000030100010001020001ac1e0224000101010101fe"
CALL_END_HEX = "ffff001a00000000000000000000030100010001020001ac1e02240006fe"


@dataclass(frozen=True)
class ControlFrame:
    raw: bytes
    declared_length: int
    kind: str

    @classmethod
    def parse(cls, raw: bytes) -> "ControlFrame":
        if len(raw) < 4 or raw[:2] != b"\xff\xff":
            raise ValueError("not an HR-6107 control frame")
        declared = int.from_bytes(raw[2:4], "big")
        if len(raw) != declared + 4:
            raise ValueError(f"length mismatch: declared={declared}, actual={len(raw) - 4}")
        hex_value = raw.hex()
        if hex_value == CALL_START_HEX:
            kind = "call_start"
        elif hex_value == CALL_END_HEX:
            kind = "call_end"
        else:
            kind = "unknown"
        return cls(raw=raw, declared_length=declared, kind=kind)


@dataclass(frozen=True)
class VideoPacket:
    header: bytes
    annex_b: bytes

    @classmethod
    def parse(cls, datagram: bytes) -> "VideoPacket":
        if len(datagram) <= 25:
            raise ValueError("video datagram is shorter than the 25-byte private header")
        return cls(datagram[:25], datagram[25:])


@dataclass(frozen=True)
class AudioPacket:
    header: bytes
    pcmu: bytes

    @classmethod
    def parse(cls, datagram: bytes) -> "AudioPacket":
        if len(datagram) <= 20:
            raise ValueError("audio datagram is shorter than the 20-byte private header")
        return cls(datagram[:20], datagram[20:])


class ProtocolProfile:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    @classmethod
    def load(cls, path: Path) -> "ProtocolProfile":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @property
    def verified(self) -> bool:
        return bool(self.payload.get("verified"))

    def command(self, name: str) -> bytes:
        value = self.payload.get("commands", {}).get(name)
        if not self.verified or not value:
            raise RuntimeError(f"command '{name}' is not verified")
        raw = bytes.fromhex(value)
        ControlFrame.parse(raw)
        return raw

    def command_available(self, name: str) -> bool:
        return self.verified and bool(self.payload.get("commands", {}).get(name))

    @property
    def audio_tx_verified(self) -> bool:
        audio = self.payload.get("audio_tx", {})
        template = audio.get("header_template_hex")
        if not (self.verified and audio.get("verified") and template):
            return False
        try:
            return len(bytes.fromhex(template)) == 20
        except ValueError:
            return False

    def audio_tx_config(self) -> dict[str, Any]:
        if not self.audio_tx_verified:
            raise RuntimeError("audio TX profile is not verified")
        audio = self.payload["audio_tx"]
        return {
            "header": bytes.fromhex(audio["header_template_hex"]),
            "sequence_offset": audio.get("sequence_offset"),
            "sequence_size": int(audio.get("sequence_size", 2)),
            "sequence_byteorder": audio.get("sequence_byteorder", "big"),
            "packet_samples": int(audio.get("packet_samples", 512)),
            "sample_rate": int(audio.get("sample_rate", 8000)),
            "codec": audio.get("codec", "pcmu"),
        }

    def public_summary(self) -> dict[str, Any]:
        commands = self.payload.get("commands", {})
        return {
            "version": self.payload.get("version", 1),
            "verified": self.verified,
            "source": self.payload.get("source", "unknown"),
            "commands": {name: self.command_available(name) for name in commands},
            "audio_tx_verified": self.audio_tx_verified,
        }
