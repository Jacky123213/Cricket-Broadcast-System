from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from pydantic import ValidationError

from .database import Database
from .models import BatteryStatus


@dataclass
class ConnectedDevice:
    device_id: str
    name: str
    role: str
    websocket: WebSocket
    remote_address: str
    connected_at_ms: int
    last_seen_monotonic: float = field(default_factory=time.monotonic)
    settings: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    battery: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "role": self.role,
            "status": "connected",
            "remote_address": self.remote_address,
            "connected_at_ms": self.connected_at_ms,
            "last_seen_age_ms": round(
                (time.monotonic() - self.last_seen_monotonic) * 1000
            ),
            "settings": self.settings,
            "capabilities": self.capabilities,
            "battery": self.battery,
        }


class DeviceManager:
    def __init__(self, database: Database):
        self.database = database
        self._devices: dict[str, ConnectedDevice] = {}
        self._umpires: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def battery_status(payload: Any) -> dict[str, Any] | None:
        """Unsupported/invalid telemetry is unavailable, never a guessed charge."""
        if payload is None:
            return None
        try:
            return BatteryStatus.model_validate(payload).model_dump()
        except ValidationError:
            return None

    async def update_battery(self, device_id: str, websocket: WebSocket, payload: Any) -> None:
        battery = self.battery_status(payload)
        if payload is not None and battery is None:
            return
        async with self._lock:
            device = self._devices.get(device_id)
            if not device or device.websocket is not websocket or device.battery == battery:
                return
            device.battery = battery
        # Ephemeral telemetry: do not persist it or restart video/recording.
        await self.broadcast_snapshot()

    async def register_camera(self, device: ConnectedDevice) -> None:
        previous: ConnectedDevice | None
        async with self._lock:
            previous = self._devices.get(device.device_id)
            self._devices[device.device_id] = device
        if previous and previous.websocket is not device.websocket:
            try:
                await previous.websocket.close(code=4001, reason="Device reconnected")
            except RuntimeError:
                pass
        await asyncio.to_thread(
            self.database.upsert_device,
            device.device_id,
            device.name,
            device.role,
            device.settings,
            device.capabilities,
        )
        await self.broadcast_snapshot()

    async def heartbeat(self, device_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            device = self._devices.get(device_id)
            if device and device.websocket is websocket:
                device.last_seen_monotonic = time.monotonic()
            else:
                device = None
        if device:
            await asyncio.to_thread(self.database.touch_device, device_id)

    async def update_media(self, device_id: str, websocket: WebSocket, microphone: bool) -> None:
        """Only the active camera socket can announce a changed capture stream."""
        async with self._lock:
            device = self._devices.get(device_id)
            if not device or device.websocket is not websocket:
                return
            revision = device.settings.get("media_revision", 0)
            revision = revision if type(revision) is int and revision >= 0 else 0
            device.settings = {**device.settings, "microphone": microphone,
                               "media_revision": revision + 1}
        await self.broadcast_snapshot()

    async def remove_camera(self, device_id: str, websocket: WebSocket) -> None:
        changed = False
        async with self._lock:
            current = self._devices.get(device_id)
            if current and current.websocket is websocket:
                del self._devices[device_id]
                changed = True
        if changed:
            await self.broadcast_snapshot()

    async def add_umpire(self, console_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            previous = self._umpires.get(console_id)
            self._umpires[console_id] = websocket
        if previous and previous is not websocket:
            try:
                await previous.close(code=4001, reason="Console reconnected")
            except RuntimeError:
                pass
        await websocket.send_json(self.snapshot_message())

    async def remove_umpire(self, console_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if self._umpires.get(console_id) is websocket:
                del self._umpires[console_id]

    def connected_snapshot(self) -> list[dict[str, Any]]:
        return sorted(
            (device.public() for device in self._devices.values()),
            key=lambda item: (item["role"], item["name"].lower()),
        )

    def snapshot_message(self) -> dict[str, Any]:
        return {
            "type": "devices",
            "server_time_ms": int(time.time() * 1000),
            "devices": self.connected_snapshot(),
        }

    async def broadcast_snapshot(self) -> None:
        message = self.snapshot_message()
        stale: list[tuple[str, WebSocket]] = []
        for console_id, websocket in list(self._umpires.items()):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append((console_id, websocket))
        if stale:
            async with self._lock:
                for console_id, websocket in stale:
                    if self._umpires.get(console_id) is websocket:
                        del self._umpires[console_id]

    async def signal_camera(self, device_id: str, message: dict[str, Any]) -> bool:
        async with self._lock:
            device = self._devices.get(device_id)
        if not device:
            return False
        try:
            await device.websocket.send_json(message)
            return True
        except Exception:
            return False

    async def signal_umpire(self, console_id: str, message: dict[str, Any]) -> bool:
        async with self._lock:
            websocket = self._umpires.get(console_id)
        if not websocket:
            return False
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False

    async def update_device(self, device_id: str, name: str, role: str) -> bool:
        async with self._lock:
            device = self._devices.get(device_id)
            if device:
                device.name = name
                device.role = role
        try:
            await asyncio.to_thread(self.database.rename_device, device_id, name, role)
        except KeyError:
            return False
        if device:
            try:
                await device.websocket.send_json(
                    {"type": "configuration", "name": name, "role": role}
                )
            except Exception:
                pass
        await self.broadcast_snapshot()
        return True

    async def disconnect_device(self, device_id: str) -> bool:
        async with self._lock:
            device = self._devices.get(device_id)
        if not device:
            return False
        await device.websocket.close(code=4000, reason="Disconnected by umpire")
        return True

    async def disconnect_stale(self, max_age_seconds: float) -> int:
        """Close connections that stopped sending application heartbeats."""
        now = time.monotonic()
        async with self._lock:
            stale = [
                device
                for device in self._devices.values()
                if now - device.last_seen_monotonic > max_age_seconds
            ]
        for device in stale:
            try:
                await device.websocket.close(code=4002, reason="Heartbeat timed out")
            except RuntimeError:
                pass
        return len(stale)
