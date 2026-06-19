"""AI tools — DDGS-powered search, extract, and time awareness.

Uses the `ddgs` package (v9.14.4) which aggregates results from
Google, Bing, Brave, DuckDuckGo, Wikipedia, Yahoo, Yandex, and more.

DDGS is synchronous internally (uses ThreadPoolExecutor), so all
functions use asyncio.to_thread() to avoid blocking the Flet event loop.
"""

import asyncio
import logging
from datetime import datetime

from ddgs import DDGS

from core.state import state

logger = logging.getLogger(__name__)

# Shared DDGS instance (reuses HTTP connections and engine cache)
_ddgs = DDGS(timeout=10)


def get_current_time() -> str:
    """Full timestamp for AI context — MANDATORY on every AI call."""
    now = datetime.now()
    human = now.strftime("%A, %B %d, %Y at %I:%M:%S %p")
    iso = now.isoformat()
    # Academic year: Jan-Aug = previous/current, Sep-Dec = current/next
    year = now.year
    academic = f"{year - 1}/{year}" if now.month <= 8 else f"{year}/{year + 1}"
    return f"{human} ({iso}) | Academic Year: {academic}"


async def search_web(query: str, max_results: int = 8) -> list[dict]:
    """General web search — aggregates Google, Bing, Brave, Wikipedia, etc."""
    if not query:
        return [{"error": "No query provided"}]

    logger.info("🔍 Web search: '%s'", query)
    try:
        results = await asyncio.to_thread(
            _ddgs.text,
            query,
            max_results=max_results,
            safesearch=state.safesearch_level,
            region=state.search_region,
        )
        clean = [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")[:250]} for r in results]
        logger.info("Found %d web results", len(clean))
        return clean
    except Exception as e:
        logger.warning("search_web failed: %s", e)
        return [{"error": f"Search failed: {e}"}]


async def search_images(query: str, max_results: int = 6) -> list[dict]:
    """Image search — find diagrams, charts, illustrations for any topic."""
    if not query:
        return [{"error": "No query provided"}]

    logger.info("🖼️ Image search: '%s'", query)
    try:
        results = await asyncio.to_thread(
            _ddgs.images,
            query,
            max_results=max_results,
            safesearch=state.safesearch_level,
            region=state.search_region,
        )
        clean = [
            {
                "title": r.get("title", ""),
                "image_url": r.get("image", ""),
                "thumbnail": r.get("thumbnail", ""),
                "source_url": r.get("url", ""),
                "width": r.get("width", ""),
                "height": r.get("height", ""),
            }
            for r in results
        ]
        logger.info("Found %d images", len(clean))
        return clean
    except Exception as e:
        logger.warning("search_images failed: %s", e)
        return [{"error": f"Image search failed: {e}"}]


async def search_news(query: str, max_results: int = 6) -> list[dict]:
    """News search — current events, breaking news, recent developments."""
    if not query:
        return [{"error": "No query provided"}]

    logger.info("📰 News search: '%s'", query)
    try:
        results = await asyncio.to_thread(
            _ddgs.news,
            query,
            max_results=max_results,
            safesearch=state.safesearch_level,
            region=state.search_region,
        )
        clean = [
            {
                "title": r.get("title", ""),
                "body": r.get("body", "")[:300],
                "url": r.get("url", ""),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "image": r.get("image", ""),
            }
            for r in results
        ]
        logger.info("Found %d news articles", len(clean))
        return clean
    except Exception as e:
        logger.warning("search_news failed: %s", e)
        return [{"error": f"News search failed: {e}"}]


async def search_videos(query: str, max_results: int = 5) -> list[dict]:
    """Video search — educational videos, tutorials, explainers."""
    if not query:
        return [{"error": "No query provided"}]

    logger.info("🎬 Video search: '%s'", query)
    try:
        results = await asyncio.to_thread(
            _ddgs.videos,
            query,
            max_results=max_results,
            safesearch=state.safesearch_level,
            region=state.search_region,
        )
        clean = [
            {
                "title": r.get("title", ""),
                "description": r.get("description", "")[:200],
                "duration": r.get("duration", ""),
                "embed_url": r.get("embed_url", ""),
                "publisher": r.get("publisher", ""),
                "published": r.get("published", ""),
                "provider": r.get("provider", ""),
            }
            for r in results
        ]
        logger.info("Found %d videos", len(clean))
        return clean
    except Exception as e:
        logger.warning("search_videos failed: %s", e)
        return [{"error": f"Video search failed: {e}"}]


async def search_books(query: str, max_results: int = 5) -> list[dict]:
    """Book search — textbooks, study guides, reference materials."""
    if not query:
        return [{"error": "No query provided"}]

    logger.info("📚 Book search: '%s'", query)
    try:
        results = await asyncio.to_thread(
            _ddgs.books,
            query,
            max_results=max_results,
        )
        clean = [
            {
                "title": r.get("title", ""),
                "author": r.get("author", ""),
                "publisher": r.get("publisher", ""),
                "info": r.get("info", "")[:200],
                "url": r.get("url", ""),
                "thumbnail": r.get("thumbnail", ""),
            }
            for r in results
        ]
        logger.info("Found %d books", len(clean))
        return clean
    except Exception as e:
        logger.warning("search_books failed: %s", e)
        return [{"error": f"Book search failed: {e}"}]


async def read_page(url: str) -> dict:
    """Extract full page content as clean Markdown from any URL."""
    if not url:
        return {"error": "No URL provided"}

    logger.info("📄 Extracting: %s", url)
    try:
        result = await asyncio.to_thread(
            _ddgs.extract,
            url,
            "text_markdown",
        )
        content = result.get("content", "")
        # Truncate very long pages to keep within AI context window
        if len(content) > 15000:
            content = content[:15000] + "\n\n[... content truncated]"
        logger.info("Extracted %d chars from %s", len(content), url)
        return {"url": url, "content": content}
    except Exception as e:
        logger.warning("read_page failed: %s", e)
        return {"error": f"Extract failed: {e}"}


# ── AI Tool Definitions (OpenAI function calling format) ──────────────

AKILI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the internet for facts, syllabuses, curriculum content, definitions, and general knowledge. Returns snippets — use read_page for full content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific, include year and education level when relevant.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_images",
            "description": "Find educational images, diagrams, charts, illustrations, and visual aids. Use when the student asks for visual explanations or diagrams. Return image URLs in markdown format: ![description](url)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for. Example: 'water cycle diagram', 'periodic table', 'human digestive system diagram'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "Search for current events, breaking news, and recent developments. Use for Social Studies, Civic Education, Current Affairs, or any question about recent events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news topic to search for. Example: 'WAEC 2026 results', 'Nigeria education news'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_videos",
            "description": "Find educational videos, tutorials, and explainer content. Use when the student needs a video explanation of a concept. Include the embed_url in your response so the app can play it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The video topic. Example: 'quadratic equations tutorial', 'photosynthesis explained'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "Find textbooks, study guides, and reference books. Use when the student needs book recommendations or study materials for a subject.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The book topic. Example: 'SS2 Chemistry textbook', 'WAEC past questions Mathematics'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_page",
            "description": "Extract the full content from a URL as clean Markdown. Use AFTER search_web when you need the complete article, syllabus, or document — not just the snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to extract content from.",
                    }
                },
                "required": ["url"],
            },
        },
    },
]
