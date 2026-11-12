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
