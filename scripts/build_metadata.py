"""Generate distributable notices and audit the bundle, never include user data."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


def notices(root: Path):
    blocks = ["Cricket Broadcast System — third-party notices\n\n"
              "These notices apply to bundled third-party components, not a licence grant for the application's own source.\n"]
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.exists():
        raise RuntimeError("Python distribution licence is missing")
    blocks.append("\n===== Python " + sys.version.split()[0] + " =====\n" + python_license.read_text("utf-8"))
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = distribution.metadata["Name"]
        blocks.append(f"\n===== {name} {distribution.version} =====\n"
                      f"Homepage: {distribution.metadata.get('Home-page', '')}\n"
                      f"Licence: {distribution.metadata.get('License-Expression', distribution.metadata.get('License', 'See included notices'))}\n")
        for entry in distribution.files or []:
            if any(entry.name.lower().startswith(prefix) for prefix in ("license", "licence", "copying", "notice")):
                location = distribution.locate_file(entry)
                if location.is_file():
                    blocks.append(f"\n--- {entry} ---\n" + location.read_text("utf-8", errors="replace"))
    output = root / "build" / "THIRD_PARTY_NOTICES.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(blocks), encoding="utf-8")
    print(f"Generated third-party notices ({output.stat().st_size:,} bytes)")


def audit(root: Path):
    folder = root / "dist" / "CricketBroadcastSystem"
    prohibited = {"rootca.crt", "rootca.key.pem", "server.crt", "server.key.pem", ".env",
                  "settings.json", "branding.json", "teams.json", "broadcast.json", "backyard_drs.db",
                  "installation.json", "studio-network.json"}
    files = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(folder)
        if path.name.lower() in prohibited or path.suffix.lower() in {".key", ".pfx", ".p12", ".db", ".sqlite", ".sqlite3", ".clip", ".mp4", ".webm", ".log"}:
            raise RuntimeError(f"Private/test data found in bundle: {relative}")
        app_parts = relative.parts[1:] if relative.parts[0] == "_internal" else relative.parts
        # WinRT legitimately includes winrt/windows/storage; only top-level
        # application storage folders are private, not that dependency namespace.
        if app_parts[0].lower() in {"certs", "storage", "data", "client-certificates", "backups", ".venv", ".build-venv", ".git", ".preview"}:
            raise RuntimeError(f"Private folder found in bundle: {relative}")
        # `webview` is also the legitimate pywebview package. Its library/DLL
        # resources are not the application's browser profile directory.
        if app_parts[0].lower() == "webview" and len(app_parts) > 1 and (app_parts[1].lower() in {"default", "host", "crashpad"} or app_parts[1].lower().startswith("client-")):
            raise RuntimeError(f"Private browser profile found in bundle: {relative}")
        files.append({"path": relative.as_posix(), "size": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if not files or not (folder / "CricketBroadcastSystem.exe").exists():
        raise RuntimeError("No built executable to audit")
    sys.path.insert(0, str(root))
    from server.build_info import APP_VERSION
    result = {"version": APP_VERSION, "files": files, "private_data_included": False}
    (root / "dist" / "bundle-manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Bundle audit passed: {len(files)} files, {sum(f['size'] for f in files):,} bytes, no app keys/matches/footage")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["notices", "audit"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    (notices if args.action == "notices" else audit)(root)
