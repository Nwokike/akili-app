"""Education tools the tutor agent can call.

Read-only and free: search the web (MCP Exa + fallbacks), find
educational videos, and read a page for grounding. No write tools in
Phase 2 — course/lesson/quiz generation are structured single-shot calls
(Phase 3), not agent tools.

Each tool's `run` never raises: failures become the error JSON the model
always sees.
"""

from __future__ import annotations

import json
import logging

import httpx

from agent.kani_backend import ToolSpec
from agent.search import fetch_page, video_search, web_search

logger = logging.getLogger(__name__)


def build_tools() -> list[ToolSpec]:
    """The tutor's three read-only tools."""

    async def run_search_web(args: dict) -> str:
        query = str(args.get("query") or "")[:200]
        count = min(int(args.get("count") or 6), 8)
        results = await web_search(query, count)
        if not results:
            return json.dumps({"error": "No results found. Try a broader query."})
        return json.dumps(
            [{"title": r.title, "url": r.url, "snippet": r.snippet[:300]} for r in results],
            ensure_ascii=False,
        )

    async def run_search_videos(args: dict) -> str:
        query = str(args.get("query") or "")[:200]
        count = min(int(args.get("count") or 6), 8)
        results = await video_search(query, count)
        if not results:
            return json.dumps({"error": "No videos found. Try a broader query."})
        return json.dumps(
            [
                {
                    "title": r.title,
                    "url": r.url,
                    "channel": r.meta.get("channel", ""),
                    "duration": r.duration,
                }
                for r in results
            ],
            ensure_ascii=False,
        )

    async def run_fetch_page(args: dict) -> str:
        url = str(args.get("url") or "")
        text, err = await fetch_page(url)
        if err:
            return json.dumps({"error": err})
        return json.dumps({"url": url, "content": text}, ensure_ascii=False)

    return [
        ToolSpec(
            name="search_web",
            desc=("Search the web for current or factual information. Returns title/url/snippet results. Use this for anything you are not certain about — never invent sources."),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 8},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            run=run_search_web,
        ),
        ToolSpec(
            name="search_videos",
            desc=("Find educational videos on a topic (YouTube). Returns title/url/channel/duration. Use when a visual explanation would help the student."),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 8},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            run=run_search_videos,
        ),
        ToolSpec(
            name="fetch_page",
            desc=("Fetch one URL as plain text for grounding or summarising. Prefer after search_web when you need the actual page content."),
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
            run=run_fetch_page,
        ),
    ]


def pretty_label(name: str, args: dict) -> str:
    """User-legible tool label: verb first, no quotes, no trailing ellipsis."""
    query = str(args.get("query") or "").strip()
    url = str(args.get("url") or "").strip()
    if name == "search_web":
        return f"Searching the web: {query[:80]}"
    if name == "search_videos":
        return f"Finding videos: {query[:80]}"
    if name == "fetch_page":
        host = url.split("/")[2] if "//" in url else url
        return f"Reading {host[:50]}"
    return f"Running {name}"


def make_client() -> httpx.AsyncClient:
    """Shared client for tool bodies that need raw HTTP."""
    return httpx.AsyncClient(timeout=25.0)
