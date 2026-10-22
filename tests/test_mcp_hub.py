"""MCP hub tests — param building, error classification, config round-trip."""

import httpx
import pytest

from agent.mcp_hub import (
    MCPError,
    MCPServerConfig,
    build_server_params,
    classify_exception,
    split_stdio_command,
)


def test_stdio_refused_on_mobile():
    server = MCPServerConfig(name="x", transport="stdio", command="npx")
    with pytest.raises(MCPError) as exc:
        build_server_params(server, is_mobile=True)
    assert exc.value.kind == "config"
    assert "mobile" in str(exc.value)


def test_remote_needs_url():
    server = MCPServerConfig(name="x", transport="streamable_http", url="")
    with pytest.raises(MCPError) as exc:
        build_server_params(server)
    assert exc.value.kind == "config"


def test_streamable_http_params_built():
    server = MCPServerConfig(
        name="exa",
        transport="streamable_http",
        url="https://mcp.exa.ai/mcp",
        headers={"Authorization": "Bearer k"},
    )
    params = build_server_params(server)
    assert params.url == "https://mcp.exa.ai/mcp"


def test_sse_params_built():
    server = MCPServerConfig(name="s", transport="sse", url="https://x/sse")
    params = build_server_params(server)
    assert params.url == "https://x/sse"


def test_classify_connect_error():
    err = classify_exception(httpx.ConnectError("boom"))
    assert err.kind == "unreachable"


def test_classify_auth_error():
    err = classify_exception(Exception("401 Unauthorized"))
    assert err.kind == "auth"


def test_classify_protocol_error():
    err = classify_exception(Exception("unsupported protocol version"))
    assert err.kind == "protocol"


def test_classify_unwraps_exception_group():
    group = BaseExceptionGroup("g", [httpx.ConnectError("x")])
    assert classify_exception(group).kind == "unreachable"


def test_split_stdio_command():
    cmd, args = split_stdio_command("npx -y some-server")
    assert cmd == "npx"
    assert args == ["-y", "some-server"]


def test_server_config_round_trip():
    server = MCPServerConfig(
        name="exa",
        transport="streamable_http",
        url="https://mcp.exa.ai/mcp",
        headers={"Authorization": "Bearer k"},
        disabled_tools=["a.b"],
    )
    restored = MCPServerConfig.from_dict(server.to_dict())
    assert restored.name == server.name
    assert restored.url == server.url
    assert restored.disabled_tools == ["a.b"]


def test_preset_payload_keyless_has_no_headers():
    from agent.mcp_catalog import PRESETS, preset_payload

    exa = next(p for p in PRESETS if p["id"] == "exa")
    payload = preset_payload(exa)
    assert payload["headers"] == {}
    assert payload["transport"] == "streamable_http"


def test_preset_payload_keyed_wires_bearer():
    from agent.mcp_catalog import PRESETS, preset_payload

    tavily = next(p for p in PRESETS if p["id"] == "tavily")
    payload = preset_payload(tavily, "secret")
    assert payload["headers"]["Authorization"] == "Bearer secret"
