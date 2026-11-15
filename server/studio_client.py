"""Verified HTTPS client. Never starts a server or imports host private keys."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from .install_support import load_preferences, write_json_atomic
from .studio_network import DISCOVERY_MAGIC, local_ip, clean_name


class ConnectionError(RuntimeError):
    pass


class ApprovalRequired(ConnectionError):
    pass


def studio_url(value: str) -> str:
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    url = urllib.parse.urlsplit(value)
    try:
        port = url.port or 8765
    except ValueError as exc:
        raise ValueError("Use a valid studio port, usually 8765") from exc
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use the host's local HTTPS address, for example https://192.168.1.68:8765")
    if not local_ip(url.hostname) or url.path not in ("", "/", "/match-day", "/umpire", "/broadcast") or not 1 <= port <= 65535:
        raise ValueError("Enter a local IPv4 address (not a public website or hostname). Use the LAN address shown in host Settings.")
    return f"https://{ipaddress.ip_address(url.hostname)}:{port}"


def public_ca(path: Path):
    raw = path.read_bytes()
    if len(raw) > 16384 or b"PRIVATE KEY" in raw:
        raise ValueError("Select only the public rootCA.crt certificate, never a private key or backup")
    try:
        ca = x509.load_pem_x509_certificate(raw) if raw.startswith(b"-----BEGIN CERTIFICATE") else x509.load_der_x509_certificate(raw)
        now = datetime.now(timezone.utc)
        if not ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca or not ca.not_valid_before_utc <= now < ca.not_valid_after_utc:
            raise ValueError("The selected CA certificate is expired or is not a certificate authority")
        ca.verify_directly_issued_by(ca)
    except (ValueError, TypeError, x509.ExtensionNotFound) as exc:
        raise ValueError("Choose the valid public CA certificate exported from the host's Settings") from exc
    der = ca.public_bytes(serialization.Encoding.DER)
    return der, hashlib.sha256(der).hexdigest().upper(), ca.public_bytes(serialization.Encoding.PEM).decode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectionError("The studio redirected to another address. Use its current LAN address instead.")


class StudioClient:
    def __init__(self, url: str, ca: Path):
        self.url = studio_url(url)
        self.ca = ca
        self.der, self.fingerprint, pem = public_ca(ca)
        # Trust only the selected public CA in this Python connection. Windows
        # trust is a separate, explicit checkbox for the native WebView2 viewer.
        self.context = ssl.create_default_context(cadata=pem)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                                 urllib.request.HTTPSHandler(context=self.context))

    def request(self, path: str, *, data=None, token=None):
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, headers=headers,
                                         method="POST" if data is not None or token else "GET")
        try:
            with self.opener.open(request, timeout=4) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ConnectionError("The studio returned an oversized response")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ConnectionError("The studio returned an invalid response")
                return result
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read(4096)).get("detail", f"HTTP {exc.code}")
            except (ValueError, AttributeError):
                detail = f"HTTP {exc.code}"
            if exc.code == 401:
                raise ApprovalRequired(str(detail)) from exc
            raise ConnectionError(str(detail)) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ConnectionError("Cannot reach or verify this studio. Check the host, its LAN address, public CA and Private-network firewall. " + str(exc)) from exc

    def info(self):
        info = self.request("/api/studio-network/info")
        if info.get("protocol") != DISCOVERY_MAGIC or not info.get("secure"):
            raise ConnectionError("Update the host to an installer version with studio connections and HTTPS enabled")
        if info.get("ca_sha256") != self.fingerprint:
            raise ConnectionError("This studio's public CA changed. Verify the new certificate with its owner before reconnecting.")
        return info

    def connect(self, *, code: str = "", token: str = "", expected_id: str | None = None):
        info = self.info()
        if expected_id and info.get("id") != expected_id:
            raise ConnectionError("A different studio is using that address. Select it explicitly and obtain a new code.")
        if token:
            result = self.request("/api/studio-network/ticket", token=token)
            result["token"] = token
        elif code.strip():
            result = self.request("/api/studio-network/pair", data={"code": code.strip(), "name": clean_name(socket.gethostname())})
        else:
            raise ApprovalRequired("Enter the connection code from Settings on the host PC")
        if not isinstance(result.get("ticket"), str) or not isinstance(result.get("token"), str) or not isinstance(result.get("studio"), dict):
            raise ConnectionError("The host did not approve a valid connection")
        if result["studio"].get("id") != info.get("id") or result["studio"].get("ca_sha256") != self.fingerprint:
            raise ConnectionError("The studio identity changed while connecting. Verify its address before retrying.")
        return result


def remember_connection(root: Path, client: StudioClient, result: dict):
    studio = result["studio"]
    import uuid
    identifier = str(uuid.UUID(studio["id"]))
    certificate = root / "client-certificates" / f"{identifier}.crt"
    certificate.parent.mkdir(parents=True, exist_ok=True)
    if certificate.exists() and certificate.read_bytes() != client.der:
        raise ConnectionError("The remembered studio CA changed. Nothing was overwritten.")
    certificate.write_bytes(client.der)  # Public certificate only, never a host key.
    prefs = load_preferences(root)
    prefs.update(studio_mode="connect", connection={"url": client.url, "id": identifier, "name": studio["name"],
                                                   "ca": str(certificate), "ca_sha256": client.fingerprint,
                                                   "token": result["token"]})
    write_json_atomic(root / "installation.json", prefs)
