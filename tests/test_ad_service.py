"""Ad service tests — gates, lifecycle, privacy outcomes."""

import pytest

from core.state import state
from services.ad_service import AdService
from tests.conftest import FakePage


class _Mobile:
    def is_mobile(self):
        return True


class _Desktop:
    def is_mobile(self):
        return False


def _page(mobile=True):
    page = FakePage()
    page.web = False
    page.platform = _Mobile() if mobile else _Desktop()
    return page


@pytest.fixture(autouse=True)
def _reset():
    state.is_premium = False
    yield
    state.is_premium = False


def test_gated_off_for_premium():
    svc = AdService(_page(mobile=True))
    state.is_premium = True
    assert svc._gated() is False
    assert svc.build_banner() is None


def test_gated_off_desktop():
    svc = AdService(_page(mobile=False))
    assert svc._gated() is False
    assert svc.build_banner() is None


def test_gated_off_no_consent():
    svc = AdService(_page(mobile=True))
    svc._can_request_ads = False
    assert svc._gated() is False


def test_unit_ids_production_by_default():
    svc = AdService(_page())
    assert "3940256099942544" not in svc.banner_unit_id()
    assert "3940256099942544" not in svc.interstitial_unit_id()


@pytest.mark.asyncio
async def test_gather_consent_offline_desktop_allows():
    svc = AdService(_page(mobile=False))
    await svc.gather_consent()
    assert svc._can_request_ads is True


@pytest.mark.asyncio
async def test_gather_consent_without_package_denies(monkeypatch):
    import services.ad_service as mod

    monkeypatch.setattr(mod, "_HAS_ADS", False)
    svc = AdService(_page(mobile=True))
    await svc.gather_consent()
    assert svc._can_request_ads is False


@pytest.mark.asyncio
async def test_show_interstitial_gated():
    svc = AdService(_page(mobile=False))
    assert await svc.show_interstitial() is False


@pytest.mark.asyncio
async def test_privacy_options_no_manager():
    svc = AdService(_page())
    assert await svc.show_privacy_options() == "no_manager"


def test_close_releases_services():
    svc = AdService(_page())
    sentinel = object()
    svc._consent_manager = sentinel
    svc.page.services.append(sentinel)
    svc.close()
    assert sentinel not in svc.page.services
    assert svc._consent_manager is None
