"""Installed-PC joining, separate from the existing trusted-LAN browser workflow.

Discovery is a short local UDP exchange, never an address-range scan. A discovery
reply is a hint, not an identity: TLS must verify against a user-selected public
CA before any connection code or saved credential is sent. Existing iPad/camera/
OBS URLs are intentionally unchanged; this is not Internet-facing authentication.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import secrets
import socket
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from .build_info import APP_VERSION
from .install_support import write_json_atomic

DISCOVERY_PORT = 52365
DISCOVERY_MAGIC = "CBS-STUDIO-1"
COOKIE = "cbs_studio_client"
LOCAL_RANGES = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8"))


def local_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        return isinstance(ip, ipaddress.IPv4Address) and any(ip in network for network in LOCAL_RANGES)
    except ValueError:
        return False


def clean_name(value: str) -> str:
    return " ".join(str(value).split())[:80] or "Studio PC"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class NetworkSettings(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    allow_join: bool


class PairRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)


class TicketRequest(BaseModel):
    ticket: str = Field(min_length=20, max_length=128)


class StudioNetwork:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_root / "studio-network.json"
        if self.path.exists():
            self.state = json.loads(self.path.read_text("utf-8"))
            if not isinstance(self.state, dict) or not isinstance(self.state.get("clients"), dict):
                raise ValueError("Saved studio connections are damaged. Nothing has been reset.")
            uuid.UUID(self.state["id"])
            if not isinstance(self.state.get("name"), str) or not isinstance(self.state.get("allow_join"), bool) or len(self.state["clients"]) > 32:
                raise ValueError("Saved studio connections are damaged. Nothing has been reset.")
            for key, client in self.state["clients"].items():
                if len(key) != 64 or any(c not in "0123456789abcdef" for c in key) or not isinstance(client, dict) or not isinstance(client.get("name"), str):
                    raise ValueError("Saved PC approval is damaged. Nothing has been reset.")
        else:
            self.state = {"id": str(uuid.uuid4()), "name": clean_name(socket.gethostname()),
                          "allow_join": False, "clients": {}}
        self.lock = threading.RLock()
        self.code = ""
        self.code_until = 0.0
        self.tickets = {}
        self.attempts = defaultdict(deque)
        self.stop_event = threading.Event()
        self.thread = None
        self.discovery_status = "Off"

    @property
    def secure(self):
        return bool(self.settings.ssl_certfile and self.settings.ssl_keyfile
                    and Path(self.settings.ssl_certfile).is_file() and Path(self.settings.ssl_keyfile).is_file())

    def public(self):
        with self.lock:
            cert = self.settings.certificate_dir / "rootCA.crt"
            return {"protocol": DISCOVERY_MAGIC, "id": self.state["id"], "name": self.state["name"],
                    "version": APP_VERSION, "secure": self.secure,
                    "allow_join": self.state["allow_join"],
                    "ca_sha256": hashlib.sha256(cert.read_bytes()).hexdigest().upper() if cert.exists() else None}

    def save(self):
        write_json_atomic(self.path, self.state)

    def start(self):
        with self.lock:
            self.save()
            if self.state["allow_join"]:
                self.rotate_code()
        # Starting a second test/host never takes ownership of another listener.
        # Address-in-use is reported; manual HTTPS joining remains available.
        if self.secure and self.settings.host not in ("127.0.0.1", "localhost"):
            self.thread = threading.Thread(target=self._serve_discovery, daemon=True, name="studio-discovery")
            self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def rotate_code(self):
        with self.lock:
            self.code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
            self.code_until = time.monotonic() + 20 * 60

    def configure(self, name: str, allow: bool):
        with self.lock:
            self.state.update(name=clean_name(name), allow_join=allow)
            if allow:
                self.rotate_code()
            else:
                self.code = ""
                self.code_until = 0
            self.save()

    def operator_snapshot(self):
        with self.lock:
            return {**self.public(), "code": self.code if time.monotonic() < self.code_until else "",
                    "code_seconds": max(0, int(self.code_until - time.monotonic())),
                    "discovery": self.discovery_status,
                    "clients": [{"id": identifier, "name": item["name"]} for identifier, item in self.state["clients"].items()]}

    def issue_ticket(self, token: str):
        with self.lock:
            identifier = digest(token)
            if identifier not in self.state["clients"]:
                raise HTTPException(401, "This PC is not approved, or its approval was removed. Connect again with a new code.")
            now = time.monotonic()
            self.tickets = {key: value for key, value in self.tickets.items() if value[1] > now}
            if len(self.tickets) >= 100:
                raise HTTPException(429, "Too many pending connections. Wait two minutes.")
            ticket = secrets.token_urlsafe(32)
            self.tickets[digest(ticket)] = (token, now + 120)
            return {"ticket": ticket, "studio": self.public()}

    def pair(self, code: str, name: str, address: str):
        with self.lock:
            now = time.monotonic()
            # Bound both per-address and total attempts; no unbounded LAN state.
            self.attempts = defaultdict(deque, {a: hits for a, hits in self.attempts.items() if hits and hits[-1] >= now - 60})
            if address not in self.attempts and len(self.attempts) >= 128:
                raise HTTPException(429, "Too many connection attempts. Try again later.")
            attempts = self.attempts[address]
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 5:
                raise HTTPException(429, "Too many codes tried. Wait one minute.")
            attempts.append(now)
            if not self.secure or not self.state["allow_join"]:
                raise HTTPException(403, "The host must enable connections in Settings on its own PC.")
            if now >= self.code_until or not self.code or not secrets.compare_digest(code.strip().upper(), self.code):
                raise HTTPException(403, "That connection code is incorrect or expired. Ask the host for a fresh code.")
            if len(self.state["clients"]) >= 32:
                raise HTTPException(409, "Remove an old approved PC in host Settings before adding another.")
            token = secrets.token_urlsafe(32)
            self.state["clients"][digest(token)] = {"name": clean_name(name)}
            self.save()
            # Each code approves one PC. A fresh code is displayed for the next.
            self.rotate_code()
            return {"token": token, **self.issue_ticket(token)}

    def consume_ticket(self, ticket: str):
        with self.lock:
            item = self.tickets.pop(digest(ticket), None)
            if not item or item[1] <= time.monotonic() or not self.valid_token(item[0]):
                raise HTTPException(401, "This connection link expired or was already used. Reopen Connect to a studio.")
            return item[0]

    def valid_token(self, token: str):
        with self.lock:
            return len(token) <= 128 and digest(token) in self.state["clients"]

    def revoke(self, identifier: str):
        with self.lock:
            self.state["clients"].pop(identifier, None)
            self.save()

    def _serve_discovery(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind((self.settings.host, DISCOVERY_PORT))
                sock.settimeout(.5)
                self.discovery_status = "Ready · UDP 52365 (Private network only)"
                last_reply = {}
                while not self.stop_event.is_set():
                    try:
                        data, (address, port) = sock.recvfrom(2048)
                    except socket.timeout:
                        continue
                    if not self.state["allow_join"] or not local_ip(address):
                        continue
                    try:
                        query = json.loads(data)
                        nonce = query.get("nonce", "")
                        if query.get("find") != DISCOVERY_MAGIC or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
                            continue
                        now = time.monotonic()
                        if now - last_reply.get(address, 0) < .2:
                            continue
                        last_reply = {a: t for a, t in last_reply.items() if now - t < 10}
                        last_reply[address] = now
                        info = self.public()
                        reply = {key: info[key] for key in ("id", "name", "version")}
                        reply.update(found=DISCOVERY_MAGIC, nonce=nonce, port=self.settings.port)
                        sock.sendto(json.dumps(reply).encode(), (address, port))
                    except (ValueError, TypeError, AttributeError, OSError):
                        continue
        except OSError as exc:
            self.discovery_status = "Discovery unavailable · use manual address"
            logging.warning("Nearby studio discovery unavailable: %s", exc)

    def router(self):
        router = APIRouter(prefix="/api/studio-network")

        def local_operator(request):
            # Existing browser APIs remain trusted-LAN. New connection approvals
            # are restricted to the actual host PC, including anti-CSRF checks.
            if not request.client or request.client.host not in ("127.0.0.1", "::1", "testclient") or request.cookies.get(COOKIE):
                raise HTTPException(403, "Approve or remove installed PCs in Settings on the host PC.")
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                raise HTTPException(403, "Open Settings directly on the host PC.")

        def secure_request(request):
            if request.url.scheme != "https" or not self.secure:
                raise HTTPException(403, "Studio connections require HTTPS. No code or credential is accepted over HTTP.")

        @router.get("/info")
        def info():
            return self.public()

        @router.get("/settings")
        def settings(request: Request):
            local_operator(request)
            return self.operator_snapshot()

        @router.post("/settings")
        def configure(changes: NetworkSettings, request: Request):
            local_operator(request)
            if changes.allow_join and not self.secure:
                raise HTTPException(403, "Prepare HTTPS before allowing installed PCs to connect.")
            self.configure(changes.name, changes.allow_join)
            return self.operator_snapshot()

        @router.post("/new-code")
        def new_code(request: Request):
            local_operator(request)
            if not self.state["allow_join"]:
                raise HTTPException(403, "Enable connections first.")
            self.rotate_code()
            return self.operator_snapshot()

        @router.delete("/clients/{identifier}")
        def revoke(identifier: str, request: Request):
            local_operator(request)
            self.revoke(identifier)
            return self.operator_snapshot()

        @router.post("/pair")
        def pair(command: PairRequest, request: Request):
            secure_request(request)
            address = request.client.host if request.client else "unknown"
            return self.pair(command.code, command.name, address)

        @router.post("/ticket")
        def ticket(request: Request):
            secure_request(request)
            authorization = request.headers.get("authorization", "")
            if not authorization.startswith("Bearer ") or len(authorization) > 150:
                raise HTTPException(401, "An approved PC credential is required.")
            return self.issue_ticket(authorization[7:])

        @router.post("/join")
        def join(command: TicketRequest, request: Request):
            secure_request(request)
            token = self.consume_ticket(command.ticket)
            response = RedirectResponse("/?studio_client=1", status_code=303)
            response.set_cookie(COOKIE, token, max_age=30 * 86400, secure=True, httponly=True, samesite="strict", path="/")
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        return router


class ApprovedClientMiddleware:
    """Revoked native sessions fail closed; old iPad/camera URLs are unaffected."""
    def __init__(self, app, studio):
        self.app, self.studio = app, studio

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            from starlette.requests import HTTPConnection
            token = HTTPConnection(scope).cookies.get(COOKIE)
            handshake = scope["path"] in ("/studio/join", "/api/studio-network/pair", "/api/studio-network/ticket", "/api/studio-network/join")
            if token and not self.studio.valid_token(token) and not handshake:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 4401})
                else:
                    from starlette.responses import JSONResponse
                    await JSONResponse({"detail": "This PC's approval was removed. Close and reconnect with a new code."}, status_code=401)(scope, receive, send)
                return
            if token and scope["type"] == "websocket":
                original_receive = receive
                async def approved_receive():
                    event = await original_receive()
                    if not self.studio.valid_token(token):
                        # Deliver a normal disconnect to the application's
                        # cleanup handlers rather than processing another command.
                        return {"type": "websocket.disconnect", "code": 4401}
                    return event
                receive = approved_receive
        await self.app(scope, receive, send)


JOIN_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connecting to studio</title><link rel="stylesheet" href="/static/app-theme.css"><meta name="referrer" content="no-referrer"></head>
<body class="app-ui" style="padding:40px"><h1>Connecting to your studio…</h1><p id="result">Preparing the approved connection.</p>
<script>const ticket=location.hash.slice(1);history.replaceState(null,'','/studio/join');
fetch('/api/studio-network/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticket})}).then(async r=>{
if(!r.ok)throw Error((await r.json()).detail||'Connection failed');location.replace('/?studio_client=1');
}).catch(e=>document.getElementById('result').textContent=e.message+' Close this window and reconnect.');</script></body></html>"""


def discover_studios(timeout: float = 2.0, *, targets=None):
    from .network import discover_local_ips
    nonce = secrets.token_hex(16)
    query = json.dumps({"find": DISCOVERY_MAGIC, "nonce": nonce}).encode()
    targets = targets or [("255.255.255.255", DISCOVERY_PORT)]
    interfaces = [ip for ip in discover_local_ips() if local_ip(ip)] or ["0.0.0.0"]
    result = {}
    sockets = []
    import select
    try:
        for interface in interfaces:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockets.append(sock)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind((interface, 0))
            sock.setblocking(False)
            for target in targets:
                sock.sendto(query, target)
        deadline = time.monotonic() + min(max(timeout, .1), 5)
        while time.monotonic() < deadline and len(result) < 32:
            ready, _, _ = select.select(sockets, [], [], min(.2, max(0, deadline - time.monotonic())))
            for sock in ready:
                raw, (address, _) = sock.recvfrom(2048)
                try:
                    item = json.loads(raw)
                    port = item.get("port")
                    if item.get("found") != DISCOVERY_MAGIC or item.get("nonce") != nonce or not local_ip(address):
                        continue
                    uuid.UUID(item["id"])
                    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
                        continue
                    key = (item["id"], address, port)
                    result[key] = {"id": item["id"], "name": clean_name(item["name"]), "url": f"https://{address}:{port}"}
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
    finally:
        for sock in sockets:
            sock.close()
    return sorted(result.values(), key=lambda item: (item["name"], item["url"]))
