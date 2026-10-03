from pathlib import Path

from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(database_path=tmp_path / "test.db", port=8765)
    return TestClient(create_app(settings))


def test_pages_and_health(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.get("/").status_code == 200
        umpire_page = client.get("/umpire").text
        assert "Camera wall" in umpire_page
        assert '<a class="server-address"' in umpire_page
        assert "<!-- CAMERA_URLS -->" not in umpire_page
        assert 'type="module"' not in umpire_page
        camera_page = client.get("/camera").text
        assert "Configure camera" in camera_page
        assert 'id="connectButton" class="btn btn-primary" type="button"' in camera_page
        assert 'onsubmit="return false"' in camera_page
        assert 'type="module"' not in camera_page
        assert 'id="cameraDevice"' in camera_page
        assert "Your ground, in one place" in client.get("/").text
        assert client.get("/scoreboard").status_code == 200
        assert client.get("/overlay").status_code == 200
        assert client.get("/broadcast").status_code == 200
        assert client.get("/api/scoreboard/state").status_code == 200
        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        assert health["connected_cameras"] == 0
        server_info = client.get("/api/server-info").json()
        assert server_info["camera_urls"]
        assert server_info["camera_urls"][0].endswith(":8765/camera")


def test_camera_registration_is_broadcast_and_persisted(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        with client.websocket_connect("/ws/umpire?console_id=test-console") as umpire:
            assert umpire.receive_json()["devices"] == []
            with client.websocket_connect("/ws/camera") as camera:
                camera.send_json(
                    {
                        "type": "register",
                        "device_id": "phone-a",
                        "name": "Crease Phone",
                        "role": "CREASE_LEFT",
                        "settings": {"resolution": "1280x720", "fps": 30},
                        "capabilities": {"media_devices": True},
                    }
                )
                update = umpire.receive_json()
                registered = camera.receive_json()
                assert update["devices"][0]["device_id"] == "phone-a"
                assert update["devices"][0]["remote_address"] == "testclient"
                assert registered["type"] == "registered"

                camera.send_json(
                    {"type": "heartbeat", "sequence": 7, "client_time_ms": 1000}
                )
                heartbeat = camera.receive_json()
                assert heartbeat["type"] == "heartbeat_ack"
                assert heartbeat["sequence"] == 7

            assert umpire.receive_json()["devices"] == []
        saved = client.get("/api/devices").json()["devices"]
        assert saved[0]["status"] == "offline"
        assert saved[0]["name"] == "Crease Phone"


def test_device_can_be_renamed_and_disconnected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        with client.websocket_connect("/ws/camera") as camera:
            camera.send_json(
                {
                    "type": "register",
                    "device_id": "phone-b",
                    "name": "Old Name",
                    "role": "OTHER",
                }
            )
            assert camera.receive_json()["type"] == "registered"
            response = client.patch(
                "/api/devices/phone-b",
                json={"name": "Wicket Phone", "role": "WICKET_MIC"},
            )
            assert response.status_code == 200
            configuration = camera.receive_json()
            assert configuration == {
                "type": "configuration",
                "name": "Wicket Phone",
                "role": "WICKET_MIC",
            }
            response = client.delete("/api/devices/phone-b/connection")
            assert response.status_code == 200


def test_invalid_registration_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        with client.websocket_connect("/ws/camera") as camera:
            camera.send_json({"type": "register", "device_id": "x"})
            message = camera.receive()
            assert message["type"] == "websocket.close"
            assert message["code"] == 4400


def test_webrtc_signaling_is_relayed_both_directions(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        with client.websocket_connect("/ws/umpire?console_id=console-one") as umpire:
            assert umpire.receive_json()["type"] == "devices"
            with client.websocket_connect("/ws/camera") as camera:
                camera.send_json(
                    {
                        "type": "register",
                        "device_id": "stream-camera",
                        "name": "Streaming Phone",
                        "role": "UMPIRE_POV",
                        "settings": {"microphone": False},
                    }
                )
                assert umpire.receive_json()["type"] == "devices"
                assert camera.receive_json()["type"] == "registered"

                offer = {"description": {"type": "offer", "sdp": "test-offer"}}
                umpire.send_json(
                    {
                        "type": "webrtc_signal",
                        "device_id": "stream-camera",
                        "signal": offer,
                    }
                )
                to_camera = camera.receive_json()
                assert to_camera == {
                    "type": "webrtc_signal",
                    "console_id": "console-one",
                    "signal": offer,
                }

                answer = {"description": {"type": "answer", "sdp": "test-answer"}}
                camera.send_json(
                    {
                        "type": "webrtc_signal",
                        "console_id": "console-one",
                        "signal": answer,
                    }
                )
                to_umpire = umpire.receive_json()
                assert to_umpire == {
                    "type": "webrtc_signal",
                    "device_id": "stream-camera",
                    "signal": answer,
                }
