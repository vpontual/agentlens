"""Block requests to internal addresses.

agentlens fetches any URL it is handed and runs with `network_mode: host`, so
before this it could be pointed at anything reachable from the docker host —
Postgres on :5433, the veepass API, a router admin page — and would return the
body. It validated only the URL scheme.

That matters more than it would for a normal service, because two of its
callers are LLM agent tools (llama_rider's `agentlens` tool and vcode's
`web_fetch`). A prompt injection in any page an agent reads can name a
follow-up URL, so "who can call agentlens" is not the same question as "what
URLs can reach it".

Requiring authentication would not fix that: the agents are legitimate callers
and would hold valid credentials. Restricting the *destination* is the fix.

Empirically safe: over the 7 days before this was written agentlens parsed 244
distinct hosts and **zero** private addresses.

Careful with split-horizon DNS. VP's own hostnames resolve to private IPs
(`agentlens.casavp.com`, `llm-api.casarp.us`, `finance.casavp.com` -> 10.x), so
a blanket private-range block would refuse them. `AGENTLENS_ALLOW_HOSTS` exists
for exactly that: a comma-separated hostname allowlist, checked before DNS.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

# Hostnames permitted to resolve to private addresses. Comma-separated.
ALLOW_HOSTS = {
    h.strip().lower()
    for h in os.environ.get("AGENTLENS_ALLOW_HOSTS", "").split(",")
    if h.strip()
}


class BlockedTarget(Exception):
    """The URL resolves somewhere we refuse to fetch."""


def _addr_is_forbidden(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        # Unparseable — refuse rather than guess.
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local  # 169.254.x, incl. cloud metadata endpoints
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def check_url(url: str) -> None:
    """Raise BlockedTarget if `url` points at an internal address.

    Resolves the hostname rather than pattern-matching the string: `10.0.0.1`,
    `0x0a000001`, a hostname with an A record pointing inside, and a DNS name
    that returns both a public and a private address are all the same attack,
    and only resolution catches them all. Every returned address must be
    acceptable — one internal answer is enough to refuse.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise BlockedTarget("URL has no host")

    if host in ALLOW_HOSTS:
        return

    # A literal IP needs no DNS.
    try:
        ipaddress.ip_address(host)
        if _addr_is_forbidden(host):
            raise BlockedTarget(f"refusing to fetch internal address {host}")
        return
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise BlockedTarget(f"could not resolve {host}") from exc

    for info in infos:
        ip = str(info[4][0])
        if _addr_is_forbidden(ip):
            raise BlockedTarget(f"{host} resolves to internal address {ip}")
