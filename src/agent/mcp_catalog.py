"""Curated MCP catalog: one-tap add for people who will never write JSON.

Ported from lm-router mcp_catalog.py (the house standard).

Every URL below completed a real initialize/tools/list round without
credentials (keyless) or with the documented auth header (keyed).
An AI tutor is only as good as its tools; this list is the zero-setup
path for users who do not know what an MCP server is.

v1 is deliberately header-auth only: servers behind OAuth stay out until
we build a real sign-in flow.
"""

from __future__ import annotations

PRESETS: tuple[dict, ...] = (
    # ---- keyless: one tap and it connects ----
    {
        "id": "exa",
        "name": "Exa",
        "url": "https://mcp.exa.ai/mcp",
        "auth": None,
        "description": ("Searches the web and reads pages, so study answers come with real sources instead of guesses."),
    },
    {
        "id": "deepwiki",
        "name": "DeepWiki",
        "url": "https://mcp.deepwiki.com/mcp",
        "auth": None,
        "description": ("Explains how any open-source project works, like a guide who already read the whole codebase."),
    },
    {
        "id": "context7",
        "name": "Context7",
        "url": "https://mcp.context7.com/mcp",
        "auth": None,
        "description": ("Looks up the latest instructions for any software tool, so coding lessons are never out of date."),
    },
    {
        "id": "huggingface",
        "name": "Hugging Face",
        "url": "https://huggingface.co/mcp",
        "auth": None,
        "description": "Finds open AI models and datasets you can browse and try.",
    },
    {
        "id": "openai-docs",
        "name": "OpenAI Docs",
        "url": "https://developers.openai.com/mcp",
        "auth": None,
        "description": "Looks up official OpenAI documentation and API details.",
    },
    {
        "id": "claude-docs",
        "name": "Claude Docs",
        "url": "https://platform.claude.com/docs/mcp",
        "auth": None,
        "description": "Looks up official Claude documentation and API details.",
    },
    {
        "id": "cloudflare-docs",
        "name": "Cloudflare Docs",
        "url": "https://docs.mcp.cloudflare.com/mcp",
        "auth": None,
        "description": "Answers questions about building and running websites on Cloudflare.",
    },
    {
        "id": "wikipedia",
        "name": "Wikipedia",
        "url": "https://mcp.wikipedia.org/mcp",
        "auth": None,
        "description": ("Reads Wikipedia articles — a solid, citable source for school research."),
    },
    # ---- key-required: the app collects the key and wires the header ----
    {
        "id": "tavily",
        "name": "Tavily",
        "url": "https://mcp.tavily.com/mcp",
        "auth": {
            "key_label": "API key",
            "get_key_url": "https://app.tavily.com",
            "hint": "Web search tuned for AI, so research comes back fast and clean.",
        },
        "description": "Searches the web tuned for AI, so research comes back fast and clean.",
    },
    {
        "id": "perplexity",
        "name": "Perplexity",
        "url": "https://api.perplexity.ai/mcp",
        "auth": {
            "key_label": "API key",
            "get_key_url": "https://docs.perplexity.ai",
            "hint": "Deep, sourced research answers with citations.",
        },
        "description": "Deep, sourced research answers to any question, with citations.",
    },
    {
        "id": "firecrawl",
        "name": "Firecrawl",
        "url": "https://mcp.firecrawl.dev/v2/mcp",
        "auth": {
            "key_label": "API key",
            "get_key_url": "https://www.firecrawl.dev/app/api-keys",
            "hint": "Reads and crawls websites, including pages that need JavaScript.",
        },
        "description": ("Reads and crawls websites, including pages that need JavaScript, and pulls out the text."),
    },
)


def preset_payload(preset: dict, api_key: str = "") -> dict:
    """Config dict for adding a server.

    Keyless presets never send headers; a supplied key becomes the standard
    Authorization bearer header.
    """
    headers: dict[str, str] = {}
    key = str(api_key or "").strip()
    if preset.get("auth") and key:
        headers["Authorization"] = f"Bearer {key}"
    return {
        "name": str(preset["name"]),
        "transport": "streamable_http",
        "url": str(preset["url"]),
        "headers": headers,
    }
