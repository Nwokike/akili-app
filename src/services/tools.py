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

            if not results and not _is_retry:
                fallback_query = re.sub(r"\s*\d{4}$", "", query).strip()
                if fallback_query != query:
                    print(f"[Tool] Retrying without year: '{fallback_query}'")
                    return await search_web(fallback_query, max_results, _is_retry=True)

                return [{"error": "No results found for this query. Try a different search term."}]

            if not results:
                return [{"error": "No results found for this query. Try a different search term."}]

            return results

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
            "description": "Searches the internet for up-to-date facts, syllabuses, or curriculum information. ALWAYS use this if you are unsure of a fact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term. Append the current year to ensure recent results.",
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
            "description": "Reads the full text of a specific website URL. Use this after searching if the search snippet doesn't contain enough detailed information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full HTTP or HTTPS URL of the page to read",
                    }
                },
                "required": ["url"],
            },
        },
    },
]