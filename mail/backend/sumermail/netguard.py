"""الاتصال بخوادم IMAP/SMTP يحددها المستخدم بأمان: نمنع الوصول للشبكات الداخلية (SSRF)
ونثبّت عنوان IP بعد التحقق، مع إبقاء اسم الخادم للتحقق من شهادة TLS."""

import imaplib
import ipaddress
import smtplib
import socket
import ssl

from .config import settings

ALLOWED_IMAP_PORTS = {993}
ALLOWED_SMTP_PORTS = {465, 587}


class NetError(Exception):
    pass


def _public(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return a.is_global and not a.is_multicast


def resolve(host: str, port: int) -> str:
    host = (host or "").strip().rstrip(".").lower()
    if not host or len(host) > 253 or any(c in host for c in "/@:\\ "):
        raise NetError("bad_host")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise NetError("dns")
    ips = [i[4][0] for i in infos]
    if not ips:
        raise NetError("dns")
    for ip in ips:
        if not settings.allow_private and not _public(ip):
            raise NetError("private")
    return ips[0]


def check_port(port: int, kind: str):
    allowed = ALLOWED_IMAP_PORTS if kind == "imap" else ALLOWED_SMTP_PORTS
    if port not in allowed and not settings.allow_private:
        raise NetError("port")


def tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if settings.insecure_tls:  # تطوير فقط (يمنعه config.check في الإنتاج)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


class PinnedIMAP4_SSL(imaplib.IMAP4_SSL):
    """IMAP عبر TLS إلى عنوان IP محدد مسبقاً، مع التحقق من الشهادة باسم الخادم الأصلي."""

    def __init__(self, host: str, port: int, ip: str, timeout: float):
        self._pinned_ip = ip
        super().__init__(host, port, ssl_context=tls_context(), timeout=timeout)

    def _create_socket(self, timeout):
        sock = socket.create_connection((self._pinned_ip, self.port), timeout)
        return self.ssl_context.wrap_socket(sock, server_hostname=self.host)


class PinnedSMTP_SSL(smtplib.SMTP_SSL):
    def __init__(self, host: str, port: int, ip: str, timeout: float):
        self._pinned_ip = ip
        super().__init__(host, port, timeout=timeout, context=tls_context())

    def _get_socket(self, host, port, timeout):
        sock = socket.create_connection((self._pinned_ip, port), timeout)
        return self.context.wrap_socket(sock, server_hostname=self._host)


class PinnedSMTP(smtplib.SMTP):
    """SMTP على 587 مع STARTTLS إلزامي."""

    def __init__(self, host: str, port: int, ip: str, timeout: float):
        self._pinned_ip = ip
        super().__init__(host, port, timeout=timeout)

    def _get_socket(self, host, port, timeout):
        return socket.create_connection((self._pinned_ip, port), timeout)
