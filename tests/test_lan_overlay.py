import ipaddress
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_app
from server.network import discover_local_ips
from server.scoreboard_state import State
from scripts import generate_certificate as certificates


def test_lan_route_is_preferred_over_vpn_and_virtual_adapter(monkeypatch):
    monkeypatch.setattr("server.network.socket.getaddrinfo", lambda *a: [
        (None, None, None, None, (ip, 0)) for ip in
        ["100.64.0.2", "192.168.56.1", "192.168.1.10", "127.0.0.1", "169.254.1.1"]
    ])
    monkeypatch.setattr("server.network.socket.socket", lambda *a: SimpleNamespace(
        connect=lambda address: None, getsockname=lambda: ("192.168.1.10", 0), close=lambda: None
    ))
    assert discover_local_ips() == ["192.168.1.10", "192.168.56.1", "100.64.0.2"]


@pytest.mark.parametrize("secure", [True, False])
def test_overlay_and_umpire_use_same_lan_server_and_tls(tmp_path, secure):
    cert, key = tmp_path / "server.crt", tmp_path / "server.key"
    cert.touch()
    key.touch()
    settings = Settings(database_path=tmp_path / "drs.db", port=8765,
                        ssl_certfile=cert if secure else None, ssl_keyfile=key if secure else None)
    app = create_app(settings, scoreboard=State(tmp_path / "scores"))
    with patch("server.main.discover_local_ips", return_value=["192.168.1.10", "192.168.56.1"]), \
            patch("server.main.start_receiver"), TestClient(app) as client:
        info = client.get("/api/server-info").json()
        base = f"{'https' if secure else 'http'}://192.168.1.10:8765"
        assert info["camera_url"] == base + "/camera"
        assert info["overlay_url"] == base + "/overlay"
        assert info["broadcast_urls"][0] == base + "/broadcast"
        status = client.get("/api/app-status").json()
        assert status["umpire_urls"][0] == base + "/umpire"
        assert status["overlay_urls"] == info["overlay_urls"]
        assert status["certificate_url"] == ("/local-ca.crt" if secure else None)
        assert client.get("/overlay").status_code == 200
        assert 'id="overlayAddress"' in client.get("/scoreboard").text
        assert "location.origin+'/overlay'" not in client.get("/control.js").text


def test_server_certificate_refresh_preserves_ca_and_private_keys(tmp_path, monkeypatch):
    for name, filename in [("CERTS", None), ("CA_KEY", "rootCA.key.pem"), ("CA_CERT", "rootCA.crt"),
                           ("SERVER_KEY", "server.key.pem"), ("SERVER_CERT", "server.crt")]:
        monkeypatch.setattr(certificates, name, tmp_path if filename is None else tmp_path / filename)
    monkeypatch.setattr(certificates, "local_addresses", lambda: [ipaddress.ip_address("127.0.0.1")])
    certificates.main([])
    unchanged = {path: path.read_bytes() for path in
                 [certificates.CA_CERT, certificates.CA_KEY, certificates.SERVER_KEY]}
    original_server_cert = certificates.SERVER_CERT.read_bytes()
    monkeypatch.setattr(certificates, "local_addresses", lambda: [
        ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("192.168.1.10")])
    certificates.main(["--reuse-ca"])
    assert all(path.read_bytes() == contents for path, contents in unchanged.items())
    assert certificates.SERVER_CERT.with_suffix(".crt.previous").read_bytes() == original_server_cert
    updated = certificates.load_certificate(certificates.SERVER_CERT)
    assert ipaddress.ip_address("192.168.1.10") in updated.extensions.get_extension_for_class(
        x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
    assert updated.issuer == certificates.load_certificate(certificates.CA_CERT).subject
