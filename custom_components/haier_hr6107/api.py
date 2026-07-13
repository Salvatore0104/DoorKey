from __future__ import annotations

from typing import Any

from aiohttp import ClientResponseError, ClientSession, ClientTimeout


class HR6107Api:
    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = ClientTimeout(total=5)

    async def state(self) -> dict[str, Any]:
        async with self._session.get(
            f"{self.base_url}/api/state", headers=self._headers, timeout=self._timeout
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def unlock(self) -> dict[str, Any]:
        async with self._session.post(
            f"{self.base_url}/api/unlock", headers=self._headers, timeout=self._timeout
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def answer(self) -> dict[str, Any]:
        return await self._post("/api/call/answer")

    async def hangup(self) -> dict[str, Any]:
        return await self._post("/api/call/hangup")

    async def reject(self) -> dict[str, Any]:
        return await self._post("/api/call/reject")

    async def webrtc_offer(self, sdp: str, offer_type: str = "offer") -> dict[str, Any]:
        async with self._session.post(
            f"{self.base_url}/api/webrtc/offer",
            headers=self._headers,
            json={"sdp": sdp, "type": offer_type},
            timeout=ClientTimeout(total=15),
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def _post(self, path: str) -> dict[str, Any]:
        async with self._session.post(
            f"{self.base_url}{path}", headers=self._headers, json={}, timeout=self._timeout
        ) as response:
            response.raise_for_status()
            return await response.json()


async def validate_api(api: HR6107Api) -> dict[str, Any]:
    try:
        return await api.state()
    except ClientResponseError:
        raise
