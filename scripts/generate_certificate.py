from __future__ import annotations

import ipaddress
import argparse
import socket
import sys
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


ROOT = Path(__file__).resolve().parents[1]
CERTS = ROOT / "certs"
CA_KEY = CERTS / "rootCA.key.pem"
CA_CERT = CERTS / "rootCA.crt"
SERVER_KEY = CERTS / "server.key.pem"
SERVER_CERT = CERTS / "server.crt"


def local_addresses() -> list[ipaddress.IPv4Address]:
    sys.path.insert(0, str(ROOT))
    from server.network import discover_local_ips

    values = {ipaddress.ip_address("127.0.0.1")}
    values.update(ipaddress.ip_address(value) for value in discover_local_ips())
    return sorted(values, key=int)


def public_key_bytes(key: rsa.RSAPrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def ca_name(key: rsa.RSAPrivateKey) -> x509.Name:
    identifier = sha256(public_key_bytes(key)).hexdigest()[:8].upper()
    return x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, f"Backyard DRS Local CA {identifier}")]
    )


def create_ca_certificate(key: rsa.RSAPrivateKey) -> x509.Certificate:
    name = ca_name(key)
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )


def load_certificate(path: Path) -> x509.Certificate:
    data = path.read_bytes()
    try:
        return x509.load_der_x509_certificate(data)
    except ValueError:
        return x509.load_pem_x509_certificate(data)


def load_or_create_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    if CA_KEY.exists():
        key = serialization.load_pem_private_key(CA_KEY.read_bytes(), password=None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)

    certificate: x509.Certificate | None = None
    if CA_CERT.exists():
        try:
            candidate = load_certificate(CA_CERT)
            same_key = candidate.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ) == public_key_bytes(key)
            if same_key and candidate.subject == ca_name(key):
                certificate = candidate
        except (ValueError, TypeError):
            pass

    # Legacy releases reused one CA display name across different keys. Reissuing
    # with a key-derived name prevents browsers selecting the wrong trusted CA.
    if certificate is None:
        certificate = create_ca_certificate(key)

    CA_KEY.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    # DER is accepted consistently by Windows, Android, and iOS certificate UIs.
    CA_CERT.write_bytes(certificate.public_bytes(serialization.Encoding.DER))
    return key, certificate


def reuse_existing_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    """Refresh a server certificate without changing an already trusted CA."""
    if not CA_KEY.exists() or not CA_CERT.exists():
        raise RuntimeError("Existing CA certificate/key missing. Run initial setup first.")
    key = serialization.load_pem_private_key(CA_KEY.read_bytes(), password=None)
    certificate = load_certificate(CA_CERT)
    if certificate.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ) != public_key_bytes(key):
        raise RuntimeError("Existing CA certificate and key do not match; nothing was replaced.")
    if not certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise RuntimeError("Existing certificate is not a certificate authority.")
    if not certificate.not_valid_before_utc <= datetime.now(timezone.utc) < certificate.not_valid_after_utc:
        raise RuntimeError("Existing CA is not currently valid; nothing was replaced.")
    return key, certificate


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the local Studio HTTPS certificate.")
    parser.add_argument("--reuse-ca", action="store_true", help="Keep the existing CA and server key unchanged.")
    args = parser.parse_args(argv)
    CERTS.mkdir(parents=True, exist_ok=True)
    ca_key, ca_certificate = reuse_existing_ca() if args.reuse_ca else load_or_create_ca()
    server_key = (serialization.load_pem_private_key(SERVER_KEY.read_bytes(), password=None)
                  if args.reuse_ca and SERVER_KEY.exists()
                  else rsa.generate_private_key(public_exponent=65537, key_size=2048))
    hostname = socket.gethostname()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    dns_names = sorted({"localhost", hostname})
    alternatives: list[x509.GeneralName] = [
        *(x509.DNSName(name) for name in dns_names),
        *(x509.IPAddress(address) for address in local_addresses()),
    ]
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_certificate.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alternatives), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    if not args.reuse_ca or not SERVER_KEY.exists():
        SERVER_KEY.write_bytes(
            server_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    if args.reuse_ca and SERVER_CERT.exists():
        # The old public server certificate is recoverable; private keys stay unchanged.
        SERVER_CERT.with_suffix(".crt.previous").write_bytes(SERVER_CERT.read_bytes())
    SERVER_CERT.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    print("Created local HTTPS certificate for:")
    for item in alternatives:
        print(f"  {item.value}")
    print(f"Local CA certificate: {CA_CERT}")
    print(f"Certificate authority: {ca_certificate.subject.rfc4514_string()}")


if __name__ == "__main__":
    main()
