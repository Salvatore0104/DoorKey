from __future__ import annotations

import asyncio
import audioop
from fractions import Fraction
from typing import Any

import av
from aiortc import AudioStreamTrack, VideoStreamTrack

from .protocol import AudioPacket, VideoPacket


def _replace_latest(queue: asyncio.Queue, item: Any) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(item)


class MediaHub:
    def __init__(self) -> None:
        self.video_queue: asyncio.Queue = asyncio.Queue(maxsize=4)
        self.audio_queue: asyncio.Queue = asyncio.Queue(maxsize=30)
        self.video_decoder = av.CodecContext.create("h264", "r")
        self.video_width = 352
        self.video_height = 240
        self._last_video_frame: Any = None

    async def feed_video(self, datagram: bytes) -> int:
        packet = VideoPacket.parse(datagram)
        decoded = 0
        for encoded in self.video_decoder.parse(packet.annex_b):
            for frame in self.video_decoder.decode(encoded):
                self.video_width = frame.width
                self.video_height = frame.height
                self._last_video_frame = frame
                _replace_latest(self.video_queue, frame)
                decoded += 1
        return decoded

    async def feed_audio(self, datagram: bytes) -> int:
        packet = AudioPacket.parse(datagram)
        pcm = audioop.ulaw2lin(packet.pcmu, 2)
        frame = av.AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
        frame.sample_rate = 8000
        frame.time_base = Fraction(1, 8000)
        frame.planes[0].update(pcm)
        _replace_latest(self.audio_queue, frame)
        return len(packet.pcmu)


class HaierVideoTrack(VideoStreamTrack):
    def __init__(self, hub: MediaHub):
        super().__init__()
        self.hub = hub

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        try:
            frame = await asyncio.wait_for(self.hub.video_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            if self.hub._last_video_frame is not None:
                frame = self.hub._last_video_frame
            else:
                frame = av.VideoFrame(self.hub.video_width, self.hub.video_height, "yuv420p")
                for index, plane in enumerate(frame.planes):
                    plane.update(bytes([16 if index == 0 else 128]) * plane.buffer_size)
        frame.pts = pts
        frame.time_base = time_base
        return frame


class HaierAudioTrack(AudioStreamTrack):
    def __init__(self, hub: MediaHub):
        super().__init__()
        self.hub = hub
        self._pts = 0

    async def recv(self):
        try:
            frame = await asyncio.wait_for(self.hub.audio_queue.get(), timeout=0.15)
        except asyncio.TimeoutError:
            frame = av.AudioFrame(format="s16", layout="mono", samples=512)
            frame.sample_rate = 8000
            frame.time_base = Fraction(1, 8000)
            frame.planes[0].update(bytes(1024))
        frame.pts = self._pts
        frame.time_base = Fraction(1, 8000)
        self._pts += frame.samples
        return frame
