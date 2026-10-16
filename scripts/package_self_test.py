"""Exercises real bundled native modules/resources without hardware or trust changes."""
from __future__ import annotations

import importlib
import json
import logging
import ssl
import threading
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

__test__ = False  # Diagnostic helpers are not pytest fixtures/tests.


def check_desktop_window(settings) -> dict:
    """Hidden, real WebView2 render against a loopback-only diagnostic server.

    The production server is HTTPS. This isolated render uses HTTP so no test
    CA has to be added to Windows trust. TLS routes are checked separately with
    an explicit CA in a Python SSL context, without disabling verification.
    """
    import uvicorn
    import webview
    from server.config import Settings
    from server.main import create_app
    from server.desktop_downloads import configure_downloads
    from run import wait_for_server
    desktop_settings = Settings(data_root=settings.data_root / "desktop-render", ssl_certfile=None, ssl_keyfile=None)
    app = create_app(desktop_settings)
    # Diagnostic-only HTTP bootstrap for the native *client* UI render. This
    # route is never part of the production app or its HTTPS handshake.
    from fastapi.responses import RedirectResponse
    from fastapi.responses import HTMLResponse
    from scripts.graphics_layout_test import FRAME_PAGE, check_graphics_layout
    from server.studio_network import COOKIE, digest
    import secrets
    diagnostic_token = secrets.token_urlsafe(32)
    app.state.studio_network.state["name"] = "Diagnostic host PC"
    app.state.studio_network.state["clients"][digest(diagnostic_token)] = {"name": "Diagnostic client"}

    @app.get("/diagnostic-client", include_in_schema=False)
    def diagnostic_client():
        response = RedirectResponse("/?studio_client=1")
        response.set_cookie(COOKIE, diagnostic_token, httponly=True, samesite="strict")
        return response

    @app.get("/diagnostic-graphics", include_in_schema=False)
    def diagnostic_graphics():
        return HTMLResponse(FRAME_PAGE)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None))
    result, errors = {}, []
    with patch("server.main.start_receiver"):
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            wait_for_server(server, thread)
            port = server.servers[0].sockets[0].getsockname()[1]
            configure_downloads(settings.data_root / "desktop-downloads")
            webview.settings["ALLOW_DOWNLOADS"] = True
            window = webview.create_window("Cricket Broadcast System diagnostics", url=f"http://127.0.0.1:{port}/", hidden=True)

            def check_window():
                try:
                    if not window.events.loaded.wait(20):
                        raise RuntimeError("The hidden WebView2 window did not load")
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        page = window.evaluate_js("({title:document.title, ready:document.getElementById('serverText')?.textContent, views:document.querySelectorAll('.view').length, matchDay:!!document.getElementById('matchDayFrame')?.contentDocument?.getElementById('programPreview'), userAgent:navigator.userAgent})")
                        if page and page.get("ready") == "Local server ready":
                            result.update(page)
                            break
                        time.sleep(.25)
                    if result.get("views", 0) < 6 or "Cricket Broadcast System" not in result.get("title", ""):
                        raise RuntimeError(f"Desktop render did not become ready: {result}")
                    window.load_url(f"http://127.0.0.1:{port}/diagnostic-client")
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        client_page = window.evaluate_js("({ready:document.getElementById('serverText')?.textContent, mode:document.getElementById('studioMode')?.textContent, approvalHidden:document.getElementById('studioNetworkControls')?.hidden, matchDay:!!document.getElementById('matchDayFrame')?.contentDocument?.getElementById('programPreview')})")
                        if client_page and client_page.get("ready") == "Connected to Diagnostic host PC" and client_page.get("matchDay"):
                            result["client_render"] = client_page
                            break
                        time.sleep(.25)
                    if result.get("client_render", {}).get("mode") != "Connected to" or not result["client_render"]["approvalHidden"]:
                        raise RuntimeError(f"Connected-PC render did not become ready: {result}")
                    result["graphics_layout"] = check_graphics_layout(window, f"http://127.0.0.1:{port}", settings.data_root / "graphics-checks")
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    window.destroy()

            webview.start(check_window, gui="edgechromium", private_mode=True,
                          storage_path=str(settings.data_root / "desktop-webview"))
            if errors:
                raise RuntimeError("; ".join(errors))
            if not result:
                raise RuntimeError("The native desktop render returned no results")
        finally:
            server.should_exit = True
            thread.join(timeout=10)
    return result


def run_self_test(settings) -> dict:
    import cv2
    import numpy as np
    import tkinter
    import webview
    import uvicorn
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from server.app_paths import RESOURCE_ROOT
    from server.build_info import APP_VERSION
    from server.install_support import ensure_https, write_json_atomic
    modules = ["webview.platforms.winforms", "webview.platforms.edgechromium", "pythonnet", "clr_loader",
               "winrt.windows.foundation", "winrt.windows.foundation.collections",
               "winrt.windows.devices.bluetooth", "winrt.windows.devices.bluetooth.genericattributeprofile",
               "winrt.windows.storage.streams", "qrcode.image.svg", "websockets"]
    for name in modules:
        importlib.import_module(name)
    assert cv2.cvtColor(np.zeros((2, 2, 3), dtype=np.uint8), cv2.COLOR_BGR2GRAY).shape == (2, 2)
    assert tkinter.Tcl().eval("info patchlevel")
    assert "ALLOW_DOWNLOADS" in webview.settings
    assert (RESOURCE_ROOT / "THIRD_PARTY_NOTICES.txt").stat().st_size > 1000
    # Test certificates live only in the explicitly selected self-test folder.
    ensure_https(settings.certificate_dir)
    ca_bytes = (settings.certificate_dir / "rootCA.crt").read_bytes()
    key_bytes = (settings.certificate_dir / "rootCA.key.pem").read_bytes()
    ensure_https(settings.certificate_dir, refresh=True)
    assert (settings.certificate_dir / "rootCA.crt").read_bytes() == ca_bytes
    assert (settings.certificate_dir / "rootCA.key.pem").read_bytes() == key_bytes
    ca = x509.load_der_x509_certificate(ca_bytes)
    ca_pem = ca.public_bytes(serialization.Encoding.PEM).decode()
    context = ssl.create_default_context(cadata=ca_pem)
    from server.main import create_app
    # Diagnostic TLS server is loopback-only, including its discovery service.
    settings.host = "127.0.0.1"
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None,
                            ssl_certfile=str(settings.ssl_certfile), ssl_keyfile=str(settings.ssl_keyfile)))
    checks = {}
    with patch("server.main.start_receiver"):
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            from run import wait_for_server
            wait_for_server(server, thread)
            port = server.servers[0].sockets[0].getsockname()[1]
            for route in ("/", "/camera", "/umpire", "/scoreboard", "/overlay", "/broadcast", "/match-day",
                          "/static/recording.js", "/desktop.js", "/scoreboard-assets/desk.css", "/reliability-checklist",
                          "/api/health", "/api/server-info", "/api/scoreboard/state", "/local-ca.crt"):
                with urllib.request.urlopen(f"https://127.0.0.1:{port}{route}", context=context, timeout=5) as response:
                    content = response.read()
                    assert response.status == 200 and content, route
                    checks[route] = len(content)
            from websockets.sync.client import connect
            with connect(f"wss://127.0.0.1:{port}/ws/umpire?console_id=packaged-self-test", ssl=context, proxy=None, open_timeout=5) as websocket:
                roster = json.loads(websocket.recv(timeout=5))
                assert "devices" in roster
                checks["/ws/umpire (verified TLS WebSocket)"] = len(roster["devices"])
            from server.studio_client import StudioClient, remember_connection
            app.state.studio_network.configure("Packaged test host", True)
            remote = StudioClient(f"https://127.0.0.1:{port}", settings.certificate_dir / "rootCA.crt")
            paired = remote.connect(code=app.state.studio_network.code)
            remembered = remote.connect(token=paired["token"], expected_id=paired["studio"]["id"])
            assert paired["ticket"] != remembered["ticket"]
            client_root = settings.data_root / "connected-pc"
            remember_connection(client_root, remote, remembered)
            assert not (client_root / "certs").exists() and not (client_root / "storage").exists()
            assert not list(client_root.rglob("*.pem"))
            # Exercise the exact installed launcher branch: no local services
            # or host certificate setup may run when Connect was selected.
            import run
            choice = {"mode": "connect", "url": remote.url + "/studio/join#" + remembered["ticket"],
                      "origin": remote.url, "name": "Packaged test host"}
            import uuid
            with patch("server.studio_launcher.show_launcher", return_value=choice), patch("run.open_desktop") as viewer, patch("run.configure_logging"), \
                 patch("run.DESKTOP_MUTEX", "Local\\CBSDiagnostic-" + uuid.uuid4().hex), \
                 patch("uvicorn.Server") as local_server, patch("server.desktop_setup.show_setup") as host_setup, \
                 patch.dict("os.environ", {"CBS_DATA_DIR": str(client_root)}):
                assert run.main(["--data-dir", str(client_root)]) == 0
                viewer.assert_called_once()
                local_server.assert_not_called()
                host_setup.assert_not_called()
            checks["installed client: verified TLS pair + remembered reconnect + no local server/private keys"] = 1
            assert (settings.database_path).exists()
            assert settings.scoreboard_path == settings.data_root / "data"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("Self-test server did not close cleanly")
    from server.desktop_setup import show_setup
    setup_window = show_setup(settings, _diagnostics=True)
    assert setup_window["scrollable"] and setup_window["certificate_approval_default"] is False
    from server.studio_launcher import show_launcher
    launcher_window = show_launcher(settings, _diagnostics=True)
    assert launcher_window["scrollable"] and launcher_window["certificate_approval_default"] is False
    desktop = check_desktop_window(settings)
    result = {"status": "passed", "version": APP_VERSION, "native_modules": modules,
              "https_routes": checks, "data_root": str(settings.data_root),
              "hardware_tested": False, "webview_window_tested": True, "desktop_render": desktop,
              "setup_window": setup_window, "studio_launcher_window": launcher_window}
    write_json_atomic(settings.data_root / "self-test-result.json", result)
    logging.info("Packaged self-test passed: %s", result)
    return result
