"""Internet / router reachability probe: a TCP connect to any of the targets."""

import asyncio
import socket
import struct


def _split(target: str, default_port: int | None = None) -> tuple[str, int] | None:
    target = target.strip()
    if not target:
        return None
    host, sep, port = target.rpartition(":")
    if not sep:
        host, port = target, str(default_port or "")
    try:
        return host, int(port)
    except ValueError:
        return None


async def _connect(host: str, port: int, timeout: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except ConnectionRefusedError:
        return True       # an RST comes from a live host: the network path works
    except (OSError, TimeoutError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return True


async def reachable(targets: list[str], timeout: float = 3.0) -> bool:
    """`host:port` targets, probed concurrently; True as soon as one connection opens."""
    parsed = [p for t in targets if (p := _split(t))]
    tasks = [asyncio.ensure_future(_connect(h, p, timeout)) for h, p in parsed]
    try:
        for fut in asyncio.as_completed(tasks):
            if await fut:
                return True
        return False
    finally:
        for t in tasks:
            t.cancel()


def default_router() -> str | None:
    """The VM's default gateway from /proc/net/route as `host:80`; None when there is none."""
    try:
        with open("/proc/net/route", encoding="ascii") as f:
            next(f, None)
            for line in f:
                cols = line.split()
                if len(cols) > 2 and cols[1] == "00000000" and int(cols[3], 16) & 2:
                    return f"{socket.inet_ntoa(struct.pack('<L', int(cols[2], 16)))}:80"
    except (OSError, ValueError):
        pass
    return None


def target(raw: str, default_port: int) -> str | None:
    """`host[:port]` → `host:port` (no port → `default_port`); None when it can't be parsed."""
    raw = raw.strip()
    host, sep, port = raw.partition(":")
    if not host or ":" in port:
        return None
    if not sep:
        return f"{host}:{default_port}"
    return f"{host}:{int(port)}" if port.isdigit() and 1 <= int(port) <= 65535 else None
