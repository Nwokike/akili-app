"""Control tree walker — test helpers for asserting on component trees.

Ported from Sherlock's flet_tree pattern (the house standard).
DFS through controls + content, with typed walkers for buttons, icons, texts.
"""

from __future__ import annotations

from collections.abc import Iterator

import flet as ft


def walk(control) -> Iterator[ft.Control]:
    """DFS through a control tree, yielding every control."""
    if control is None:
        return
    yield control
    # Recurse into content
    content = getattr(control, "content", None)
    if content is not None:
        if isinstance(content, ft.Control):
            yield from walk(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, ft.Control):
                    yield from walk(item)
    # Recurse into controls
    controls = getattr(control, "controls", None)
    if controls is not None:
        if isinstance(controls, ft.Control):
            yield from walk(controls)
        elif isinstance(controls, list):
            for item in controls:
                if isinstance(item, ft.Control):
                    yield from walk(item)


def walk_buttons(control) -> Iterator[ft.Control]:
    """Yield all Button-like controls in the tree."""
    for c in walk(control):
        if isinstance(c, (ft.Button, ft.TextButton, ft.OutlinedButton, ft.FilledButton, ft.IconButton)):
            yield c


def walk_icons(control) -> Iterator[ft.Control]:
    """Yield all Icon and IconButton controls in the tree."""
    for c in walk(control):
        if isinstance(c, (ft.Icon, ft.IconButton)):
            yield c


def walk_texts(control) -> Iterator[ft.Control]:
    """Yield all Text controls in the tree."""
    for c in walk(control):
        if isinstance(c, ft.Text):
            yield c


def walk_containers(control) -> Iterator[ft.Control]:
    """Yield all Container controls in the tree."""
    for c in walk(control):
        if isinstance(c, ft.Container):
            yield c


def find_button_by_label(control, label: str) -> ft.Control | None:
    """Find a button by its label text."""
    for btn in walk_buttons(control):
        content = getattr(btn, "content", None)
        if isinstance(content, ft.Text) and content.value == label:
            return btn
        if isinstance(content, str) and content == label:
            return btn
    return None


def find_icon(control, icon_name: str) -> ft.Control | None:
    """Find an icon by its name."""
    for ic in walk_icons(control):
        if getattr(ic, "icon", None) == icon_name:
            return ic
    return None
