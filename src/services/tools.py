"""Tool execution — DDGS web search + extract, run locally in-app."""

from ddgs import DDGS


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using DDGS (DuckDuckGo). Sync — called before AI."""
    if not query:
        return [{"error": "No query provided"}]

    try:
        results = DDGS().text(query, max_results=min(max_results, 10))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        print(f"[Tool] web_search error: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


def extract_content(url: str) -> dict:
    """Extract webpage content as markdown using DDGS."""
    if not url:
        return {"error": "No URL provided"}

    try:
        result = DDGS().extract(url, fmt="text_markdown")
        content = result.get("content", "")

        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        if len(content) > 4000:
            content = content[:4000] + "\n\n[... content truncated]"

        return {"url": url, "content": content}
    except Exception as e:
        print(f"[Tool] extract_content error: {e}")
        return {"error": f"Extract failed: {str(e)}"}
