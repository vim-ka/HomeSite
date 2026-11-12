"""Internet probe: TCP connect to any of the targets."""

import asyncio

import pytest

from app.services.internet_probe import default_router, reachable


async def _free_port() -> int:
    s = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = s.sockets[0].getsockname()[1]
    s.close()
    await s.wait_closed()
    return port


@pytest.mark.asyncio
async def test_reachable_any_target():
    closed = f"127.0.0.1:{await _free_port()}"
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    try:
        open_ = f"127.0.0.1:{server.sockets[0].getsockname()[1]}"
        assert await reachable([closed, open_], timeout=1) is True
        assert await reachable([closed], timeout=1) is True   # refused = a live host answered
        assert await reachable([f"10.255.255.1:{await _free_port()}"], timeout=0.3) is False
        assert await reachable([], timeout=1) is False
    finally:
        server.close()
        await server.wait_closed()


def test_default_router_shape():
    r = default_router()
    assert r is None or r.endswith(":80")


def test_target_adds_the_default_port_and_rejects_garbage():
    from app.services.internet_probe import target

    assert target("ya.ru", 443) == "ya.ru:443"
    assert target(" 1.1.1.1:53 ", 443) == "1.1.1.1:53"
    assert target("192.168.55.1", 80) == "192.168.55.1:80"
    for bad in ("", "  ", "ya.ru:abc", "ya.ru:0", "ya.ru:70000", ":53", "a:b:c"):
        assert target(bad, 443) is None, bad


def test_default_router_survives_a_short_route_line():
    from unittest.mock import mock_open, patch

    table = "Iface\tDestination\tGateway\tFlags\n" "eth0\t00000000\t0137A8C0\n" "eth1\t00000000\t0137A8C0\t0003\n"
    with patch("app.services.internet_probe.open", mock_open(read_data=table), create=True):
        assert default_router() == "192.168.55.1:80"
    with patch("app.services.internet_probe.open", mock_open(read_data=table.rsplit("\n", 2)[0] + "\n"), create=True):
        assert default_router() is None
