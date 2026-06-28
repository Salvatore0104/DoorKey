from __future__ import annotations

import asyncio
import audioop
import time
from contextlib import suppress

import av

from .config import Settings
from .events import EventBus
from .media import MediaHub
from .protocol import ControlFrame, ProtocolProfile
from .state import CallState, TerminalState


class MediaProtocol(asyncio.DatagramProtocol):
    def __init__(self, controller: "TerminalController", kind: str):
        self.controller = controller
        self.kind = kind

    def datagram_received(self, data: bytes, addr):
        if addr[0] != self.controller.settings.door_ip:
            return
        asyncio.create_task(self.controller.handle_media(self.kind, data, addr))

    def error_received(self, exc):
        asyncio.create_task(self.controller.events.publish("SYS", "error", f"{self.kind} UDP错误", error=str(exc)))


class TerminalController:
    def __init__(self, settings: Settings, profile: ProtocolProfile, events: EventBus, media: MediaHub):
        self.settings = settings
        self.profile = profile
        self.events = events
        self.media = media
        self.state = TerminalState()
        self.control_server: asyncio.Server | None = None
        self.transports: list[asyncio.DatagramTransport] = []
        self.media_transports: dict[str, asyncio.DatagramTransport] = {}
        self.ring_timer: asyncio.Task | None = None
        self.last_unlock_at = 0.0
        self.started = False
        self._audio_resampler = av.AudioResampler(format="s16", layout="mono", rate=8000)
        self._audio_tx_buffer = bytearray()
        self._audio_tx_sequence = 0
        self._last_video_log_at = 0.0

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.control_server = await asyncio.start_server(
            self.handle_control,
            host=self.settings.device_ip,
            port=self.settings.control_port,
        )
        for port, kind in ((self.settings.audio_port, "audio"), (self.settings.video_port, "video")):
            transport, _ = await loop.create_datagram_endpoint(
                lambda kind=kind: MediaProtocol(self, kind),
                local_addr=(self.settings.device_ip, port),
            )
            self.transports.append(transport)
            self.media_transports[kind] = transport
        self.started = True
        await self.events.publish(
            "SYS",
            "ok",
            "501软件终端监听已启动",
            control=f"{self.settings.device_ip}:{self.settings.control_port}",
            audio=self.settings.audio_port,
            video=self.settings.video_port,
        )

    async def stop(self) -> None:
        if self.ring_timer:
            self.ring_timer.cancel()
        if self.control_server:
            self.control_server.close()
            await self.control_server.wait_closed()
        for transport in self.transports:
            transport.close()
        self.started = False
        await self.events.publish("SYS", "info", "501软件终端监听已停止")

    async def handle_control(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        remote_ip = peer[0] if peer else "unknown"
        if remote_ip != self.settings.door_ip:
            await self.events.publish("RX", "warn", "拒绝非门口机控制连接", remote=remote_ip)
            writer.close()
            await writer.wait_closed()
            return
        try:
            header = await asyncio.wait_for(reader.readexactly(4), timeout=5)
            declared = int.from_bytes(header[2:4], "big")
            if header[:2] != b"\xff\xff" or declared > 4092:
                raise ValueError("invalid HR-6107 control header")
            payload = header + await asyncio.wait_for(reader.readexactly(declared), timeout=5)
            self.state.rx_bytes += len(payload)
            frame = ControlFrame.parse(payload)
            await self.events.publish(
                "RX",
                "call" if frame.kind == "call_start" else "info",
                f"控制报文 {frame.kind}",
                remote=remote_ip,
                bytes=len(payload),
                hex=payload.hex(),
            )
            if frame.kind == "call_start":
                await self.on_ring()
            elif frame.kind == "call_end":
                await self.on_remote_end()
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ValueError) as exc:
            self.state.last_error = str(exc)
            await self.events.publish("RX", "error", "控制报文解析失败", error=str(exc))
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def on_ring(self) -> None:
        if self.state.call_state not in {CallState.IDLE, CallState.ERROR}:
            await self.events.publish("SYS", "warn", "重复来电通知", state=self.state.call_state)
            return
        self.state.ring()
        await self.events.publish("STATE", "call", "501来电", state=self.state.call_state)
        if self.profile.command_available("call_ack"):
            try:
                await self.send_command("call_ack")
                await self.events.publish("TX", "ok", "501来电确认已发送")
            except Exception as exc:
                self.state.last_error = str(exc)
                await self.events.publish("TX", "error", "501来电确认失败", error=str(exc))
        if self.ring_timer:
            self.ring_timer.cancel()
        self.ring_timer = asyncio.create_task(self._ring_timeout())

    async def _ring_timeout(self) -> None:
        await asyncio.sleep(self.settings.ring_timeout_seconds)
        if self.state.call_state == CallState.RINGING:
            self.state.transition(CallState.IDLE)
            await self.events.publish("STATE", "info", "来电超时", state=self.state.call_state)

    async def on_remote_end(self) -> None:
        if self.state.call_state != CallState.IDLE:
            if self.state.call_state not in {CallState.ENDING, CallState.ERROR}:
                self.state.transition(CallState.ENDING)
            self.state.transition(CallState.IDLE)
        await self.events.publish("STATE", "info", "门口机结束会话", state=self.state.call_state)

    async def handle_media(self, kind: str, data: bytes, addr) -> None:
        try:
            if kind == "video":
                self.state.video_packets += 1
                decoded = await self.media.feed_video(data)
                now = time.monotonic()
                if decoded and now - self._last_video_log_at >= 1.0:
                    self._last_video_log_at = now
                    await self.events.publish("RX", "media", "解码视频帧", packets=self.state.video_packets, frames=decoded)
            else:
                self.state.audio_packets += 1
                await self.media.feed_audio(data)
        except Exception as exc:
            self.state.last_error = str(exc)
            await self.events.publish("RX", "error", f"{kind}媒体解析失败", error=str(exc), bytes=len(data))

    async def answer(self) -> dict:
        if self.state.call_state != CallState.RINGING:
            raise RuntimeError("当前没有可接听的来电")
        self.state.transition(CallState.CONNECTING)
        result = await self.send_command("answer")
        self.state.transition(CallState.ACTIVE)
        await self.events.publish("STATE", "ok", "通话已接听", state=self.state.call_state)
        return result

    async def hangup(self) -> dict:
        if self.state.call_state not in {CallState.RINGING, CallState.CONNECTING, CallState.ACTIVE}:
            raise RuntimeError("当前没有可挂断的会话")
        self.state.transition(CallState.ENDING)
        result = await self.send_command("hangup")
        self.state.transition(CallState.IDLE)
        await self.events.publish("STATE", "ok", "会话已挂断", state=self.state.call_state)
        return result

    async def reject(self) -> dict:
        if self.state.call_state != CallState.RINGING:
            raise RuntimeError("当前没有可拒绝的来电")
        self.state.transition(CallState.ENDING)
        result = await self.send_command("reject_or_cancel")
        self.state.transition(CallState.IDLE)
        await self.events.publish("STATE", "ok", "来电已拒绝", state=self.state.call_state)
        return result

    async def unlock(self, source: str) -> dict:
        now = time.monotonic()
        remaining = self.settings.unlock_cooldown_seconds - (now - self.last_unlock_at)
        if remaining > 0:
            raise RuntimeError(f"开门限频中，请等待 {remaining:.1f} 秒")
        result = await self.send_command("unlock")
        self.last_unlock_at = now
        await self.events.publish("TX", "audit", "开门命令已发送", source=source, result=result)
        return result

    async def send_command(self, name: str) -> dict:
        payload = self.profile.command(name)
        await self.events.publish("TX", "info", f"发送控制命令 {name}", bytes=len(payload))
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.settings.door_ip, self.settings.control_port),
            timeout=3,
        )
        try:
            writer.write(payload)
            await writer.drain()
            self.state.tx_bytes += len(payload)
            await self.events.publish("TX", "ok", f"命令 {name} 已完成TCP发送", bytes=len(payload))
            return {"command": name, "sent": len(payload), "tcp_sent": True}
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def microphone_frame(self, frame) -> None:
        if not self.profile.audio_tx_verified:
            return
        config = self.profile.audio_tx_config()
        if config["codec"].lower() != "pcmu" or config["sample_rate"] != 8000:
            raise RuntimeError("only verified PCMU/8000 audio TX profiles are supported")
        for converted in self._audio_resampler.resample(frame):
            self._audio_tx_buffer.extend(bytes(converted.planes[0]))
        chunk_size = config["packet_samples"] * 2
        transport = self.media_transports.get("audio")
        if transport is None:
            return
        while len(self._audio_tx_buffer) >= chunk_size:
            pcm = bytes(self._audio_tx_buffer[:chunk_size])
            del self._audio_tx_buffer[:chunk_size]
            header = bytearray(config["header"])
            offset = config["sequence_offset"]
            if offset is not None:
                size = config["sequence_size"]
                if offset < 0 or offset + size > len(header):
                    raise RuntimeError("audio TX sequence field lies outside the 20-byte header")
                modulo = 1 << (size * 8)
                header[offset : offset + size] = (self._audio_tx_sequence % modulo).to_bytes(
                    size, config["sequence_byteorder"]
                )
            packet = bytes(header) + audioop.lin2ulaw(pcm, 2)
            transport.sendto(packet, (self.settings.door_ip, self.settings.audio_port))
            self._audio_tx_sequence += 1
            self.state.tx_bytes += len(packet)

    def snapshot(self) -> dict:
        result = self.state.snapshot()
        result.update(
            {
                "listener": "online" if self.started else "offline",
                "device_ip": self.settings.device_ip,
                "door_ip": self.settings.door_ip,
                "auth_required": self.settings.auth_required,
                "ports": {
                    "control": self.settings.control_port,
                    "audio": self.settings.audio_port,
                    "video": self.settings.video_port,
                },
                "protocol": self.profile.public_summary(),
                "actions": {
                    "answer": self.profile.command_available("answer"),
                    "hangup": self.profile.command_available("hangup"),
                    "unlock": self.profile.command_available("unlock"),
                    "talk": self.profile.audio_tx_verified,
                },
            }
        )
        return result
