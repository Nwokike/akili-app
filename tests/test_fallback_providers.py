"""Tests for fallback search providers (YouTube InnerTube + OpenLibrary)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from services.fallback_providers import (
    openlibrary_book_fallback,
    youtube_video_fallback,
)


# ── YouTube InnerTube fallback ──────────────────────────────────────────


class TestYouTubeVideoFallback:
    def _mock_innerube_response(self, items: list[dict] | None = None) -> MagicMock:
        """Build a mock httpx response with the YouTube InnerTube structure."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "contents": {
                "twoColumnSearchResultsRenderer": {
                    "primaryContents": {
                        "sectionListRenderer": {
                            "contents": [
                                {
                                    "itemSectionRenderer": {
                                        "contents": items or []
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        return resp

    def _video_renderer(self, video_id: str, title: str, **kwargs) -> dict:
        return {
            "videoRenderer": {
                "videoId": video_id,
                "title": {"runs": [{"text": title}]},
                "lengthText": {"simpleText": kwargs.get("duration", "10:00")},
                "ownerText": {
                    "runs": [{"text": kwargs.get("publisher", "Test Channel")}]
                },
                "publishedTimeText": {
                    "simpleText": kwargs.get("published", "2 days ago")
                },
            }
        }

    @pytest.mark.asyncio
    async def test_success_returns_results(self):
        items = [
            self._video_renderer("abc12345678", "Quadratic Tutorial"),
            self._video_renderer("xyz98765432", "Algebra Basics"),
        ]
        mock_resp = self._mock_innerube_response(items)

        with patch(
            "services.fallback_providers._get_client"
        ) as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("quadratic equations", max_results=5)

        assert len(results) == 2
        assert results[0]["title"] == "Quadratic Tutorial"
        assert results[0]["embed_url"] == "https://www.youtube.com/embed/abc12345678"
        assert results[0]["provider"] == "youtube"
        assert results[1]["title"] == "Algebra Basics"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self):
        mock_resp = self._mock_innerube_response(items=[])

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("nonsense query")

        assert results == []

    @pytest.mark.asyncio
    async def test_non_200_returns_empty(self):
        resp = MagicMock()
        resp.status_code = 429

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=resp)
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("test")

        assert results == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self):
        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("timeout"))
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("test")

        assert results == []

    @pytest.mark.asyncio
    async def test_max_results_respected(self):
        items = [
            self._video_renderer(f"vid{i}", f"Video {i}") for i in range(10)
        ]
        mock_resp = self._mock_innerube_response(items)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("test", max_results=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_returns_correct_dict_keys(self):
        items = [self._video_renderer("abc12345678", "Test Video")]
        mock_resp = self._mock_innerube_response(items)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("test")

        expected_keys = {
            "title",
            "description",
            "duration",
            "embed_url",
            "publisher",
            "published",
            "provider",
        }
        assert set(results[0].keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_skips_items_without_video_renderer(self):
        items = [
            {"somethingElse": "not a video"},
            self._video_renderer("abc12345678", "Real Video"),
        ]
        mock_resp = self._mock_innerube_response(items)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await youtube_video_fallback("test")

        assert len(results) == 1
        assert results[0]["title"] == "Real Video"


# ── OpenLibrary book fallback ───────────────────────────────────────────


class TestOpenLibraryBookFallback:
    def _mock_openlibrary_response(self, docs: list[dict]) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"docs": docs}
        return resp

    @pytest.mark.asyncio
    async def test_success_returns_results(self):
        docs = [
            {
                "title": "Introduction to Algorithms",
                "author_name": ["Thomas H. Cormen", "Charles E. Leiserson"],
                "publisher": ["MIT Press"],
                "cover_i": 12345,
                "key": "/works/OL12345W",
                "first_publish_year": 1990,
            }
        ]
        mock_resp = self._mock_openlibrary_response(docs)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("algorithms textbook")

        assert len(results) == 1
        assert results[0]["title"] == "Introduction to Algorithms"
        assert results[0]["author"] == "Thomas H. Cormen, Charles E. Leiserson"
        assert results[0]["thumbnail"] == "https://covers.openlibrary.org/b/id/12345-M.jpg"
        assert results[0]["url"] == "https://openlibrary.org/works/OL12345W"

    @pytest.mark.asyncio
    async def test_empty_docs_returns_empty(self):
        mock_resp = self._mock_openlibrary_response(docs=[])

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("nonsense query")

        assert results == []

    @pytest.mark.asyncio
    async def test_non_200_returns_empty(self):
        resp = MagicMock()
        resp.status_code = 500

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=resp)
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("test")

        assert results == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self):
        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("test")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_correct_dict_keys(self):
        docs = [{"title": "Test Book", "author_name": ["Author"]}]
        mock_resp = self._mock_openlibrary_response(docs)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("test")

        expected_keys = {"title", "author", "publisher", "info", "url", "thumbnail"}
        assert set(results[0].keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_skips_docs_without_title(self):
        docs = [
            {"author_name": ["Author"]},  # no title
            {"title": "Valid Book"},
        ]
        mock_resp = self._mock_openlibrary_response(docs)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("test")

        assert len(results) == 1
        assert results[0]["title"] == "Valid Book"

    @pytest.mark.asyncio
    async def test_no_cover_returns_empty_thumbnail(self):
        docs = [{"title": "No Cover Book", "key": "/works/OL1W"}]
        mock_resp = self._mock_openlibrary_response(docs)

        with patch("services.fallback_providers._get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client

            results = await openlibrary_book_fallback("test")

        assert results[0]["thumbnail"] == ""


# ── Integration: search_videos/search_books with fallback ────────────────


class TestToolsFallbackWiring:
    """Test that tools.py search functions actually invoke fallback on failure."""

    @pytest.mark.asyncio
    async def test_search_videos_falls_back_on_empty_ddgs(self):
        with (
            patch("services.tools._ddgs") as mock_ddgs,
            patch("services.tools.youtube_video_fallback", new_callable=AsyncMock) as mock_fallback,
        ):
            mock_ddgs.videos = MagicMock(return_value=[])  # DDGS returns 0 results
            mock_fallback.return_value = [
                {
                    "title": "Fallback Video",
                    "description": "Test",
                    "duration": "5:00",
                    "embed_url": "https://youtube.com/embed/abc",
                    "publisher": "Fallback",
                    "published": "today",
                    "provider": "youtube",
                }
            ]

            from services.tools import search_videos
            results = await search_videos("quantum physics")

        assert len(results) == 1
        assert results[0]["title"] == "Fallback Video"
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_videos_falls_back_on_exception(self):
        with (
            patch("services.tools._ddgs") as mock_ddgs,
            patch("services.tools.youtube_video_fallback", new_callable=AsyncMock) as mock_fallback,
        ):
            mock_ddgs.videos = MagicMock(side_effect=Exception("rate limited"))
            mock_fallback.return_value = [
                {
                    "title": "Saved by Fallback",
                    "description": "Test",
                    "duration": "3:00",
                    "embed_url": "https://youtube.com/embed/xyz",
                    "publisher": "Fallback",
                    "published": "yesterday",
                    "provider": "youtube",
                }
            ]

            from services.tools import search_videos
            results = await search_videos("test query")

        assert results[0]["title"] == "Saved by Fallback"
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_books_falls_back_on_empty_ddgs(self):
        with (
            patch("services.tools._ddgs") as mock_ddgs,
            patch("services.tools.openlibrary_book_fallback", new_callable=AsyncMock) as mock_fallback,
        ):
            mock_ddgs.books = MagicMock(return_value=[])  # DDGS returns 0 results
            mock_fallback.return_value = [
                {
                    "title": "Fallback Book",
                    "author": "OL Author",
                    "publisher": "OL Press",
                    "info": "A book",
                    "url": "https://openlibrary.org/works/OL1",
                    "thumbnail": "",
                }
            ]

            from services.tools import search_books
            results = await search_books("calculus")

        assert len(results) == 1
        assert results[0]["title"] == "Fallback Book"
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_books_falls_back_on_exception(self):
        with (
            patch("services.tools._ddgs") as mock_ddgs,
            patch("services.tools.openlibrary_book_fallback", new_callable=AsyncMock) as mock_fallback,
        ):
            mock_ddgs.books = MagicMock(side_effect=Exception("connection refused"))
            mock_fallback.return_value = [
                {
                    "title": "Rescued Book",
                    "author": "Author",
                    "publisher": "Press",
                    "info": "Info",
                    "url": "",
                    "thumbnail": "",
                }
            ]

            from services.tools import search_books
            results = await search_books("chemistry")

        assert results[0]["title"] == "Rescued Book"
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_videos_no_fallback_when_ddgs_works(self):
        with (
            patch("services.tools._ddgs") as mock_ddgs,
            patch("services.tools.youtube_video_fallback", new_callable=AsyncMock) as mock_fallback,
        ):
            mock_ddgs.videos = MagicMock(
                return_value=[
                    {
                        "title": "DDGS Video",
                        "description": "desc",
                        "duration": "10:00",
                        "embed_url": "https://yt.com/e/123",
                        "publisher": "Ch",
                        "published": "now",
                        "provider": "ddgs",
                    }
                ]
            )

            from services.tools import search_videos
            results = await search_videos("math")

        assert results[0]["title"] == "DDGS Video"
        mock_fallback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_books_no_fallback_when_ddgs_works(self):
        with (
            patch("services.tools._ddgs") as mock_ddgs,
            patch("services.tools.openlibrary_book_fallback", new_callable=AsyncMock) as mock_fallback,
        ):
            mock_ddgs.books = MagicMock(
                return_value=[
                    {
                        "title": "DDGS Book",
                        "author": "Author",
                        "publisher": "Pub",
                        "info": "Info",
                        "url": "",
                        "thumbnail": "",
                    }
                ]
            )

            from services.tools import search_books
            results = await search_books("physics")

        assert results[0]["title"] == "DDGS Book"
        mock_fallback.assert_not_awaited()
