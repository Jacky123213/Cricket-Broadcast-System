from __future__ import annotations

import asyncio
import mimetypes
import math
import threading
from html import escape
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, Settings, get_settings
from .database import Database
from .device_manager import ConnectedDevice, DeviceManager
from .models import CameraRole, DeviceUpdate
from .network import discover_local_ips
from .replay import ReplayStore
from .calibration import Calibration
from .power import SleepGuard
from .scoreboard_state import State as ScoreboardState
from .bluetooth_receiver import start_receiver
from .build_info import APP_VERSION, SCOREBOARD_VERSION, UI_BUILD_ID
from .broadcast_desk import BroadcastDesk


mimetypes.init()
mimetypes.add_type("application/javascript", ".js")

FRONTEND = PROJECT_ROOT / "frontend"
SCOREBOARD_FRONTEND = FRONTEND / "scoreboard"


def create_app(settings: Settings | None = None, scoreboard: ScoreboardState | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_path)
    manager = DeviceManager(database)
    calibration = Calibration(settings.database_path)
    replay = ReplayStore(settings.database_path.parent / "buffer" / "milestone4")
    scoreboard = scoreboard or ScoreboardState(PROJECT_ROOT / "data")
    bluetooth_stop = threading.Event()
    bluetooth_thread: threading.Thread | None = None

    sleep_guard = SleepGuard()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal bluetooth_thread
        database.initialise()
        calibration.initialise()
        replay.initialise()
        async def monitor_connections() -> None:
            while True:
                await asyncio.sleep(settings.heartbeat_interval_seconds)
                await manager.disconnect_stale(settings.device_timeout_seconds)
                async with replay.lock:
                    replay.cleanup()

        sleep_guard.start()
        bluetooth_stop.clear()
        bluetooth_thread = threading.Thread(
            target=start_receiver,
            args=(scoreboard, bluetooth_stop),
            name="scoreboard-bluetooth",
            daemon=True,
        )
        bluetooth_thread.start()
        monitor_task = asyncio.create_task(monitor_connections())
        try:
            yield
        finally:
            await asyncio.to_thread(scoreboard.flush)
            bluetooth_stop.set()
            if bluetooth_thread:
                await asyncio.to_thread(bluetooth_thread.join, 5)
            sleep_guard.stop()
            monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await monitor_task

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.include_router(replay.router())
    desk = BroadcastDesk(replay, manager)
    app.include_router(desk.router())
    app.include_router(calibration.router())
    app.state.settings = settings
    app.state.database = database
    app.state.devices = manager
    app.state.scoreboard = scoreboard
    app.state.broadcast_desk = desk
    app.state.replay_store = replay

    @app.middleware("http")
    async def fresh_ui(request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if any(kind in content_type for kind in ("text/html", "text/css", "javascript", "application/json")):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    app.mount("/static", StaticFiles(directory=FRONTEND / "assets"), name="static")
    app.mount('/broadcast-assets', StaticFiles(directory=FRONTEND/'broadcast'), name='broadcast-assets')
    app.mount(
        "/scoreboard-assets",
        StaticFiles(directory=SCOREBOARD_FRONTEND),
        name="scoreboard-assets",
    )

    def current_server_info() -> dict[str, Any]:
        tls_ready = bool(
            settings.ssl_certfile
            and settings.ssl_keyfile
            and Path(settings.ssl_certfile).exists()
            and Path(settings.ssl_keyfile).exists()
        )
        protocol = "https" if tls_ready else "http"
        ips = discover_local_ips() or ["127.0.0.1"]
        ip = ips[0]
        return {
            "name": settings.app_name,
            "version": app.version,
            "local_ip": ip,
            "port": settings.port,
            "base_url": f"{protocol}://{ip}:{settings.port}",
            "camera_url": f"{protocol}://{ip}:{settings.port}/camera",
            "addresses": [f"{protocol}://{item}:{settings.port}" for item in ips],
            "camera_urls": [f"{protocol}://{item}:{settings.port}/camera" for item in ips],
            "overlay_url": f"{protocol}://{ip}:{settings.port}/overlay",
            "overlay_urls": [f"{protocol}://{item}:{settings.port}/overlay" for item in ips],
            "broadcast_urls": [f"{protocol}://{item}:{settings.port}/broadcast" for item in ips],
            "secure_context": tls_ready,
            "certificate_url": "/local-ca.crt" if tls_ready else None,
            "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
            "sleep_prevention": sleep_guard.status,
        }

    @app.get("/", include_in_schema=False)
    async def index() -> HTMLResponse:
        page = (FRONTEND / "desktop" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(page.replace("__STUDIO_BUILD__", UI_BUILD_ID))

    @app.get("/desktop.css", include_in_schema=False)
    async def desktop_css() -> FileResponse:
        return FileResponse(FRONTEND / "desktop" / "desktop.css")

    @app.get("/desktop.js", include_in_schema=False)
    async def desktop_js() -> FileResponse:
        return FileResponse(FRONTEND / "desktop" / "desktop.js")

    @app.get("/hardware", include_in_schema=False)
    async def hardware_guide() -> FileResponse:
        return FileResponse(FRONTEND / "desktop" / "hardware.html")

    @app.get("/broadcast", include_in_schema=False)
    async def broadcast_output() -> FileResponse:
        return FileResponse(FRONTEND / "broadcast" / "index.html")

    @app.get('/match-day', include_in_schema=False)
    async def match_day():
        return FileResponse(FRONTEND / 'match-day' / 'index.html')

    @app.get('/reliability-checklist', include_in_schema=False)
    async def reliability_checklist(download: bool = False):
        path = PROJECT_ROOT / 'RELIABILITY_TEST_CHECKLIST.md'
        if download:
            return FileResponse(path, media_type='text/markdown', filename=path.name)
        content = escape(path.read_text(encoding='utf-8'))
        return HTMLResponse('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Reliability test checklist · Cricket Broadcast System</title>'
            '<link rel="stylesheet" href="/static/app-theme.css?v=1.3.0">'
            '<style>body{margin:24px auto;padding:0 20px;max-width:1000px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 ui-monospace,monospace}'
            'nav{display:flex;gap:20px}@media print{nav{display:none}body,pre{background:white!important;color:black!important}}</style>'
            '</head><body class="app-ui"><nav><a href="/match-day">Back to Match Day</a>'
            '<a href="/reliability-checklist?download=true">Save checklist</a></nav>'
            f'<pre>{content}</pre></body></html>')

    app.mount('/match-day-assets', StaticFiles(directory=FRONTEND / 'match-day'), name='match-day-assets')

    @app.get("/broadcast.css", include_in_schema=False)
    async def broadcast_css() -> FileResponse:
        return FileResponse(FRONTEND / "broadcast" / "broadcast.css")

    @app.get("/broadcast.js", include_in_schema=False)
    async def broadcast_js() -> FileResponse:
        return FileResponse(FRONTEND / "broadcast" / "broadcast.js")

    @app.get("/camera", include_in_schema=False)
    async def camera_page() -> FileResponse:
        return FileResponse(FRONTEND / "camera" / "index.html")

    @app.get("/umpire", include_in_schema=False)
    async def umpire_page() -> HTMLResponse:
        info = current_server_info()
        links = "".join(
            f'<a class="server-address" href="{escape(url)}" target="_blank" '
            f'rel="noopener">{"Camera" if index == 0 else "Alternative"}: '
            f'{escape(url)}</a>'
            for index, url in enumerate(info["camera_urls"])
        )
        page = (FRONTEND / "umpire" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(page.replace("<!-- CAMERA_URLS -->", links))

    @app.get("/scoreboard", include_in_schema=False)
    async def scoreboard_page() -> FileResponse:
        return FileResponse(SCOREBOARD_FRONTEND / "control.html")

    @app.get("/overlay", include_in_schema=False)
    async def scoreboard_overlay() -> FileResponse:
        return FileResponse(SCOREBOARD_FRONTEND / "overlay.html")

    @app.get("/style.css", include_in_schema=False)
    async def scoreboard_css() -> FileResponse:
        return FileResponse(SCOREBOARD_FRONTEND / "style.css")

    @app.get("/control.js", include_in_schema=False)
    async def scoreboard_control_js() -> FileResponse:
        return FileResponse(SCOREBOARD_FRONTEND / "control.js")

    @app.get("/overlay.js", include_in_schema=False)
    async def scoreboard_overlay_js() -> FileResponse:
        return FileResponse(SCOREBOARD_FRONTEND / "overlay.js")

    @app.get("/api/scoreboard/state")
    async def scoreboard_state() -> dict[str, Any]:
        return await asyncio.to_thread(scoreboard.snapshot)

    @app.get("/api/state", include_in_schema=False)
    async def scoreboard_state_compat() -> dict[str, Any]:
        return await scoreboard_state()

    @app.post("/api/scoreboard/settings")
    async def scoreboard_settings(changes: dict[str, Any]) -> dict[str, bool]:
        try:
            await asyncio.to_thread(scoreboard.save, changes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.get('/api/broadcast/branding')
    async def broadcast_branding() -> dict[str, Any]:
        return await asyncio.to_thread(scoreboard.branding_snapshot)

    @app.post('/api/broadcast/branding')
    async def save_broadcast_branding(changes: dict[str, Any]) -> dict[str, bool]:
        try:
            await asyncio.to_thread(scoreboard.save_branding, changes)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, 'Could not save broadcast logo. Check the Studio data folder.') from exc
        return {'ok': True}

    @app.get('/api/scoreboard/program-state')
    async def program_state(at: float):
        now = time.time()
        if not math.isfinite(at) or not now-35 <= at <= now+1:
            raise HTTPException(422, 'Choose a recent playout time')
        return await asyncio.to_thread(scoreboard.program_snapshot, min(at,now))

    @app.post("/api/settings", include_in_schema=False)
    async def scoreboard_settings_compat(changes: dict[str, Any]) -> dict[str, bool]:
        return await scoreboard_settings(changes)

    @app.post("/api/scoreboard/reset")
    async def scoreboard_reset() -> dict[str, bool]:
        await asyncio.to_thread(scoreboard.reset)
        return {"ok": True}

    @app.post("/api/reset", include_in_schema=False)
    async def scoreboard_reset_compat() -> dict[str, bool]:
        return await scoreboard_reset()

    @app.post("/api/scoreboard/broadcast/settings")
    async def broadcast_settings(changes: dict[str, Any]) -> dict[str, bool]:
        try:
            await asyncio.to_thread(scoreboard.broadcast_settings, changes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/scoreboard/broadcast/action")
    async def broadcast_action(command: dict[str, Any]) -> dict[str, bool]:
        try:
            await asyncio.to_thread(scoreboard.broadcast_action, command)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/scoreboard/broadcast/stats")
    async def broadcast_stats(changes: dict[str, Any]) -> dict[str, bool]:
        try:
            await asyncio.to_thread(scoreboard.broadcast_stats, changes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    @app.get("/api/app-status")
    async def app_status() -> dict[str, Any]:
        info = current_server_info()
        snapshot = scoreboard.snapshot()
        return {
            "status": "ok",
            "version": app.version,
            "drs_version": "0.15.2",
            "scoreboard_version": SCOREBOARD_VERSION,
            "ui_build": UI_BUILD_ID,
            "connected_cameras": len(manager.connected_snapshot()),
            "bluetooth_status": snapshot["status"],
            "score_packets": snapshot["packet_count"],
            "addresses": info["addresses"],
            "camera_urls": info["camera_urls"],
            "umpire_urls": [f"{url}/umpire" for url in info["addresses"]],
            "overlay_url": info["overlay_url"],
            "overlay_urls": info["overlay_urls"],
            "broadcast_urls": info["broadcast_urls"],
            "certificate_url": info["certificate_url"],
            "secure_context": info["secure_context"],
            "sleep_prevention": info["sleep_prevention"],
        }

    @app.get('/api/camera-qr')
    async def camera_qr(index: int = 0):
        import qrcode
        import qrcode.image.svg
        urls = current_server_info()['camera_urls']
        if not 0 <= index < len(urls): raise HTTPException(404, 'Camera address not found')
        qr = qrcode.QRCode(border=4, box_size=8)
        qr.add_data(urls[index]); qr.make(fit=True)
        return Response(qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage).to_string(), media_type='image/svg+xml', headers={'Cache-Control':'no-store'})

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/local-ca.crt", include_in_schema=False)
    async def local_ca_certificate() -> FileResponse:
        certificate = PROJECT_ROOT / "certs" / "rootCA.crt"
        if not certificate.exists():
            raise HTTPException(status_code=404, detail="Local certificate has not been generated")
        return FileResponse(
            certificate,
            media_type="application/x-x509-ca-cert",
            filename="Backyard-DRS-Local-CA.crt",
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": app.version,
            "server_time_ms": int(time.time() * 1000),
            "connected_cameras": len(manager.connected_snapshot()),
        }

    @app.get("/api/server-info")
    async def server_info() -> dict[str, Any]:
        return current_server_info()

    @app.get("/api/devices")
    async def devices() -> dict[str, Any]:
        connected = {item["device_id"]: item for item in manager.connected_snapshot()}
        known = []
        for saved in await asyncio.to_thread(database.list_known_devices):
            live = connected.get(saved["device_id"])
            known.append(live or {**saved, "status": "offline", "remote_address": None})
        return {"devices": known, "server_time_ms": int(time.time() * 1000)}

    @app.patch("/api/devices/{device_id}")
    async def update_device(device_id: str, update: DeviceUpdate) -> dict[str, str]:
        if not await manager.update_device(device_id, update.name, update.role.value):
            raise HTTPException(status_code=404, detail="Device not found")
        return {"status": "updated"}

    @app.delete("/api/devices/{device_id}/connection")
    async def disconnect_device(device_id: str) -> dict[str, str]:
        if not await manager.disconnect_device(device_id):
            raise HTTPException(status_code=404, detail="Device is not connected")
        return {"status": "disconnecting"}

    @app.websocket("/ws/camera")
    async def camera_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        device_id: str | None = None
        try:
            registration = await websocket.receive_json()
            if registration.get("type") != "register":
                await websocket.close(code=4400, reason="Registration required")
                return
            device_id = str(registration.get("device_id", ""))[:80]
            name = str(registration.get("name", ""))[:48].strip()
            role = str(registration.get("role", ""))
            if not device_id or not name or role not in {item.value for item in CameraRole}:
                await websocket.close(code=4400, reason="Invalid registration")
                return
            device = ConnectedDevice(
                device_id=device_id,
                name=name,
                role=role,
                websocket=websocket,
                remote_address=websocket.client.host if websocket.client else "unknown",
                connected_at_ms=int(time.time() * 1000),
                settings=registration.get("settings", {}),
                capabilities=registration.get("capabilities", {}),
                battery=manager.battery_status(registration.get("battery")),
            )
            await manager.register_camera(device)
            await websocket.send_json(
                {
                    "type": "registered",
                    "device_id": device_id,
                    "server_time_ms": int(time.time() * 1000),
                    "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
                }
            )
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "heartbeat":
                    await manager.heartbeat(device_id, websocket)
                    if "battery" in message:
                        await manager.update_battery(device_id, websocket, message["battery"])
                    await websocket.send_json(
                        {
                            "type": "heartbeat_ack",
                            "sequence": message.get("sequence"),
                            "client_time_ms": message.get("client_time_ms"),
                            "server_time_ms": int(time.time() * 1000),
                        }
                    )
                elif message.get("type") == "webrtc_signal":
                    console_id = str(message.get("console_id", ""))[:80]
                    signal = message.get("signal")
                    if console_id and isinstance(signal, dict):
                        await manager.signal_umpire(
                            console_id,
                            {
                                "type": "webrtc_signal",
                                "device_id": device_id,
                                "signal": signal,
                            },
                        )
                elif message.get("type") == "media_changed" and isinstance(message.get("microphone"), bool):
                    await manager.update_media(device_id, websocket, message["microphone"])
        except WebSocketDisconnect:
            pass
        except Exception:
            try:
                await websocket.close(code=1011, reason="Connection error")
            except RuntimeError:
                pass
        finally:
            if device_id:
                await manager.remove_camera(device_id, websocket)

    @app.websocket("/ws/umpire")
    async def umpire_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        console_id = str(websocket.query_params.get("console_id", ""))[:80]
        if not console_id:
            await websocket.close(code=4400, reason="Console ID required")
            return
        await manager.add_umpire(console_id, websocket)
        try:
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "ping":
                    await websocket.send_json(
                        {"type": "pong", "server_time_ms": int(time.time() * 1000)}
                    )
                elif message.get("type") == "webrtc_signal":
                    device_id = str(message.get("device_id", ""))[:80]
                    signal = message.get("signal")
                    if device_id and isinstance(signal, dict):
                        delivered = await manager.signal_camera(
                            device_id,
                            {
                                "type": "webrtc_signal",
                                "console_id": console_id,
                                "signal": signal,
                            },
                        )
                        if not delivered:
                            await websocket.send_json(
                                {
                                    "type": "webrtc_error",
                                    "device_id": device_id,
                                    "message": "Camera disconnected before signaling completed",
                                }
                            )
        except WebSocketDisconnect:
            pass
        finally:
            await manager.remove_umpire(console_id, websocket)

    return app


app = create_app()
