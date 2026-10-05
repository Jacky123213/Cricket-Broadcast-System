"""Release labels and a source fingerprint for desktop cache invalidation."""
import hashlib

from .config import PROJECT_ROOT

APP_VERSION = "1.1.2"
SCOREBOARD_VERSION = "0.4.2"


def ui_build_id() -> str:
    digest = hashlib.sha256()
    frontend = PROJECT_ROOT / "frontend"
    for path in sorted(frontend.rglob("*")):
        if path.is_file() and path.suffix in {".html", ".css", ".js"}:
            digest.update(path.relative_to(frontend).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


UI_BUILD_ID = ui_build_id()
