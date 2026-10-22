"""Web search, page fetch, and video search for the tutor.

Replaces ddgs (removed): search goes through the Exa MCP server, with
keyless Wikipedia/DuckDuckGo fallbacks. Video search parses YouTube's
own results page (no key, no yt-dlp).

All functions are async and bounded; failures return an error string
rather than raising, so a tool body never explodes the agent turn.
"""

from __future__ import annotations

import contextlib
import html
import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from core.constants import API_SAFE_SEARCH, SEARCH_ENDPOINT, SEARCH_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")


@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    snippet: str = ""
    kind: str = "web"
    thumbnail: str = ""
    duration: str = ""
    meta: dict = field(default_factory=dict)


def _clean_html(raw: str) -> str:
    """Strip scripts/styles/tags to readable text."""
    text = _SCRIPT_RE.sub(" ", raw)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return text.strip()


# ── Web search ──────────────────────────────────────────────────────────────


async def _exa_search(query: str, count: int) -> list[SearchResult]:
    """Search via the Exa MCP server (streamable HTTP, keyless).

    Bounded: one hung MCP server must not wedge the whole agent turn —
    the timeout raises into the caller's fallback chain (Wikipedia/DDG).
    """
    import asyncio

    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    results: list[SearchResult] = []
    try:
        async with asyncio.timeout(30.0):
            async with streamable_http_client(SEARCH_ENDPOINT) as (read, write, _), ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                tool_name = None
                for tool in listed.tools:
                    nm = str(tool.name)
                    if "web_search" in nm or nm.endswith("search") or "search" in nm:
                        tool_name = nm
                        break
                if tool_name is None:
                    raise RuntimeError("Exa MCP exposed no search tool")
                called = await session.call_tool(
                    tool_name,
                    {"query": query, "numResults": count},
                )
                if called.isError:
                    raise RuntimeError("Exa search returned an error")
                for block in called.content:
                    text = getattr(block, "text", None)
                    if not text:
                        continue
                    try:
                        payload = json.loads(text)
                    except Exception:
                        continue
                    rows = payload.get("results") if isinstance(payload, dict) else payload
                    for row in rows or []:
                        if not isinstance(row, dict):
                            continue
                        results.append(
                            SearchResult(
                                title=str(row.get("title") or ""),
                                url=str(row.get("url") or ""),
                                snippet=str(row.get("text") or row.get("snippet") or "")[:400],
                                kind="web",
                            )
                        )
    except TimeoutError:
        logger.info("Exa MCP search timed out; falling back")
        return []
    return results[:count]


async def _wikipedia_search(query: str, count: int) -> list[SearchResult]:
    """Keyless Wikipedia fallback."""
    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": count,
            },
        )
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        return [
            SearchResult(
                title=str(h.get("title") or ""),
                url=f"https://en.wikipedia.org/wiki/{str(h.get('title') or '').replace(' ', '_')}",
                snippet=_clean_html(str(h.get("snippet") or ""))[:400],
                kind="web",
            )
            for h in hits
        ][:count]


async def _ddg_search(query: str, count: int) -> list[SearchResult]:
    """Keyless DuckDuckGo HTML fallback."""
    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": API_SAFE_SEARCH or "wt-wt"},
        )
        resp.raise_for_status()
        raw = resp.text
    out: list[SearchResult] = []
    for match in re.finditer(
        r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a class="result__snippet"[^>]*>(.*?)</a>',
        raw,
        re.DOTALL,
    ):
        out.append(
            SearchResult(
                title=_clean_html(match.group(2)),
                url=html.unescape(match.group(1)),
                snippet=_clean_html(match.group(3))[:400],
                kind="web",
            )
        )
        if len(out) >= count:
            break
    return out


async def web_search(query: str, count: int = 6) -> list[SearchResult]:
    """Search the web: Exa MCP first, then Wikipedia, then DuckDuckGo."""
    query = (query or "").strip()[:200]
    if not query:
        return []
    count = max(1, min(int(count or 6), 8))
    for name, fn in (("exa", _exa_search), ("wikipedia", _wikipedia_search), ("ddg", _ddg_search)):
        try:
            results = await fn(query, count)
            if results:
                logger.info("search via %s: %d results", name, len(results))
                return results
        except Exception as exc:
            logger.info("search %s failed: %r", name, exc)
    return []


# ── Page fetch ──────────────────────────────────────────────────────────────


async def fetch_page(url: str, limit: int = 8000) -> tuple[str, str]:
    """Fetch a URL and return (text, error). Text is markdown-ish plain text.

    Successful fetches are cached by URL hash under cache/pages/ so repeat
    visits across turns don't re-download (the OS may purge this tier —
    a miss just re-fetches).
    """
    import hashlib
    import json

    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return "", "url must be http(s)"

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    cache_file = None
    try:
        from core.storage_paths import cache_dir

        pages = cache_dir() / "pages"
        pages.mkdir(parents=True, exist_ok=True)
        cache_file = pages / f"{digest}.json"
        if cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("url") == url and cached.get("text"):
                return str(cached["text"])[:limit], ""
    except Exception:
        cache_file = None

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = _clean_html(resp.text)
        if cache_file is not None:
            with contextlib.suppress(Exception):
                cache_file.write_text(
                    json.dumps({"url": url, "text": text[:16000]}, ensure_ascii=False),
                    encoding="utf-8",
                )
        return text[:limit], ""
    except Exception as exc:
        return "", str(exc)[:200]


# ── Video search (YouTube, keyless) ─────────────────────────────────────────

_YT_INITIAL_RE = re.compile(r"var ytInitialData\s*=\s*(\{.*?\});</script>", re.DOTALL)


def _walk_video_renderers(obj, out: list[dict]) -> None:
    """Recursively collect videoRenderer nodes from ytInitialData."""
    if isinstance(obj, dict):
        if "videoRenderer" in obj and isinstance(obj["videoRenderer"], dict):
            out.append(obj["videoRenderer"])
        for value in obj.values():
            _walk_video_renderers(value, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_video_renderers(item, out)


def _runs_text(node) -> str:
    """Join a runs/simpleText node into plain text."""
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return str(node["simpleText"])
    return "".join(str(r.get("text", "")) for r in node.get("runs") or [])


async def video_search(query: str, count: int = 6) -> list[SearchResult]:
    """Search YouTube via its own results page (keyless, no yt-dlp)."""
    query = (query or "").strip()[:200]
    if not query:
        return []
    count = max(1, min(int(count or 6), 8))
    try:
        async with httpx.AsyncClient(
            timeout=SEARCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        ) as client:
            resp = await client.get(
                "https://www.youtube.com/results",
                params={"search_query": query, "sp": "EgIQAQ%3D%3D"},
            )
            resp.raise_for_status()
            match = _YT_INITIAL_RE.search(resp.text)
            if not match:
                return []
            data = json.loads(match.group(1))
    except Exception as exc:
        logger.info("video search failed: %r", exc)
        return []

    renderers: list[dict] = []
    _walk_video_renderers(data, renderers)
    out: list[SearchResult] = []
    for r in renderers:
        vid = str(r.get("videoId") or "")
        if not vid:
            continue
        thumb = ""
        thumbs = (r.get("thumbnail") or {}).get("thumbnails") or []
        if thumbs:
            thumb = str(thumbs[-1].get("url") or "")
        out.append(
            SearchResult(
                title=_runs_text(r.get("title")),
                url=f"https://www.youtube.com/watch?v={vid}",
                snippet=_runs_text(r.get("detailedMetadataSnippets", [{}])[0].get("snippetText")) if r.get("detailedMetadataSnippets") else "",
                kind="video",
                thumbnail=thumb,
                duration=_runs_text(r.get("lengthText")),
                meta={"channel": _runs_text(r.get("ownerText")), "video_id": vid},
            )
        )
        if len(out) >= count:
            break
    return out
