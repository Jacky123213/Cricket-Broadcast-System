"""Read-only packaged resources and persistent, per-user files are separate."""
from __future__ import annotations

import os
import sys
from pathlib import Path

RESOURCE_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_FOLDER = "CricketBroadcastSystem"


def default_data_root() -> Path:
    # Also useful for isolated tests / explicitly managed deployments. Never
    # resolve a relative override against an unpredictable shortcut working dir.
    override = os.environ.get("CBS_DATA_DIR") or os.environ.get("DRS_DATA_ROOT")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError("CBS_DATA_DIR must be an absolute folder path")
        return path.resolve()
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            raise RuntimeError("Windows did not provide a Local AppData folder")
        return Path(local) / PRODUCT_FOLDER
    # Source/.bat installations remain compatible. The existing installation is
    # not migrated implicitly simply because an installer build was created.
    return RESOURCE_ROOT


def default_recordings_root(data_root: Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / "Videos" / "Cricket Broadcast System"
    return data_root / "recordings"
