"""Agent tool tests — schemas, dispatch, failure handling."""

import json

import pytest

from agent.chat_agent import _charged_steps, _count_results, _error_text
from agent.tools import build_tools, pretty_label


def test_build_tools_shape():
    tools = build_tools()
    names = {t.name for t in tools}
    assert names == {"search_web", "search_videos", "fetch_page"}
    for tool in tools:
        assert tool.desc
        assert tool.parameters["type"] == "object"
        assert "properties" in tool.parameters


def test_pretty_label_verbs():
    assert pretty_label("search_web", {"query": "photosynthesis"}).startswith("Searching the web")
    assert pretty_label("search_videos", {"query": "water cycle"}).startswith("Finding videos")
    assert pretty_label("fetch_page", {"url": "https://example.com/x"}).startswith("Reading example.com")


def test_charged_steps_floor_when_text_delivered():
    assert _charged_steps(0, ["hello"]) == 1
    assert _charged_steps(0, []) == 0
    assert _charged_steps(3, ["x"]) == 3


def test_count_results_list_payload():
    assert _count_results(json.dumps([{"a": 1}, {"b": 2}])) == 2
    assert _count_results(json.dumps({"error": "x"})) == 0
    assert _count_results("not json") == 0


def test_error_text_names_empty_exceptions():
    assert _error_text(TimeoutError()) == "timed out"
    assert _error_text(RuntimeError("boom")) == "boom"
    assert _error_text(ValueError()) == "ValueError"


@pytest.mark.asyncio
async def test_search_web_returns_json(monkeypatch):
    from agent import tools

    async def _fake_search(query, count=6):
        from agent.search import SearchResult

        return [SearchResult(title="T", url="https://x", snippet="s")]

    monkeypatch.setattr(tools, "web_search", _fake_search)
    spec = next(t for t in build_tools() if t.name == "search_web")
    payload = json.loads(await spec.run({"query": "anything"}))
    assert isinstance(payload, list)
    assert payload[0]["title"] == "T"


@pytest.mark.asyncio
async def test_search_web_empty_is_error_payload(monkeypatch):
    from agent import tools

    async def _empty(query, count=6):
        return []

    monkeypatch.setattr(tools, "web_search", _empty)
    spec = next(t for t in build_tools() if t.name == "search_web")
    payload = json.loads(await spec.run({"query": "anything"}))
    assert "error" in payload


def test_tool_source_accepts_our_toolspec():
    import asyncio

    from agent.chat_agent import _tool_source
    from agent.kani_backend import ToolSpec

    async def impl(args: dict) -> str:
        return f"ran {args.get('x')}"

    spec = ToolSpec(name="my_tool", desc="Does a thing", parameters={"type": "object"}, run=impl)
    name, desc, parameters, source_run = _tool_source(spec)
    assert (name, desc, parameters) == ("my_tool", "Does a thing", {"type": "object"})
    assert asyncio.run(source_run({"x": 1})) == "ran 1"


def test_tool_source_accepts_aifunction():
    """MCP hub tools are AIFunctions — schema in .json_schema, impl in .inner."""
    import asyncio

    from kani import AIFunction

    from agent.chat_agent import _tool_source

    async def fake_mcp(query: str) -> str:
        return f"results for {query}"

    fn = AIFunction(
        fake_mcp,
        name="web_search",
        desc="Search the web",
        json_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    name, desc, parameters, source_run = _tool_source(fn)
    assert name == "web_search"
    assert desc == "Search the web"
    assert parameters["properties"]["query"] == {"type": "string"}
    assert asyncio.run(source_run({"query": "photosynthesis"})) == "results for photosynthesis"


def test_tool_source_aifunction_without_schema():
    """AIFunction auto-generates json_schema at construction (never None)."""
    from kani import AIFunction

    from agent.chat_agent import _tool_source

    async def fake_mcp() -> str:
        return "ok"

    name, desc, parameters, source_run = _tool_source(AIFunction(fake_mcp))
    assert name == "fake_mcp"
    assert parameters["type"] == "object"  # kani auto-generated it
