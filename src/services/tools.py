import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup


def get_current_time() -> str:
    now = datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M %p")


async def search_web(query: str, max_results: int = 10, _is_retry: bool = False) -> list[dict]:
    if not query:
        return [{"error": "No query provided"}]

    print(f"\n[Tool] 🔍 Search: '{query}'")

    url = f"https://www.bing.com/search?q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            for li in soup.select("li.b_algo"):
                title_tag = li.select_one("h2 a")
                snippet_tag = li.select_one(".b_caption p") or li.select_one(".b_snippet")

                if title_tag:
                    title = title_tag.get_text(strip=True)
                    link = title_tag.get("href", "")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                    results.append({"title": title, "url": link, "content": snippet})
                    if len(results) >= max_results:
                        break

            print(f"[Tool] Found {len(results)} results")
            
            # CLEAN AND SHORTEN RESULTS FOR THE AI
            clean_results = []
            for r in results:
                # Remove common tracking params to keep URLs clean
                url = r["url"].split("?")[0]
                clean_results.append({
                    "title": r["title"],
                    "url": url,
                    "snippet": r["content"][:200]
                })

            if not clean_results and not _is_retry:
                fallback_query = re.sub(r"\s*\d{4}$", "", query).strip()
                if fallback_query != query:
                    print(f"[Tool] Retrying without year: '{fallback_query}'")
                    return await search_web(fallback_query, max_results, _is_retry=True)

            return clean_results

    except Exception as e:
        print(f"[Tool] search_web error: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


async def read_page(url: str) -> dict:
    if not url:
        return {"error": "No URL provided"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.extract()

            text = soup.get_text(separator=" ", strip=True)

            if len(text) > 15000:
                text = text[:15000] + "\n\n[... content truncated]"

            return {"url": url, "content": text}

    except Exception as e:
        print(f"[Tool] read_page error: {e}")
        return {"error": f"Extract failed: {str(e)}"}


AKILI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Searches the internet for current events, facts, or syllabuses. Search results only show snippets. If you need the full syllabus or detailed topics, you MUST follow up by calling read_page on the most relevant URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term. Be specific.",
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
            "description": "Extracts the full text from a URL. ALWAYS use this after search_web as search snippets are insufficient for complex structured data.",
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