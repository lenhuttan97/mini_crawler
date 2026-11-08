"""Policy Gate — kiểm tra URL/SSRF trước mọi kết nối mạng (P01 Item 3).

Chỉ cho phép http/https, từ chối user-info, scheme nguy hiểm, cổng không
cho phép và mọi địa chỉ IP private/loopback/link-local/multicast/reserved
(kể cả IPv6). Kiểm tra lại trước mỗi redirect để phòng DNS rebinding.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

# Các scheme được phép.
ALLOWED_SCHEMES = frozenset({"http", "https"})

# Các cổng web thông thường được phép.
ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})

# Mạng private/loopback/link-local/multicast/reserved (IPv4 + IPv6).
_PRIVATE_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("127.0.0.0/8"),  # loopback IPv4
    ipaddress.ip_network("10.0.0.0/8"),  # private IPv4
    ipaddress.ip_network("172.16.0.0/12"),  # private IPv4
    ipaddress.ip_network("192.168.0.0/16"),  # private IPv4
    ipaddress.ip_network("169.254.0.0/16"),  # link-local IPv4
    ipaddress.ip_network("224.0.0.0/4"),  # multicast IPv4
    ipaddress.ip_network("240.0.0.0/4"),  # reserved IPv4
    ipaddress.ip_network("0.0.0.0/8"),  # this network / this host
    ipaddress.ip_network("::1/128"),  # loopback IPv6
    ipaddress.ip_network("fc00::/7"),  # unique local IPv6
    ipaddress.ip_network("fe80::/10"),  # link-local IPv6
    ipaddress.ip_network("ff00::/8"),  # multicast IPv6
    ipaddress.ip_network("::/128"),  # unspecified IPv6
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
)


def _is_private_ip(ip_str: str) -> bool:
    """Trả True nếu chuỗi địa chỉ IP nằm trong mạng bị chặn."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def _resolve_host(host: str, port: int | None) -> list[str]:
    """Phân giải hostname thành danh sách địa chỉ IP (rỗng nếu không phân giải được)."""
    try:
        results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return []
    addresses: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in results:
        addresses.append(sockaddr[0])
    return addresses


def _check_url(url: str, is_redirect: bool = False) -> tuple[bool, str | None, str | None]:
    """Kiểm tra một URL đơn lẻ. Trả về (allowed, reason_code, reason_message)."""
    parts = urlsplit(url)

    # 1. Scheme phải được phép.
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return False, "scheme_not_allowed", f"scheme không được phép: {parts.scheme}"

    # 2. Không được chứa user-info.
    if parts.username is not None or parts.password is not None:
        return False, "scheme_not_allowed", "URL không được chứa user-info"

    # 3. Cổng phải được phép (mặc định theo scheme nếu không chỉ định).
    port = parts.port
    if port is None:
        port = 443 if parts.scheme.lower() == "https" else 80
    if port not in ALLOWED_PORTS:
        return False, "port_not_allowed", f"cổng không được phép: {port}"

    host = parts.hostname
    if not host:
        return False, "scheme_not_allowed", "URL không có hostname"

    ssrf_code = "ssrf_redirect_private_ip" if is_redirect else "ssrf_private_ip"

    # 4. Hostname là IP literal => kiểm tra ngay.
    if _is_private_ip(host):
        return False, ssrf_code, f"đích IP private/loopback: {host}"

    # 5. Hostname là tên miền => phân giải DNS và kiểm tra mọi địa chỉ.
    resolved = _resolve_host(host, port)
    for ip in resolved:
        if _is_private_ip(ip):
            return False, ssrf_code, f"hostname phân giải về IP private: {ip}"

    return True, None, None


@dataclass(frozen=True)
class PolicyCommand:
    """Lệnh đánh giá chính sách cho một lần gọi mạng."""

    url: str
    action: str
    caller_id: str
    redirect_target: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    """Kết quả của Policy Gate."""

    allowed: bool
    reason_code: str | None = None
    reason_message: str | None = None


class PolicyGate:
    """Cổng chính sách duy nhất trước mọi kết nối mạng (P01 §5.1)."""

    def evaluate(self, command: PolicyCommand) -> PolicyDecision:
        """Đánh giá chính sách cho command, bao gồm cả redirect_target nếu có."""
        allowed, reason_code, reason_message = _check_url(command.url)
        if not allowed:
            return PolicyDecision(False, reason_code, reason_message)

        if command.redirect_target is not None:
            allowed, reason_code, reason_message = _check_url(
                command.redirect_target, is_redirect=True
            )
            if not allowed:
                return PolicyDecision(False, reason_code, reason_message)

        return PolicyDecision(True, None, None)


def evaluate_policy(command: PolicyCommand) -> PolicyDecision:
    """Hàm tiện ích đánh giá chính sách (gateway duy nhất trước network)."""
    return PolicyGate().evaluate(command)
