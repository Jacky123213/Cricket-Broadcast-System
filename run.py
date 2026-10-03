from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from server.config import get_settings
from server.build_info import APP_VERSION, UI_BUILD_ID
from server.main import create_app


def wait_for_server(server: uvicorn.Server, thread: threading.Thread, timeout: float = 12) -> None:
    """Wait for our server, never mistake another listener for a successful start."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise RuntimeError(
                f"Studio could not start on port {server.config.port}. "
                "Close any other Studio windows and their launcher consoles, then try again. "
                "Check the server error above if the port is free."
            )
        if server.started:
            return
        time.sleep(.15)
    server.should_exit = True
    raise RuntimeError(f"The local server did not finish starting on port {server.config.port}")


def main() -> None:
    settings = get_settings()
    cert = Path(settings.ssl_certfile) if settings.ssl_certfile else None
    key = Path(settings.ssl_keyfile) if settings.ssl_keyfile else None
    use_tls = bool(cert and key and cert.exists() and key.exists())
    protocol = "https" if use_tls else "http"
    url = f"{protocol}://127.0.0.1:{settings.port}/?build={UI_BUILD_ID}"
    print(f"Backyard Cricket Studio {APP_VERSION} · build {UI_BUILD_ID}")
    print(f"Application folder: {Path(__file__).resolve().parent}")
    config = uvicorn.Config(
        create_app(settings), host=settings.host, port=settings.port, log_level="info",
        ssl_certfile=str(cert) if use_tls else None,
        ssl_keyfile=str(key) if use_tls else None,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="backyard-server", daemon=True)
    thread.start()
    wait_for_server(server, thread)

    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        print(f"Backyard Cricket Studio: {url}\nPress Ctrl+C to stop.")
        try:
            thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
        return

    window = webview.create_window(
        "Backyard Cricket Studio", url=url, width=1440, height=920,
        min_size=(980, 640), background_color="#0d110f",
    )
    try:
        webview.start(debug=False, private_mode=False)
    finally:
        server.should_exit = True
        thread.join(timeout=8)


if __name__ == "__main__":
    main()
