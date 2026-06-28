from __future__ import annotations

import asyncio

from aiortc import RTCPeerConnection, RTCSessionDescription

from .events import EventBus
from .media import HaierAudioTrack, HaierVideoTrack, MediaHub


class WebRTCManager:
    def __init__(self, media: MediaHub, events: EventBus, microphone_handler):
        self.media = media
        self.events = events
        self.microphone_handler = microphone_handler
        self.peers: set[RTCPeerConnection] = set()

    async def offer(self, sdp: str, offer_type: str) -> dict[str, str]:
        pc = RTCPeerConnection()
        self.peers.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            await self.events.publish("WEBRTC", "info", "连接状态变化", state=pc.connectionState)
            if pc.connectionState in {"failed", "closed"}:
                await pc.close()
                self.peers.discard(pc)

        @pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                asyncio.create_task(self._consume_microphone(track))

        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=offer_type))
        pc.addTrack(HaierVideoTrack(self.media))
        pc.addTrack(HaierAudioTrack(self.media))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await self.events.publish("WEBRTC", "ok", "浏览器媒体会话已创建")
        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async def _consume_microphone(self, track) -> None:
        await self.events.publish("WEBRTC", "info", "浏览器麦克风轨道已连接")
        try:
            while True:
                frame = await track.recv()
                await self.microphone_handler(frame)
        except Exception as exc:
            await self.events.publish("WEBRTC", "warn", "浏览器麦克风轨道结束", error=str(exc))

    async def close(self) -> None:
        await asyncio.gather(*(pc.close() for pc in tuple(self.peers)), return_exceptions=True)
        self.peers.clear()
