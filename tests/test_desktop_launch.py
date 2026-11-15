from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from run import wait_for_server
from server.build_info import APP_VERSION, SCOREBOARD_VERSION, UI_BUILD_ID
from server.config import Settings
from server.main import create_app
from server.scoreboard_state import State


def test_launcher_waits_for_its_own_server():
    server = SimpleNamespace(started=True, config=SimpleNamespace(port=8765))
    wait_for_server(server, SimpleNamespace(is_alive=lambda: True))


def test_failed_server_never_opens_an_older_listener():
    server = SimpleNamespace(started=False, config=SimpleNamespace(port=8765))
    with pytest.raises(RuntimeError, match="Close any other Studio"):
        wait_for_server(server, SimpleNamespace(is_alive=lambda: False))


def test_startup_timeout_requests_shutdown():
    server = SimpleNamespace(started=False, should_exit=False, config=SimpleNamespace(port=8765))
    with pytest.raises(RuntimeError, match="did not finish starting"):
        wait_for_server(server, SimpleNamespace(is_alive=lambda: True), timeout=0)
    assert server.should_exit is True


def test_desktop_embeds_upgraded_broadcast_desk_without_cached_html(tmp_path):
    app = create_app(Settings(database_path=tmp_path / "test.db"), scoreboard=State(tmp_path / "scores"))
    with patch("server.main.start_receiver"), TestClient(app) as client:
        desktop = client.get("/")
        assert f'/scoreboard?build={UI_BUILD_ID}' in desktop.text
        assert 'data-page-src="/graphics"' in desktop.text
        assert 'data-page-src="/match-setup"' in desktop.text
        assert 'data-page-src="/connections"' in desktop.text
        assert "__STUDIO_BUILD__" not in desktop.text
        page = client.get(f"/scoreboard?build={UI_BUILD_ID}")
        assert 'data-operator="scoreboard"' in page.text
        assert f'/operator-assets/workspace.js?build={UI_BUILD_ID}' in page.text
        assert 'id="statsEditor"' in client.get('/scoreboard?legacy=1').text
        assert f'/overlay.js?v={SCOREBOARD_VERSION}' in client.get('/overlay').text
        for route in ("/", "/scoreboard", "/overlay", "/control.js", "/scoreboard-assets/desk.css"):
            assert "no-store" in client.get(route).headers["cache-control"]
        assert client.get("/api/app-status").json()["scoreboard_version"] == SCOREBOARD_VERSION
