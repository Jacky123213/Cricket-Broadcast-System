"""Conservative first-run import. Never move or overwrite an old installation."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCORE_FILES = ("settings.json", "teams.json", "broadcast.json", "branding.json")
CERT_FILES = ("rootCA.crt", "rootCA.key.pem", "server.crt", "server.key.pem")
MANAGED_FOLDERS = ("data", "storage", "certs")


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_preferences(root: Path) -> dict:
    path = root / "installation.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        return value
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot read saved setup preferences: {path}. Nothing was reset.") from exc


def is_link(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def checked_source(path: Path, root: Path) -> Path:
    # Reject directory junctions as well as symlinks; do not copy files outside
    # the explicitly selected old app folder, even through a linked parent.
    relative = path.relative_to(root)
    current = root
    for component in relative.parts:
        current /= component
        if is_link(current):
            raise ValueError(f"Import does not follow linked files/folders: {current.name}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Import file is outside the selected app folder")
    return path


def has_saved_data(root: Path) -> bool:
    return any((root / "data" / name).exists() for name in SCORE_FILES) or any(
        (root / "certs" / name).exists() for name in CERT_FILES
    ) or (root / "storage" / "backyard_drs.db").exists()


def import_legacy(source: Path, target: Path) -> dict:
    source, target = source.absolute(), target.resolve()
    if not source.is_dir() or is_link(source):
        raise ValueError("Choose the original app folder, not a linked folder")
    source = source.resolve()
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError("Old and new data folders must be separate and must not contain one another")
    if not has_saved_data(source):
        raise ValueError("That folder has no recognised match data or certificates")
    # Refuse even empty pre-existing managed folders: recovery is explicit,
    # never a partial merge over a previously used installation.
    if any((target / name).exists() for name in MANAGED_FOLDERS):
        raise ValueError("This installation already has saved data. Import is only available before first setup; nothing was overwritten.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = target / "backups" / f"import-{stamp}-{uuid.uuid4().hex[:8]}"
    backup.mkdir(parents=True)
    copied = []
    for name in SCORE_FILES:
        original = source / "data" / name
        if original.exists():
            checked_source(original, source)
            # Detect damaged JSON before any new match state is committed.
            json.loads(original.read_text("utf-8"))
            destination = backup / "data" / name
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(original, destination)
            copied.append(f"data/{name}")
    for name in CERT_FILES:
        original = source / "certs" / name
        if original.exists():
            checked_source(original, source)
            destination = backup / "certs" / name
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(original, destination)
            copied.append(f"certs/{name}")
    ca = backup / "certs"
    if ca.exists():
        from scripts.generate_certificate import reuse_existing_ca
        reuse_existing_ca(ca)  # Abort on missing/mismatched/expired CA, never replace it.
    original_db = source / "storage" / "backyard_drs.db"
    if original_db.exists():
        checked_source(original_db, source)
        (backup / "storage").mkdir(exist_ok=True)
        # SQLite's online backup includes committed WAL records consistently.
        # The source is opened read-only and never rewritten or checkpointed.
        with sqlite3.connect(original_db.as_uri() + "?mode=ro", uri=True) as old:
            with sqlite3.connect(backup / "storage" / original_db.name) as new:
                old.backup(new)
                if new.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("The old match database failed its integrity check")
        copied.append("storage/backyard_drs.db")
    # Stage all target folders first. An unexpected failure leaves the import
    # backup and a clear refusal on retry instead of silently merging partial data.
    for folder in MANAGED_FOLDERS:
        if (backup / folder).exists():
            shutil.copytree(backup / folder, target / folder, symlinks=False)
    result = {"source": str(source), "backup": str(backup), "files": copied,
              "imported_at": datetime.now(timezone.utc).isoformat()}
    write_json_atomic(target / "import-report.json", result)
    return result


def ensure_https(cert_dir: Path, *, refresh: bool = False) -> None:
    from scripts.generate_certificate import generate_certificates, reuse_existing_ca, load_certificate, local_addresses
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.x509.oid import ExtendedKeyUsageOID
    ca_present = any((cert_dir / name).exists() for name in CERT_FILES[:2])
    if not ca_present and any((cert_dir / name).exists() for name in CERT_FILES[2:]):
        raise RuntimeError("Existing server certificate/key found without its CA. Restore your certificate backup; nothing was replaced.")
    if ca_present:
        _, ca = reuse_existing_ca(cert_dir)
        valid = False
        if not refresh and (cert_dir / "server.crt").exists() and (cert_dir / "server.key.pem").exists():
            cert = load_certificate(cert_dir / "server.crt")
            key = serialization.load_pem_private_key((cert_dir / "server.key.pem").read_bytes(), password=None)
            now = datetime.now(timezone.utc)
            same_key = cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) == key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            addresses = set(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress))
            cert.verify_directly_issued_by(ca)
            valid = same_key and cert.not_valid_before_utc <= now < cert.not_valid_after_utc and set(local_addresses()) <= addresses and ExtendedKeyUsageOID.SERVER_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if valid and not refresh:
            return
    # Preserve CA and server key on all updates, network/IP changes and repairs.
    generate_certificates(cert_dir, reuse_ca=ca_present)
