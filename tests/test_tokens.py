"""Verify all tokens are positive integers."""

from core import tokens


def test_font_tokens_positive():
    for name in dir(tokens):
        if name.startswith("FONT_") and not name.startswith("FONT_FAMILY_"):
            val = getattr(tokens, name)
            assert isinstance(val, int) and val > 0, f"{name} must be positive int"


def test_space_tokens_positive():
    for name in dir(tokens):
        if name.startswith("SPACE_"):
            val = getattr(tokens, name)
            assert isinstance(val, int) and val > 0, f"{name} must be positive int"


def test_radius_tokens_positive():
    for name in dir(tokens):
        if name.startswith("RADIUS_"):
            val = getattr(tokens, name)
            assert isinstance(val, int) and val > 0, f"{name} must be positive int"


def test_icon_tokens_positive():
    for name in dir(tokens):
        if name.startswith("ICON_"):
            val = getattr(tokens, name)
            assert isinstance(val, int) and val > 0, f"{name} must be positive int"


def test_anim_tokens_positive():
    for name in dir(tokens):
        if name.startswith("ANIM_"):
            val = getattr(tokens, name)
            assert isinstance(val, int) and val > 0, f"{name} must be positive int"


def test_opacity_tokens_range():
    for name in dir(tokens):
        if name.startswith("OPACITY_"):
            val = getattr(tokens, name)
            assert isinstance(val, (int, float)) and 0 <= val <= 1, f"{name} must be 0-1"
