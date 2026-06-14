"""Generate a self-signed TLS certificate for local development."""

import argparse
import datetime
import os
import sys

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print("Install cryptography: pip install cryptography")
    sys.exit(1)


def generate_self_signed_cert(
    cert_path: str = "cert.pem",
    key_path: str = "key.pem",
    hostname: str = "localhost",
    days: int = 365,
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "RemoteDesktop Dev"),
    ])

    san = x509.SubjectAlternativeName([
        x509.DNSName(hostname),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=days)
        )
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )

    print(f"Certificate: {os.path.abspath(cert_path)}")
    print(f"Private key: {os.path.abspath(key_path)}")
    print(f"Valid for {days} days")


if __name__ == "__main__":
    import ipaddress

    parser = argparse.ArgumentParser(description="Generate self-signed TLS certificate")
    parser.add_argument("--cert", default="cert.pem", help="Certificate output path")
    parser.add_argument("--key", default="key.pem", help="Private key output path")
    parser.add_argument("--hostname", default="localhost", help="Certificate hostname")
    parser.add_argument("--days", type=int, default=365, help="Validity period in days")
    args = parser.parse_args()

    generate_self_signed_cert(args.cert, args.key, args.hostname, args.days)
