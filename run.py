from __future__ import annotations

import argparse
import ctypes
import io
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

DESKTOP_MUTEX = "Local\\CricketBroadcastSystem"

def wait_for_server(server, thread: threading.Thread, timeout: float = 12) -> None:
    """Wait for our server, never mistake another listener for a successful start."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise RuntimeError(
                f"Studio could not start on port {server.config.port}. "
                "Close any other Studio windows and their launcher consoles, then try again. "
                "Check the saved server log if the port is free."
            )
        if server.started:
            return
        time.sleep(.15)
    server.should_exit = True
    raise RuntimeError(f"The local server did not finish starting on port {server.config.port}")


def configure_logging(root: Path) -> Path:
    folder = root / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "application.log"
    handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # Windowed bundles have no stdout/stderr. Third-party code must not fail on None.
    if sys.stdout is None:
        sys.stdout = LogStream("stdout")
    if sys.stderr is None:
        sys.stderr = LogStream("stderr")
    return path


class LogStream(io.TextIOBase):
    """Capture windowed-library output in bounded logs, not an unlimited buffer."""
    def __init__(self, name):
        self.logger = logging.getLogger("desktop." + name)

    @property
    def encoding(self):
        return "utf-8"

    def write(self, value):
        if value.strip():
            self.logger.info(value.rstrip())
        return len(value)

    def flush(self):
        pass


class DesktopInstance:
    """Per-session guard; the installer checks the same mutex before updating."""
    def __init__(self):
        self.handle = None

    def acquire(self):
        if sys.platform != "win32":
            return
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        self.handle = kernel.CreateMutexW(None, False, DESKTOP_MUTEX)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            self.close()
            raise RuntimeError("Cricket Broadcast System is already running. Close it before opening Setup & connections or another app window.")

    def close(self):
        if self.handle:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(self.handle)
            self.handle = None


def open_desktop(settings, url, *, title="Cricket Broadcast System", client_origin=None):
    import webview
    from server.app_paths import default_recordings_root
    from server.install_support import load_preferences
    preferences = load_preferences(settings.data_root)
    downloads = Path(preferences.get("recordings_dir", str(default_recordings_root(settings.data_root))))
    downloads.mkdir(parents=True, exist_ok=True)
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["ALLOW_FILE_URLS"] = False
    from server.desktop_downloads import configure_downloads
    configure_downloads(downloads)
    webview.create_window(title, url=url, width=1440, height=920,
                          min_size=(980, 640), background_color="#0d110f")
    # Separate origin caches prevent host cookies/preferences following a PC
    # that switches between hosting and controlling another studio.
    import hashlib
    cache = "client-" + hashlib.sha256(client_origin.encode()).hexdigest()[:16] if client_origin else "host"
    webview.start(gui="edgechromium", debug=False, private_mode=False,
                  storage_path=str(settings.data_root / "webview" / cache))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cricket Broadcast System")
    parser.add_argument("--setup", action="store_true", help="Open setup / import / certificate maintenance")
    parser.add_argument("--data-dir", type=Path, help="Explicit absolute persistent data folder")
    parser.add_argument("--self-test", action="store_true", help="Check bundled modules and assets without opening the app")
    parser.add_argument("--headless", action="store_true", help="Server only; no desktop or setup UI")
    parser.add_argument("--port", type=int, help="Override port for managed deployments/tests")
    args = parser.parse_args(argv)
    if args.data_dir:
        if not args.data_dir.is_absolute():
            raise ValueError("--data-dir must be an absolute path")
        os.environ["CBS_DATA_DIR"] = str(args.data_dir)
    # Defer settings/server imports until overrides have been applied.
    from server.config import Settings
    from server.build_info import APP_VERSION, UI_BUILD_ID
    settings = Settings(**({"port": args.port} if args.port else {}))
    configure_logging(settings.data_root)
    if args.self_test:
        if not args.data_dir:
            raise ValueError("Use --self-test with an explicit, disposable --data-dir; normal saved data must not be used for tests")
        from server.install_support import has_saved_data
        if has_saved_data(settings.data_root) and not (settings.data_root / "self-test-result.json").exists():
            raise ValueError("The self-test folder already has saved data. Choose a new, disposable folder")
        from scripts.package_self_test import run_self_test
        run_self_test(settings)
        return 0
    instance = DesktopInstance()
    instance.acquire()
    try:
        from server.install_support import ensure_https, load_preferences
        if not args.headless:
            from server.studio_launcher import show_launcher
            choice = show_launcher(settings)
            if not choice:
                return 0
            if choice["mode"] == "connect":
                logging.info("Opening a remote studio client; local server and Bluetooth remain off")
                open_desktop(settings, choice["url"], title="Cricket Broadcast System · Connected to " + choice["name"],
                             client_origin=choice["origin"])
                return 0
        if getattr(sys, "frozen", False) or args.setup:
            from server.desktop_setup import setup_required, show_setup
            if args.setup or setup_required(settings):
                if args.headless:
                    raise RuntimeError("First-run setup / local certificate trust is incomplete. Open the desktop app once to finish setup.")
                if not show_setup(settings):
                    return 0
                if args.setup:
                    return 0
            ensure_https(settings.certificate_dir)
        cert = Path(settings.ssl_certfile) if settings.ssl_certfile else None
        key = Path(settings.ssl_keyfile) if settings.ssl_keyfile else None
        use_tls = bool(cert and key and cert.exists() and key.exists())
        if getattr(sys, "frozen", False) and not use_tls:
            raise RuntimeError("Local HTTPS is not ready. Use Setup & connections and choose Host; the installed app will not silently fall back to HTTP.")
        protocol = "https" if use_tls else "http"
        url = f"{protocol}://127.0.0.1:{settings.port}/?build={UI_BUILD_ID}"
        logging.info("Cricket Broadcast System %s · build %s · saved files %s", APP_VERSION, UI_BUILD_ID, settings.data_root)
        import uvicorn
        from server.main import create_app
        config = uvicorn.Config(
            create_app(settings), host=settings.host, port=settings.port, log_level="info", log_config=None,
            ssl_certfile=str(cert) if use_tls else None,
            ssl_keyfile=str(key) if use_tls else None,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, name="cricket-server", daemon=True)
        thread.start()
        try:
            wait_for_server(server, thread)
            if args.headless:
                thread.join()
                return 0
            try:
                import webview
            except ImportError:
                if getattr(sys, "frozen", False):
                    raise RuntimeError("The desktop viewer is missing from this installation. Please reinstall the app.")
                webbrowser.open(url)
                thread.join()
                return 0
            open_desktop(settings, url)
        finally:
            server.should_exit = True
            thread.join(timeout=8)
    finally:
        instance.close()
    return 0


def entrypoint() -> None:
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.exception("Application startup failed")
        if getattr(sys, "frozen", False) and "--headless" not in sys.argv and "--self-test" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, f"{exc}\n\nSee application.log in your saved files folder.\nUse Setup & connections and choose Host if local HTTPS needs attention.", "Cricket Broadcast System could not start", 0x10)
        elif sys.stderr:
            print(str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    entrypoint()
