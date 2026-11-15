import asyncio
from unittest.mock import patch

from server.database import Database
from server.device_manager import ConnectedDevice, DeviceManager


class Socket:
    def __init__(self): self.messages=[];self.closed=None
    async def send_json(self,message): self.messages.append(message)
    async def close(self,code,reason): self.closed=(code,reason)


def test_server_heartbeat_uses_network_events_without_inventing_liveness(tmp_path):
    async def check():
        database=Database(tmp_path/'test.db');database.initialise();manager=DeviceManager(database)
        socket,legacy=Socket(),Socket()
        device=ConnectedDevice('direct','Direct','OTHER',socket,'test',0,last_seen_monotonic=1,capabilities={'server_heartbeat':True})
        await manager.register_camera(device)
        await manager.register_camera(ConnectedDevice('legacy','Legacy','OTHER',legacy,'test',0))
        await manager.request_heartbeats()
        assert socket.messages==[{'type':'heartbeat_request'}] and not legacy.messages
        assert device.last_seen_monotonic==1
        # A frozen tab still times out: a request alone proves nothing.
        with patch('server.device_manager.time.monotonic',return_value=15):
            await manager.disconnect_stale(12)
        assert socket.closed[0]==4002
    asyncio.run(check())


def test_background_response_keeps_silent_static_camera_connected(tmp_path):
    async def check():
        database=Database(tmp_path/'test.db');database.initialise();manager=DeviceManager(database);socket=Socket()
        device=ConnectedDevice('black','Static virtual camera','OTHER',socket,'test',0,last_seen_monotonic=1,
                               settings={'microphone':False},capabilities={'server_heartbeat':True})
        await manager.register_camera(device);await manager.request_heartbeats()
        with patch('server.device_manager.time.monotonic',return_value=10): await manager.heartbeat('black',socket)
        with patch('server.device_manager.time.monotonic',return_value=15): assert await manager.disconnect_stale(12)==0
        assert socket.closed is None and device.settings=={'microphone':False}
    asyncio.run(check())
