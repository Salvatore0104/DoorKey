from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class CallState(StrEnum):
    IDLE = "IDLE"
    RINGING = "RINGING"
    CONNECTING = "CONNECTING"
    ACTIVE = "ACTIVE"
    ENDING = "ENDING"
    ERROR = "ERROR"


ALLOWED = {
    CallState.IDLE: {CallState.RINGING, CallState.CONNECTING, CallState.ERROR},
    CallState.RINGING: {CallState.CONNECTING, CallState.ENDING, CallState.IDLE, CallState.ERROR},
    CallState.CONNECTING: {CallState.ACTIVE, CallState.ENDING, CallState.ERROR},
    CallState.ACTIVE: {CallState.ENDING, CallState.ERROR},
    CallState.ENDING: {CallState.IDLE, CallState.ERROR},
    CallState.ERROR: {CallState.IDLE, CallState.RINGING},
}


@dataclass
class TerminalState:
    call_state: CallState = CallState.IDLE
    last_call: str | None = None
    call_count: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    video_packets: int = 0
    audio_packets: int = 0
    last_error: str | None = None

    def transition(self, target: CallState) -> None:
        if target == self.call_state:
            return
        if target not in ALLOWED[self.call_state]:
            raise ValueError(f"invalid transition {self.call_state} -> {target}")
        self.call_state = target

    def ring(self) -> None:
        if self.call_state == CallState.ERROR:
            self.call_state = CallState.IDLE
        self.transition(CallState.RINGING)
        self.call_count += 1
        self.last_call = datetime.now().isoformat(timespec="seconds")

    def snapshot(self) -> dict:
        return {
            "call_state": self.call_state,
            "last_call": self.last_call,
            "call_count": self.call_count,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
            "video_packets": self.video_packets,
            "audio_packets": self.audio_packets,
            "last_error": self.last_error,
        }
