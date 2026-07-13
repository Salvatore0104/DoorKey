from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN


def register_views(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("views_registered"):
        return
    hass.http.register_view(HR6107StateView())
    hass.http.register_view(HR6107ActionView("answer", "/api/haier_hr6107/call/answer"))
    hass.http.register_view(HR6107ActionView("hangup", "/api/haier_hr6107/call/hangup"))
    hass.http.register_view(HR6107ActionView("reject", "/api/haier_hr6107/call/reject"))
    hass.http.register_view(HR6107ActionView("unlock", "/api/haier_hr6107/unlock"))
    hass.http.register_view(HR6107WebRTCOfferView())
    hass.http.register_view(HR6107CardView())
    data["views_registered"] = True


def first_coordinator(hass: HomeAssistant):
    coordinators = hass.data.get(DOMAIN, {}).get("coordinators", {})
    if not coordinators:
        raise web.HTTPNotFound(text="HR-6107 integration is not configured")
    return next(iter(coordinators.values()))


class HR6107StateView(HomeAssistantView):
    url = "/api/haier_hr6107/state"
    name = "api:haier_hr6107:state"

    async def get(self, request):
        coordinator = first_coordinator(request.app["hass"])
        return web.json_response(coordinator.data or await coordinator.api.state())


class HR6107ActionView(HomeAssistantView):
    name = "api:haier_hr6107:action"

    def __init__(self, action: str, url: str) -> None:
        self.action = action
        self.url = url
        self.name = f"api:haier_hr6107:{action}"

    async def post(self, request):
        coordinator = first_coordinator(request.app["hass"])
        method = getattr(coordinator.api, self.action)
        result = await method()
        await coordinator.async_request_refresh()
        return web.json_response({"ok": True, "result": result})


class HR6107WebRTCOfferView(HomeAssistantView):
    url = "/api/haier_hr6107/webrtc/offer"
    name = "api:haier_hr6107:webrtc_offer"

    async def post(self, request):
        body = await request.json()
        coordinator = first_coordinator(request.app["hass"])
        result = await coordinator.api.webrtc_offer(body["sdp"], body.get("type", "offer"))
        return web.json_response(result)


class HR6107CardView(HomeAssistantView):
    url = "/haier_hr6107/card.js"
    name = "haier_hr6107:card"
    requires_auth = False

    async def get(self, request):
        path = request.app["hass"].config.path("custom_components/haier_hr6107/haier_hr6107_card.js")
        return web.FileResponse(path)
