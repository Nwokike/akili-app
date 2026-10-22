"""Settings component smoke tests — kit, sections, screen assembly."""

import flet as ft

from components.settings_kit import setting_row, settings_card
from tests.flet_tree import walk, walk_texts


def test_setting_row_renders():
    row = setting_row(ft.Icons.SCHOOL_ROUNDED, "Title", "Subtitle", ft.Switch(value=True))
    texts = [t.value for t in walk_texts(row)]
    assert "Title" in texts


def test_setting_row_none_trailing():
    row = setting_row(ft.Icons.SCHOOL_ROUNDED, "Title", "Subtitle", None)
    assert list(walk(row))


def test_setting_row_tappable():
    seen = []
    row = setting_row(ft.Icons.SCHOOL_ROUNDED, "Title", "Sub", None, on_click=lambda e: seen.append(1))
    assert row.on_click is not None
    row.on_click(None)
    assert seen == [1]


def test_settings_card_dividers():
    card = settings_card(
        [
            setting_row(ft.Icons.ABC_ROUNDED, "A", "a", None),
            setting_row(ft.Icons.ABC_ROUNDED, "B", "b", None),
        ]
    )
    dividers = [c for c in walk(card) if isinstance(c, ft.Divider)]
    assert len(dividers) == 1


def test_mcp_section_helpers():
    from agent.mcp_hub import MCPHub, builtin_exa_server, builtin_parallel_server
    from components.settings.sections_mcp import _builtin, _exa, _exa_tools, _server_tools

    hub = MCPHub(servers=[builtin_exa_server(), builtin_parallel_server()])
    exa, parallel = _builtin(hub)
    assert exa is not None and parallel is not None
    assert parallel.url == "https://search.parallel.ai/mcp"
    assert parallel.builtin is True
    assert _exa(hub) is not None
    hub.names = ["Exa.web_search", "Exa.fetch", "Parallel.web_search", "Other.tool"]
    assert _exa_tools(hub) == ["fetch", "web_search"]
    assert _server_tools(hub, "Parallel") == ["web_search"]
    assert _exa(MCPHub()) is None


def test_builtin_exa_server_shape():
    from agent.mcp_hub import builtin_exa_server

    exa = builtin_exa_server()
    assert exa.builtin is True
    assert exa.enabled is True
    assert exa.transport == "streamable_http"
    assert exa.url == "https://mcp.exa.ai/mcp"


def test_model_picker_state_shapes():
    from components.model_picker import model_picker_state, model_status_subtitle
    from core.state import state

    state.router_status = "starting"
    state.ai_model = "auto"
    state.model_catalog = []
    picker = model_picker_state()
    assert picker["label"] == "Starting router…"
    assert picker["active"] is False
    assert isinstance(model_status_subtitle(), str)


def test_credit_word():
    from components.credit_pill import credit_word

    assert credit_word(1) == "1 credit"
    assert credit_word(7) == "7 credits"


def test_premium_subtitle_helpers():
    from components.settings.sections_premium import _paid_subtitle, _pitch_subtitle

    assert "500" in _pitch_subtitle(None)
    assert "a day" in _pitch_subtitle(None)
    assert "500 credits a day" in _paid_subtitle(None, None)


def test_settings_screen_assembles():
    # Import-level check: the composer references every section builder.
    from pathlib import Path

    import screens.settings_screen as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    for name in [
        "build_appearance_section",
        "build_learning_section",
        "build_ai_section",
        "MCPSection",
        "build_premium_section",
        "build_data_section",
        "build_study_section",
        "build_troubleshooting_section",
        "build_about_section",
    ]:
        assert name in src, f"settings screen missing {name}"
