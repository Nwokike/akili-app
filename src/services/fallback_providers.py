"""Fallback search providers for video and book searches.

When DDGS rate-limits or fails on videos/books (single-engine categories),
we silently fall back to alternative providers:

  - Videos: YouTube InnerTube search API (direct, no API key)
  - Books: OpenLibrary search API (free, no API key)

Both return dicts matching the shape expected by the AI tools in tools.py.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# Reusable async client (connection pooling)
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10, follow_redirects=True)
    return _client


async def youtube_video_fallback(
    query: str, max_results: int = 5
) -> list[dict]:
    """Search YouTube directly via InnerTube when DDGS.videos fails or returns 0 results.

    Returns list of dicts matching the shape of search_videos() output:
        {title, description, duration, embed_url, publisher, published, provider}
    """
    try:
        client = await _get_client()
        body = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00",
                    "hl": "en",
                    "gl": "US",
                }
            },
            "query": query,
        }
        resp = await client.post(
            "https://www.youtube.com/youtubei/v1/search", json=body
        )
        if resp.status_code != 200:
            logger.warning(
                "YouTube InnerTube search returned status %d", resp.status_code
            )
            return []

        data = resp.json()
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        items = (
            contents[0].get("itemSectionRenderer", {}).get("contents", [])
            if contents
            else []
        )

        results = []
        for item in items:
            if "videoRenderer" not in item:
                continue
            vr = item["videoRenderer"]
            title = vr.get("title", {}).get("runs", [{}])[0].get("text", "")
            video_id = vr.get("videoId", "")
            if not title or not video_id:
                continue

            duration = vr.get("lengthText", {}).get("simpleText", "")
            publisher = vr.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
            published = vr.get("publishedTimeText", {}).get("simpleText", "")

            results.append(
                {
                    "title": title,
                    "description": f"{publisher} • {duration}" if publisher else title,
                    "duration": duration,
                    "embed_url": f"https://www.youtube.com/embed/{video_id}",
                    "publisher": publisher,
                    "published": published,
                    "provider": "youtube",
                }
            )
            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        logger.warning("YouTube video fallback error: %s", e)
        return []


async def openlibrary_book_fallback(
    query: str, max_results: int = 5
) -> list[dict]:
    """Search OpenLibrary directly when DDGS.books returns 0 results or fails.

    Returns list of dicts matching the shape of search_books() output:
        {title, author, publisher, info, url, thumbnail}
    """
    try:
        client = await _get_client()
        resp = await client.get(
            "https://openlibrary.org/search.json",
            params={"q": query, "limit": str(max_results)},
        )
        if resp.status_code != 200:
            logger.warning(
                "OpenLibrary search returned status %d", resp.status_code
            )
            return []

        docs = resp.json().get("docs", [])
        results = []
        for doc in docs:
            title = doc.get("title", "")
            if not title:
                continue

            authors = ", ".join(doc.get("author_name", []))
            publisher = doc.get("publisher", [""])[0] if doc.get("publisher") else ""
            cover_i = doc.get("cover_i")
            thumbnail = (
                f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg"
                if cover_i
                else ""
            )
            key = doc.get("key", "")
            url = f"https://openlibrary.org{key}" if key else ""
            first_publish_year = doc.get("first_publish_year", "")
            info = f"{authors} ({first_publish_year})" if authors else (
                f"Published {first_publish_year}" if first_publish_year else title
            )

            results.append(
                {
                    "title": title,
                    "author": authors,
                    "publisher": publisher,
                    "info": info[:200],
                    "url": url,
                    "thumbnail": thumbnail,
                }
            )
            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        logger.warning("OpenLibrary book fallback error: %s", e)
        return []
