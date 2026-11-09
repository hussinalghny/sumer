"""حارس الشبكة: يمنع الزاحف من الوصول للشبكات الداخلية (SSRF) ومن إعادة ربط DNS.

الآلية:
1. نحلّ اسم النطاق مرة واحدة، ونرفض إذا أي عنوان ناتج غير عام.
2. نتصل بالعنوان المفحوص نفسه (تثبيت IP)، مع Host وSNI باسم النطاق، فلا يمكن
   لخادم DNS أن يعطينا عنواناً عاماً للفحص ثم عنواناً داخلياً للاتصال.
3. كل تحويل (redirect) يمر بنفس الفحص من جديد.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from .config import settings

# عناوين ممنوعة صراحة حتى لو بدت عامة
_EXTRA_BLOCKED = [
    ipaddress.ip_network("100.64.0.0/10"),     # CGNAT
    ipaddress.ip_network("169.254.0.0/16"),    # link-local + metadata
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("fd00:ec2::254/128"), # AWS IMDS v6
    ipaddress.ip_network("64:ff9b::/96"),      # NAT64 قد يغلّف عناوين داخلية
]


class BlockedDestination(Exception):
    pass


def is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    if not addr.is_global or addr.is_multicast or addr.is_reserved or addr.is_loopback \
            or addr.is_link_local or addr.is_private or addr.is_unspecified:
        return False
    return not any(addr in net for net in _EXTRA_BLOCKED)


@dataclass
class ResolvedTarget:
    url: str
    host: str
    port: int
    ip: str


async def resolve(url: str, allowed_ports=(80, 443)) -> ResolvedTarget:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise BlockedDestination(f"scheme غير مسموح: {parts.scheme}")
    if parts.username or parts.password:
        raise BlockedDestination("بيانات دخول داخل الرابط غير مسموحة")
    host = parts.hostname
    if not host:
        raise BlockedDestination("رابط بدون نطاق")
    host = host.encode("idna").decode("ascii") if not host.isascii() else host.lower()
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in allowed_ports and not settings.allow_private_networks:
        raise BlockedDestination(f"المنفذ {port} غير مسموح")
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise BlockedDestination(f"تعذّر حلّ النطاق: {e}") from e
        ips = list(dict.fromkeys(i[4][0] for i in infos))
    if not ips:
        raise BlockedDestination("لا توجد عناوين")
    if not settings.allow_private_networks:
        bad = [ip for ip in ips if not is_public_ip(ip)]
        if bad:
            raise BlockedDestination(f"عنوان داخلي أو محجوز: {bad[0]}")
    return ResolvedTarget(url=url, host=host, port=port, ip=ips[0])


def pinned_request(client: httpx.AsyncClient, target: ResolvedTarget, headers: dict) -> httpx.Request:
    """طلب موجّه للـ IP المفحوص، مع Host/SNI الأصليين حتى يتحقق TLS من اسم النطاق."""
    parts = urlsplit(target.url)
    ip_host = f"[{target.ip}]" if ":" in target.ip else target.ip
    default = (parts.scheme == "https" and target.port == 443) or (parts.scheme == "http" and target.port == 80)
    netloc = ip_host if default else f"{ip_host}:{target.port}"
    pinned = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    host_header = target.host if default else f"{target.host}:{target.port}"
    req = client.build_request("GET", pinned, headers={**headers, "Host": host_header})
    if parts.scheme == "https":
        req.extensions["sni_hostname"] = target.host
    return req


@dataclass
class FetchResult:
    url: str            # الرابط النهائي بعد التحويلات
    status: int
    headers: httpx.Headers
    content: bytes
    redirects: list
    truncated: bool


async def safe_fetch(client: httpx.AsyncClient, url: str, headers: dict, max_bytes: int,
                     max_redirects: int = 5, allowed_ports=(80, 443)) -> FetchResult:
    redirects = []
    current = url
    for _ in range(max_redirects + 1):
        target = await resolve(current, allowed_ports)
        req = pinned_request(client, target, headers)
        resp = await client.send(req, stream=True, follow_redirects=False)
        try:
            if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                nxt = httpx.URL(current).join(resp.headers["location"])
                redirects.append((current, resp.status_code))
                current = str(nxt.copy_with(fragment=None))
                continue
            chunks, size, truncated = [], 0, False
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    truncated = True
                    break
                chunks.append(chunk)
            return FetchResult(current, resp.status_code, resp.headers, b"".join(chunks), redirects, truncated)
        finally:
            await resp.aclose()
    raise BlockedDestination("تحويلات كثيرة")
