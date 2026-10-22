"""JSON KV storage — atomic, debounced, offline-first.

Ported from Sherlock's storage_service pattern (the house standard).
All values stored as strings (JSON-serialized). Atomic tmp+replace write.
1s debounced flush. flush() on lifecycle events.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import tempfile

import flet as ft

logger = logging.getLogger(__name__)

_FLUSH_DELAY = 1.0  # seconds


class StorageService:
    """File-backed key-value store with atomic writes and debounced flush."""

    def __init__(self, page: ft.Page | None = None):
        self._page = page
        self._data: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Load persisted data from disk."""
        if self._initialized:
            return
        path = self._storage_path()
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                logger.warning("Storage load failed, starting fresh", exc_info=True)
                self._data = {}
        self._initialized = True

    def _storage_path(self) -> str | None:
        """Resolve the storage file path (data tier)."""
        base = None
        if self._page is not None:
            with contextlib.suppress(Exception):
                base = self._page.storage_paths.data
        if not base:
            from core.storage_paths import data_dir

            base = str(data_dir())
        return os.path.join(str(base), "akili", "storage.json")

    async def get(self, key: str, default: str | None = None) -> str | None:
        """Get a value by key."""
        return self._data.get(key, default)

    async def set(self, key: str, value: str) -> None:
        """Set a value and schedule a debounced flush."""
        self._data[key] = value
        self._schedule_flush()

    async def remove(self, key: str) -> None:
        """Remove a key and schedule a flush."""
        self._data.pop(key, None)
        self._schedule_flush()

    # ── Typed settings accessors (DDGS pattern) ─────────────────────────

    async def get_theme(self) -> str:
        from core.constants import STORAGE_THEME

        return str(await self.get(STORAGE_THEME, "system") or "system")

    async def set_theme(self, value: str) -> None:
        from core.constants import STORAGE_THEME

        await self.set(STORAGE_THEME, value)

    async def get_onboarding_done(self) -> bool:
        from core.constants import STORAGE_ONBOARDING_DONE

        return (await self.get(STORAGE_ONBOARDING_DONE)) == "true"

    async def set_onboarding_done(self, value: bool) -> None:
        from core.constants import STORAGE_ONBOARDING_DONE

        await self.set(STORAGE_ONBOARDING_DONE, "true" if value else "false")

    async def get_ai_model(self) -> str:
        from core.constants import STORAGE_AI_MODEL

        return str(await self.get(STORAGE_AI_MODEL, "auto") or "auto")

    async def set_ai_model(self, value: str) -> None:
        from core.constants import STORAGE_AI_MODEL

        await self.set(STORAGE_AI_MODEL, value or "auto")

    async def get_ai_mode(self) -> bool:
        from core.constants import STORAGE_AI_MODE

        return (await self.get(STORAGE_AI_MODE, "true")) != "false"

    async def set_ai_mode(self, value: bool) -> None:
        from core.constants import STORAGE_AI_MODE

        await self.set(STORAGE_AI_MODE, "true" if value else "false")

    async def get_reasoning_effort(self) -> str:
        from core.constants import STORAGE_REASONING_EFFORT

        return str(await self.get(STORAGE_REASONING_EFFORT, "auto") or "auto")

    async def set_reasoning_effort(self, value: str) -> None:
        from core.constants import STORAGE_REASONING_EFFORT

        await self.set(STORAGE_REASONING_EFFORT, value or "auto")

    async def get_biometric_lock(self) -> bool:
        from core.constants import STORAGE_BIOMETRIC_LOCK

        return (await self.get(STORAGE_BIOMETRIC_LOCK, "true")) != "false"

    async def set_biometric_lock(self, value: bool) -> None:
        from core.constants import STORAGE_BIOMETRIC_LOCK

        await self.set(STORAGE_BIOMETRIC_LOCK, "true" if value else "false")

    async def get_history(self) -> list:
        import json

        from core.constants import STORAGE_HISTORY

        raw = await self.get(STORAGE_HISTORY, "[]")
        try:
            data = json.loads(raw or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def set_history(self, value: list) -> None:
        import json

        from core.constants import STORAGE_HISTORY

        await self.set(STORAGE_HISTORY, json.dumps(value or []))

    def _schedule_flush(self) -> None:
        """Schedule a debounced flush."""
        if self._flush_task:
            self._flush_task.cancel()

        async def _delayed_flush():
            await asyncio.sleep(_FLUSH_DELAY)
            await self.flush()

        try:
            loop = asyncio.get_running_loop()
            self._flush_task = loop.create_task(_delayed_flush())
        except Exception:
            pass

    async def flush(self) -> None:
        """Flush data to disk immediately (atomic tmp+replace)."""
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
        path = self._storage_path()
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(path),
                suffix=".tmp",
                prefix="akili_storage_",
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp_path, path)
        except Exception:
            logger.warning("Storage flush failed", exc_info=True)

    async def flush_now(self) -> None:
        """Synchronous flush alias for lifecycle hooks."""
        await self.flush()

    async def clear_all(self) -> None:
        """Clear all data (for Reset App)."""
        self._data.clear()
        await self.flush()
