"""MCP section — the built-in search servers + toggles.

No custom servers, no delete, no add (per owner direction). Two servers
ship built in and always present: Exa (primary: web_search_exa +
web_fetch_exa) and Parallel (independent fallback: web_search +
web_fetch) for when Exa is down — both keyless and free at the
anonymous tier. Settings offers per-server enable Switches, per-tool
toggles (mapped to the hub's `disabled_tools`), a Test button with
honest errors, and a live tool count. Persisted to STORAGE_MCP_SERVERS;
every change calls `request_reconnect()` on the hub.
"""

from __future__ import annotations

import json

import flet as ft

from agent.mcp_hub import MCPHub, builtin_exa_server, builtin_parallel_server
from components.settings_kit import setting_row, settings_card
from core import tokens
from core.constants import STORAGE_MCP_SERVERS


def _hub(page: ft.Page | None) -> MCPHub | None:
    try:
        live = page or ft.context.page
        return getattr(live, "_akili_mcp_hub", None)
    except Exception:
        return None


def _builtin(hub: MCPHub | None):
    """(exa, parallel) servers, in display order."""
    exa = parallel = None
    if hub is not None:
        wanted = (builtin_exa_server().name, builtin_parallel_server().name)
        for server in hub.servers:
            if server.name == wanted[0]:
                exa = server
            elif server.name == wanted[1]:
                parallel = server
    return exa, parallel


def _exa(hub: MCPHub | None):
    return _builtin(hub)[0]


def _server_tools(hub: MCPHub, server_name: str) -> list[str]:
    """Live tool short-names for one server (hub prefixes `Name.<tool>`)."""
    prefix = f"{server_name}."
    return sorted({name[len(prefix) :] for name in hub.names if name.startswith(prefix)})


def _exa_tools(hub: MCPHub) -> list[str]:
    return _server_tools(hub, builtin_exa_server().name)


async def _persist(page: ft.Page | None, hub: MCPHub) -> None:
    """Persist the builtins' toggles; reconnect the hub."""
    extras = [s for s in hub.servers if not s.builtin]
    try:
        live = page or ft.context.page
        storage = getattr(live, "_akili_storage", None)
        if storage is not None:
            await storage.set(STORAGE_MCP_SERVERS, json.dumps([s.to_dict() for s in extras], ensure_ascii=False))
    except Exception:
        pass
    hub.request_reconnect()


@ft.component
def MCPSection():
    """The Web Search (Exa + Parallel fallback) settings section."""
    testing, set_testing = ft.use_state("")
    test_result, set_test_result = ft.use_state("")
    refresh, set_refresh = ft.use_state(0)

    _ = refresh
    page = ft.context.page
    hub = _hub(page)
    exa, parallel = _builtin(hub)
    if hub is None or exa is None or parallel is None:
        return settings_card(
            [
                setting_row(
                    ft.Icons.CLOUD_OFF_ROUNDED,
                    "Web Search",
                    "Search service is starting…",
                    None,
                )
            ]
        )

    def _status(server) -> str:
        tools = _server_tools(hub, server.name)
        if not server.enabled:
            return "Turned off"
        if tools:
            return f"{len(tools)} tools available"
        return "Connecting…"

    def _toggle(server, enabled: bool):
        server.enabled = enabled
        set_refresh(refresh + 1)
        page.run_task(_persist, page, hub)

    def _toggle_tool(server, tool: str, on: bool):
        if on:
            server.disabled_tools = [t for t in server.disabled_tools if t != tool]
        elif tool not in server.disabled_tools:
            server.disabled_tools = [*server.disabled_tools, tool]
        set_refresh(refresh + 1)
        page.run_task(_persist, page, hub)

    async def _run_test(server):
        set_testing(server.name)
        set_test_result("")
        try:
            found = await hub.test(server)
            set_test_result(f"{server.name}: connected — {len(found)} tools.")
        except Exception as exc:
            set_test_result(f"{server.name}: {exc}")
        finally:
            set_testing("")

    def _server_block(server, blurb: str) -> list:
        rows = [
            setting_row(
                ft.Icons.TRAVEL_EXPLORE_ROUNDED,
                server.name,
                f"{_status(server)} · {blurb}",
                ft.Switch(value=server.enabled, on_change=lambda e: _toggle(server, e.control.value)),
            ),
            setting_row(
                ft.Icons.WIFI_TETHERING_ROUNDED,
                f"Test {server.name}",
                test_result or f"Check that {server.name} answers right now.",
                ft.OutlinedButton(
                    "Testing…" if testing == server.name else "Test",
                    on_click=lambda e: page.run_task(_run_test, server),
                    disabled=bool(testing),
                ),
            ),
        ]
        tools = _server_tools(hub, server.name)
        if tools:
            rows.append(
                setting_row(
                    ft.Icons.BUILD_ROUNDED,
                    f"{server.name} tools",
                    "Turn off tools you don't want the tutor to call.",
                    None,
                )
            )
            for tool in tools:
                on = tool not in server.disabled_tools
                rows.append(
                    setting_row(
                        ft.Icons.FUNCTIONS_ROUNDED,
                        tool,
                        "Enabled" if on else "Disabled",
                        ft.Switch(
                            value=on,
                            on_change=lambda e, t=tool: _toggle_tool(server, t, e.control.value),
                        ),
                    )
                )
        return rows

    rows = _server_block(exa, "Primary web search + page fetch. Built in, always available.")
    rows.append(ft.Divider(height=1))
    rows += _server_block(parallel, "Independent fallback when Exa is down. No key, free tier.")
    if test_result:
        rows.append(
            ft.Container(
                content=ft.Text(test_result, size=tokens.FONT_XS, color=ft.Colors.ON_SURFACE_VARIANT),
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_SM),
            )
        )
    no_tools = not _server_tools(hub, exa.name) and not _server_tools(hub, parallel.name)
    if no_tools:
        rows.append(
            ft.Container(
                content=ft.Text(
                    "Tool lists appear once the servers connect. The tutor's built-in search keeps working meanwhile.",
                    size=tokens.FONT_XS,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_SM),
            )
        )

    return settings_card(rows)
