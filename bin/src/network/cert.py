import hashlib
import ipaddress
import logging
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

log = logging.getLogger("localsend")

# 获取本地 IP 地址
def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

### 证书管理类
class CertManager:
    def __init__(self, cert_dir: Path):
        self.cert_dir = cert_dir
        self.cert_path = cert_dir / "cert.pem"
        self.key_path = cert_dir / "key.pem"
    def ensure_cert(self) -> Tuple[str, str, str]:
        if not self.cert_path.exists() or not self.key_path.exists() or not self._has_san():
            self._generate()
        fingerprint = self._compute_fingerprint()
        return str(self.cert_path), str(self.key_path), fingerprint
    def _has_san(self) -> bool:
        try:
            cert = x509.load_pem_x509_certificate(self.cert_path.read_bytes())
            cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            return True
        except Exception:
            return False
    def _generate(self) -> None:
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "LocalSend"),
        ])
        san_entries: list = [x509.DNSName("localhost")]
        local_ip = _local_ip()
        try:
            san_entries.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        except Exception:
            pass
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName(san_entries),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )
        self.key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        self.cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        log.info("已生成自签名证书 (IP=%s): %s", local_ip, self.cert_path)
    def _compute_fingerprint(self) -> str:
        cert_data = self.cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)
        der = cert.public_bytes(serialization.Encoding.DER)
        return hashlib.sha256(der).hexdigest()
