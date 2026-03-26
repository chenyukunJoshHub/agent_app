"""SSRF protection for HTTP fetch tool.

Validates URLs before allowing HTTP requests, preventing access to
internal services, cloud metadata endpoints, and private networks.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6 addresses
]

ALLOWED_SCHEMES = {"http", "https"}

RESOLVED_LOCALHOSTS = frozenset({"localhost", "localhost.localdomain"})


class UnsafeURLError(ValueError):
    """Raised when a URL fails SSRF safety checks."""


def _is_ip_blocked(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in network for network in BLOCKED_RANGES)
    except ValueError:
        return False


def _is_ip_blocked_any(hostname: str) -> bool:
    try:
        addrinfo = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _socktype, _proto, _canonname, sockaddr in addrinfo:
            ip_str = str(sockaddr[0])  # Convert to string to handle both IPv4 and IPv6
            if _is_ip_blocked(ip_str):
                return True
    except socket.gaierror:
        raise UnsafeURLError(f"Cannot resolve hostname: {hostname}")
    return False


def is_safe_url(url: str) -> bool:
    if not url or not url.strip():
        raise UnsafeURLError("URL is empty")

    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"URL scheme '{parsed.scheme}' is not allowed. Use http:// or https://")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname")

    if hostname.lower() in RESOLVED_LOCALHOSTS:
        raise UnsafeURLError("Access to localhost is not allowed (private network)")

    if _is_ip_blocked_any(hostname):
        raise UnsafeURLError(
            f"Resolved IP for '{hostname}' belongs to a private/blocked network range"
        )

    return True


__all__ = ["is_safe_url", "UnsafeURLError"]
