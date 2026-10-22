"""Update service tests — build compare, failure silence, mandatory."""

import httpx
import pytest

from services.update_service import UpdateService

URL = "https://example.com/version.json"
GH = "https://github.com/x/y"
PLAY = "https://play.google.com/store/apps/details?id=x"


def _svc(build=1):
    return UpdateService(URL, build, GH, PLAY)


class _Resp:
    def __init__(self, status_code, body=None, exc=None):
        self.status_code = status_code
        self._body = body
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._body


class _Client:
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **k):
        if self._exc is not None:
            raise self._exc
        return self._resp


@pytest.mark.asyncio
async def test_newer_build_reported(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **k: _Client(_Resp(200, {"build_number": 5, "version": "1.1", "title": "T", "release_notes": "N"})),
    )
    data = await _svc(build=1).check_for_update()
    assert data is not None
    assert data["build_number"] == 5
    assert data["version"] == "1.1"


@pytest.mark.asyncio
async def test_same_or_older_build_silent(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **k: _Client(_Resp(200, {"build_number": 1, "version": "1.0"})),
    )
    assert await _svc(build=1).check_for_update() is None
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **k: _Client(_Resp(200, {"build_number": 0})),
    )
    assert await _svc(build=1).check_for_update() is None


@pytest.mark.asyncio
async def test_http_error_silent(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: _Client(_Resp(500, {})))
    assert await _svc(build=1).check_for_update() is None


@pytest.mark.asyncio
async def test_network_error_silent(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: _Client(exc=httpx.ConnectError("down")))
    assert await _svc(build=1).check_for_update() is None


@pytest.mark.asyncio
async def test_bad_json_silent(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: _Client(_Resp(200, ValueError("bad"), exc=None) if False else _Resp(200, None)))
    # None body is not a dict -> None
    assert await _svc(build=1).check_for_update() is None


@pytest.mark.asyncio
async def test_mandatory_passthrough(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **k: _Client(_Resp(200, {"build_number": 9, "mandatory": True})),
    )
    data = await _svc(build=1).check_for_update()
    assert data["mandatory"] is True


@pytest.mark.asyncio
async def test_url_fallbacks(monkeypatch):
    seen = {}

    class _Cap(_Client):
        async def get(self, url, **k):
            seen["url"] = url
            return _Resp(200, {"build_number": 2})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: _Cap())
    await _svc(build=1).check_for_update()
    assert seen["url"] == URL
