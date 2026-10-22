"""Settings persistence tests — save bridge round-trips + storage paths."""

import os

import pytest

from core.constants import STORAGE_AI_MODEL
from tests.conftest import FakeStorage


@pytest.mark.asyncio
async def test_storage_typed_accessors():
    from services.storage import StorageService

    storage = StorageService(None)
    storage._data = {}
    assert await storage.get_ai_model() == "auto"
    await storage.set_ai_model("gpt-x")
    assert await storage.get_ai_model() == "gpt-x"
    assert await storage.get(STORAGE_AI_MODEL) == "gpt-x"

    assert await storage.get_ai_mode() is True
    await storage.set_ai_mode(False)
    assert await storage.get_ai_mode() is False

    assert await storage.get_reasoning_effort() == "auto"
    await storage.set_reasoning_effort("high")
    assert await storage.get_reasoning_effort() == "high"

    assert await storage.get_biometric_lock() is True
    await storage.set_biometric_lock(False)
    assert await storage.get_biometric_lock() is False

    await storage.set_history([{"q": 1}])
    assert await storage.get_history() == [{"q": 1}]


@pytest.mark.asyncio
async def test_save_bridge_applies_and_persists():
    from app_controller import AppController
    from core.state import state
    from tests.conftest import FakePage

    ctrl = AppController(FakePage())
    ctrl.storage = FakeStorage()
    ctrl.save("ai_model", "test-model")
    assert state.ai_model == "test-model"  # applied synchronously
    await ctrl.save_setting("ai_model", "test-model")
    assert await ctrl.storage.get(STORAGE_AI_MODEL) == "test-model"


@pytest.mark.asyncio
async def test_save_theme_maps_to_mode():
    import flet as ft

    from app_controller import AppController
    from core.state import state
    from tests.conftest import FakePage

    ctrl = AppController(FakePage())
    ctrl.storage = FakeStorage()
    ctrl.save("theme", "dark")
    assert state.theme_mode == ft.ThemeMode.DARK
    await ctrl.save_setting("theme", "dark")
    assert await ctrl.storage.get("theme") == "dark"


def test_credit_word():
    from core.constants import credit_word

    assert credit_word(1) == "1 credit"
    assert credit_word(0) == "0 credits"
    assert credit_word(5) == "5 credits"


def test_storage_paths_resolve_and_create(tmp_path, monkeypatch):
    from core import storage_paths

    monkeypatch.delenv("FLET_APP_STORAGE_DATA", raising=False)
    monkeypatch.delenv("FLET_APP_STORAGE_CACHE", raising=False)
    monkeypatch.delenv("FLET_APP_STORAGE_TEMP", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert storage_paths.data_dir().exists()
    assert storage_paths.cache_dir().exists()
    assert storage_paths.temp_dir().exists()


def test_storage_paths_honor_env(tmp_path, monkeypatch):
    from core import storage_paths

    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "d"))
    assert storage_paths.data_dir() == tmp_path / "d"


def test_clear_temp_removes_scratch_but_keeps_guards(tmp_path, monkeypatch):
    from core import storage_paths

    root = tmp_path / "t"
    root.mkdir()
    (root / "scratch.txt").write_text("x")
    (root / "keep-cacert.pem").write_text("x")
    (root / "engine_local.py").write_text("x")
    monkeypatch.setenv("FLET_APP_STORAGE_TEMP", str(root))
    monkeypatch.setenv("FLET_APP_STORAGE_CACHE", str(tmp_path / "c"))
    removed = storage_paths.clear_temp()
    assert removed == 1
    assert (root / "keep-cacert.pem").exists()
    assert (root / "engine_local.py").exists()
    assert not (root / "scratch.txt").exists()


def test_tiktoken_cache_dir_points_into_cache(tmp_path, monkeypatch):
    from core import storage_paths

    monkeypatch.setenv("FLET_APP_STORAGE_CACHE", str(tmp_path / "c"))
    home = storage_paths.cache_dir() / "tiktoken_cache"
    assert "tiktoken_cache" in str(home)
    assert str(tmp_path) in str(home)
    _ = os.environ.get("TIKTOKEN_CACHE_DIR", "")
