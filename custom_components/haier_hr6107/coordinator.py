from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from logging import getLogger
from urllib.parse import urlencode, urlparse, urlunparse

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HR6107Api
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


class HR6107Coordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, api: HR6107Api) -> None:
        super().__init__(
            hass,
            logger=getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._ws_task: asyncio.Task | None = None
        self._last_call_key: str | None = None
        self._notification_visible = False

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.state()
            await self._handle_state(data)
            return data
        except Exception as exc:
            raise UpdateFailed(f"HR-6107 backend is not available: {exc}") from exc

    async def async_start(self) -> None:
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = self.hass.loop.create_task(self._ws_loop())

    async def async_stop(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._ws_task
            self._ws_task = None

    async def _ws_loop(self) -> None:
        while True:
            try:
                async with self.api._session.ws_connect(
                    self._ws_url(),
                    headers=self.api._headers,
                    heartbeat=30,
                    timeout=15,
                ) as ws:
                    async for msg in ws:
                        if msg.type.name != "TEXT":
                            continue
                        payload = msg.json()
                        if payload.get("type") == "state":
                            data = payload["data"]
                            self.async_set_updated_data(data)
                            await self._handle_state(data)
                        elif payload.get("type") == "event":
                            data = await self.api.state()
                            self.async_set_updated_data(data)
                            await self._handle_state(data)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.debug("HR-6107 WebSocket disconnected: %s", exc)
                await asyncio.sleep(3)

    def _ws_url(self) -> str:
        parsed = urlparse(self.api.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        query = urlencode({"token": self.api.token}) if self.api.token else ""
        return urlunparse(
            parsed._replace(scheme=scheme, path="/ws/events", params="", query=query, fragment="")
        )

    async def _handle_state(self, data: dict) -> None:
        call_state = data.get("call_state")
        if call_state == "RINGING":
            key = str(data.get("last_call") or data.get("call_count") or "ringing")
            if key != self._last_call_key:
                notified = await self._notify_call()
                if notified:
                    self._last_call_key = key
            return

        if self._notification_visible and call_state in {"IDLE", "ENDING", "ERROR"}:
            await self._clear_call_notification()
        if call_state in {"IDLE", "ENDING", "ERROR"}:
            self._last_call_key = None

    async def _notify_call(self) -> bool:
        services = self._mobile_notify_services()
        if not services:
            self.logger.warning("No mobile_app notify services found for HR-6107 call notification")
            return False

        self.logger.info("Sending HR-6107 call notification to: %s", ", ".join(services))
        payload = {
            "title": "门禁来电",
            "message": "501 门口机正在呼叫",
            "data": {
                "tag": "hr6107_call",
                "group": "hr6107",
                "url": "/door-key/door",
                "clickAction": "/door-key/door",
                "presentation_options": ["alert", "sound"],
                "actions": [{"action": "URI", "title": "查看", "uri": "/door-key/door"}],
                "push": {"sound": "default", "interruption-level": "time-sensitive"},
            },
        }
        for service in services:
            await self.hass.services.async_call("notify", service, payload, blocking=False)
        self._notification_visible = True
        return True

    async def _clear_call_notification(self) -> None:
        payload = {"message": "clear_notification", "data": {"tag": "hr6107_call"}}
        for service in self._mobile_notify_services():
            await self.hass.services.async_call("notify", service, payload, blocking=False)
        self._notification_visible = False

    def _mobile_notify_services(self) -> list[str]:
        notify = self.hass.services.async_services().get("notify", {})
        return sorted(service for service in notify if service.startswith("mobile_app_"))
