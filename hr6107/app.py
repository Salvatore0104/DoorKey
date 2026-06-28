from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import Settings, load_settings
from .controller import TerminalController
from .events import EventBus
from .media import MediaHub
from .protocol import ProtocolProfile
from .webrtc import WebRTCManager


class LoginRequest(BaseModel):
    token: str


class OfferRequest(BaseModel):
    sdp: str
    type: str = "offer"


settings: Settings = load_settings()
api_token = settings.api_token() if settings.auth_required else ""
events = EventBus(settings.log_path)
profile = ProtocolProfile.load(settings.profile_path)
media = MediaHub()
controller = TerminalController(settings, profile, events, media)
webrtc = WebRTCManager(media, events, controller.microphone_frame)


def valid_token(value: str | None) -> bool:
    return bool(value) and hmac.compare_digest(value, api_token)


async def require_auth(
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
    hr6107_session: str | None = Cookie(default=None),
) -> str:
    if not settings.auth_required:
        return "local-no-auth"
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    supplied = bearer or x_api_token or hr6107_session
    if not valid_token(supplied):
        raise HTTPException(status_code=401, detail="需要有效的HR-6107访问令牌")
    return supplied


@asynccontextmanager
async def lifespan(app: FastAPI):
    await controller.start()
    yield
    await webrtc.close()
    await controller.stop()


app = FastAPI(title="HR-6107 501 Software Terminal", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse(settings.base_dir / "haier_dashboard_v2.html", media_type="text/html")


@app.get("/health")
async def health():
    return {"ok": True, "listener": controller.started}


@app.get("/api/state")
async def get_state():
    return controller.snapshot()


@app.get("/api/logs")
async def get_logs(after: int = 0):
    return {"events": await events.since(after)}


@app.get("/api/profile")
async def get_profile():
    return profile.public_summary()


@app.get("/api/auth")
async def auth_status(_: str = Depends(require_auth)):
    return {"ok": True}


@app.post("/api/login")
async def login(body: LoginRequest, response: Response):
    if not settings.auth_required:
        return {"ok": True, "auth_required": False}
    if not valid_token(body.token):
        raise HTTPException(status_code=401, detail="令牌错误")
    response.set_cookie(
        "hr6107_session",
        body.token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=86400,
    )
    await events.publish("AUTH", "ok", "网页会话认证成功")
    return {"ok": True}


@app.post("/api/call/answer")
async def answer(_: str = Depends(require_auth)):
    try:
        return {"ok": True, "result": await controller.answer()}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/call/hangup")
async def hangup(_: str = Depends(require_auth)):
    try:
        return {"ok": True, "result": await controller.hangup()}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/call/reject")
async def reject(_: str = Depends(require_auth)):
    try:
        return {"ok": True, "result": await controller.reject()}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/unlock")
async def unlock(request: Request, _: str = Depends(require_auth)):
    source = request.client.host if request.client else "unknown"
    try:
        return {"ok": True, "result": await controller.unlock(source)}
    except RuntimeError as exc:
        await events.publish("TX", "blocked", "开门请求未发送", source=source, error=str(exc))
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/webrtc/offer")
async def offer(body: OfferRequest, _: str = Depends(require_auth)):
    return await webrtc.offer(body.sdp, body.type)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.cookies.get("hr6107_session")
    if settings.auth_required and not valid_token(token):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    queue = events.subscribe()
    try:
        await websocket.send_json({"type": "state", "data": controller.snapshot()})
        while True:
            event = await queue.get()
            await websocket.send_json({"type": "event", "data": event})
    except WebSocketDisconnect:
        pass
    finally:
        events.unsubscribe(queue)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=settings.web_host, port=settings.web_port, log_level="info")
