"""Version discipline — pyproject is truth, feed never ahead, changelog synced.

Ported from DDGS test_version_discipline.py + KTV's changelog guards
(the house standard).
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)


def _version_json() -> dict:
    with open(ROOT / "version.json", encoding="utf-8") as handle:
        return json.load(handle)


def test_pyproject_version_shape():
    data = _pyproject()
    version = data["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"bad version {version!r}"
    assert isinstance(data["tool"]["flet"]["build_number"], int)


def test_app_constants_match_pyproject():
    from core.constants import APP_BUILD_NUMBER, APP_VERSION, USER_AGENT

    data = _pyproject()
    assert data["project"]["version"] == APP_VERSION
    assert data["tool"]["flet"]["build_number"] == APP_BUILD_NUMBER
    assert APP_VERSION in USER_AGENT


def test_feed_never_ahead():
    """version.json may be held back (lower) for staged rollouts, never ahead."""
    data = _pyproject()
    feed = _version_json()
    assert feed["build_number"] <= data["tool"]["flet"]["build_number"], "feed build_number is ahead of the app — hold the feed back, never forward"


def test_changelog_has_entry_for_current_version():
    from core.changelog import CHANGELOG, notes_for
    from core.constants import APP_VERSION

    assert APP_VERSION in CHANGELOG, "add a CHANGELOG entry when bumping the version"
    assert notes_for(APP_VERSION).strip(), "changelog entry must not be empty"


def test_notes_for_unknown_version_falls_back():
    from core.changelog import notes_for

    assert notes_for("0.0.0-nope").strip(), "fallback must return the latest entry"


def test_play_url_carries_bundle_id():
    from core.constants import PLAYSTORE_URL

    assert "id=ng.kiri.akili" in PLAYSTORE_URL


def test_update_feed_url_points_at_akili_app():
    from core.constants import UPDATE_CONFIG_URL

    assert "Nwokike/akili-app" in UPDATE_CONFIG_URL
    assert UPDATE_CONFIG_URL.endswith("version.json")


def test_no_test_ad_ids_in_production_config():
    """The AdMob guard: test unit IDs must never ship in constants."""
    from core.constants import AD_BANNER_UNIT_ID, AD_INTERSTITIAL_UNIT_ID

    for unit in (AD_BANNER_UNIT_ID, AD_INTERSTITIAL_UNIT_ID):
        assert "3940256099942544" not in unit, f"test ad unit shipped: {unit}"


def test_github_repo_points_at_akili_app():
    from core.constants import GITHUB_REPO_URL

    assert GITHUB_REPO_URL == "https://github.com/Nwokike/akili-app"


@pytest.mark.skipif(not (ROOT / ".github" / "workflows" / "build-all.yml").exists(), reason="CI workflow not yet added")
def test_ci_gate_present():
    text = (ROOT / ".github" / "workflows" / "build-all.yml").read_text(encoding="utf-8")
    assert "ruff" in text
    assert "pytest" in text
