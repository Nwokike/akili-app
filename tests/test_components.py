"""Smoke-test all components with FakePage."""

from components.app_header import AppHeader
from components.banner_ad import build_banner_ad
from components.empty_state import EmptyState
from components.section_header import SectionHeader
from components.stat_card import StatCard
from tests.flet_tree import walk, walk_buttons, walk_texts


def test_app_header_renders(fake_page):
    header = AppHeader(fake_page, title="Test", subtitle="Sub")
    controls = list(walk(header))
    assert len(controls) > 0


def test_app_header_has_theme_toggle(fake_page):
    header = AppHeader(fake_page)
    buttons = list(walk_buttons(header))
    assert len(buttons) >= 2  # theme toggle + settings


def test_empty_state_renders():
    es = EmptyState("Title", "Message", "Action", on_action=None)
    controls = list(walk(es))
    assert len(controls) > 0


def test_empty_state_has_action():
    es = EmptyState("Title", "Message", "Click Me", on_action=lambda e: None)
    buttons = list(walk_buttons(es))
    assert len(buttons) == 1


def test_section_header_renders():
    sh = SectionHeader("Test Section")
    texts = list(walk_texts(sh))
    assert len(texts) == 1


def test_stat_card_renders():
    sc = StatCard("Label", 42)
    controls = list(walk(sc))
    assert len(controls) > 0


def test_stat_card_large_value():
    sc = StatCard("Label", 12345)
    controls = list(walk(sc))
    assert len(controls) > 0


def test_banner_ad_renders(fake_page):
    ad = build_banner_ad(fake_page)
    assert ad is not None
