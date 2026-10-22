"""Kiri router lifecycle — discover, attach, or embed.

Ported from DDGS ai_service.py + engine.py (the house standard for
apps on the Kiri router, not the gateway).

The router is the ONLY AI source. Model choice belongs to the router:
the app sends state.ai_model verbatim and the router handles ranking,
per-conversation stickiness and in-request failover.

Discovery scans 127.0.0.1:8082..8092 for GET /health with
{"adapter":"kiri-router"}. The engine itself is fetched LIVE from
router.kiri.ng/run.py on every cold start and cached to user storage —
never vendored (upstream changes constantly and a bundled snapshot would
silently shadow it).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import threading
import time
from pathlib import Path

import httpx

from core.constants import (
    APP_VERSION,
    ENGINE_URL,
    PROBE_MISS_TTL,
    ROUTER_BASE_PORT,
    ROUTER_HOST,
    ROUTER_SPAN,
    ROUTER_STICKY_COOLDOWN,
)
from core.state import state

logger = logging.getLogger(__name__)

USER_AGENT = f"AkiliApp/{APP_VERSION}"
MODULE_NAME = "akili_engine"
# Tolerant on quote style (lm-router's regex accepts both); the engine is
# fetched live and a needlessly strict pattern would reject a valid update.
VERSION_RE = re.compile(rb'VERSION\s*=\s*["\']([^"\']+)["\']')
# An engine is a single main-guarded .py file; 5MB is already absurd for
# one — anything larger is rejected before it can OOM the app (lm-router
# enforces the same bound).
MAX_ENGINE_BYTES = 5 * 1024 * 1024


class EngineUnavailable(Exception):
    """No engine could be fetched and no cache exists."""


# ── Module state ────────────────────────────────────────────────────────────
_router_server = None  # only set when WE embedded it
_router_port: int | None = None
_router_lock = threading.Lock()
_router_failed_until = 0.0
_catalog: list[dict] = []
_catalog_fetched_at = 0.0
_probe_miss_until = 0.0


# ── Engine fetch-from-URL ───────────────────────────────────────────────────


def engine_cache_path() -> Path:
    """Cache tier path for the fetched engine."""
    from core.storage_paths import cache_dir

    return cache_dir() / "engine_local.py"


def _cache_dir() -> Path:
    from core.storage_paths import cache_dir

    p = cache_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _download(url: str) -> bytes:
    """Fetch the engine, with the Akili UA (router 403s default agents)."""
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(http2=False) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=30.0,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                # Bound the read: a compromised/buggy upstream must not be
                # able to OOM the app with an unbounded body.
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_ENGINE_BYTES:
                        raise EngineUnavailable("Engine download exceeds the size bound")
                    chunks.append(chunk)
                return b"".join(chunks)
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                import asyncio

                await asyncio.sleep(1.0)
    raise EngineUnavailable(f"Could not fetch engine: {last_exc}")


def _validate(data: bytes) -> str:
    """Verify the download looks like the router engine. Returns version label."""
    if len(data) > MAX_ENGINE_BYTES:
        raise EngineUnavailable("Engine download exceeds the size bound")
    if b'if __name__ == "__main__":' not in data:
        raise EngineUnavailable("Engine download failed the main-guard check")
    match = VERSION_RE.search(data)
    if not match:
        raise EngineUnavailable("Engine download has no VERSION token")
    label = match.group(1).decode("utf-8", "replace")
    label = re.sub(r"[^A-Za-z0-9.+_-]", "", label)[:40]
    return label


def _load_module(path: Path):
    """Import the engine module and require acquire_server."""
    spec = importlib.util.spec_from_file_location(MODULE_NAME, str(path))
    if spec is None or spec.loader is None:
        raise EngineUnavailable("Engine path must end in .py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "acquire_server", None)):
        raise EngineUnavailable("Engine has no acquire_server contract")
    return module


async def load_engine():
    """Fetch a fresh engine, or fall back to the cached one.

    Order matters: validate → write tmp → import tmp → atomic replace.
    A bad upstream never overwrites last-known-good.
    """
    import anyio

    cache = engine_cache_path()
    # PID-suffixed tmp: two processes starting together must not
    # truncate each other's download (lm-router uses the same pattern).
    tmp = cache.with_name(f"{cache.stem}.{os.getpid()}.new.py")
    try:
        data = await _download(ENGINE_URL)
        version = _validate(data)
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        module = await anyio.to_thread.run_sync(_load_module, tmp)
        os.replace(tmp, cache)
        return module, f"fetched {version}"
    except Exception as exc:
        logger.warning("engine fetch failed: %r", exc)
        with __import__("contextlib").suppress(Exception):
            tmp.unlink(missing_ok=True)
    try:
        data = cache.read_bytes()
        version = _validate(data)
        module = await anyio.to_thread.run_sync(_load_module, cache)
        return module, f"cached {version}"
    except Exception as exc:
        raise EngineUnavailable(f"Could not reach {ENGINE_URL} and no cached engine.") from exc


# ── Router discovery ────────────────────────────────────────────────────────


async def _probe_existing_router() -> int | None:
    """Scan 8082..8092 for a live Kiri router.

    A full miss is remembered for PROBE_MISS_TTL so the 3s watchdog stops
    paying a serial 11-port scan while nothing is listening.
    """
    global _probe_miss_until
    if time.monotonic() < _probe_miss_until:
        return None
    try:
        async with httpx.AsyncClient(http2=False) as client:
            for port in range(ROUTER_BASE_PORT, ROUTER_BASE_PORT + ROUTER_SPAN + 1):
                try:
                    resp = await client.get(f"http://{ROUTER_HOST}:{port}/health", timeout=0.5)
                    if resp.status_code == 200 and resp.json().get("adapter") == "kiri-router":
                        _probe_miss_until = 0.0
                        return port
                except Exception:
                    pass  # closed port or not a router — keep scanning
    except Exception as exc:
        # A broken probe is NOT a miss. Never poison the TTL.
        logger.debug("router scan failed: %r", exc)
        return None
    _probe_miss_until = time.monotonic() + PROBE_MISS_TTL
    return None


async def probe_router() -> tuple[str, int | None]:
    """Report the router's live status without starting anything.

    Returns (status, port): ready | stopped | unavailable | starting.
    """
    with _router_lock:
        port = _router_port
    if port is None:
        found = await _probe_existing_router()
        if found is None:
            return ("unavailable", None)
        return ("ready", found)
    try:
        async with httpx.AsyncClient(http2=False) as client:
            resp = await client.get(f"http://{ROUTER_HOST}:{port}/health", timeout=2.0)
        if resp.status_code == 200:
            return ("ready", port)
    except Exception as exc:
        logger.debug("router health probe failed on %s: %r", port, exc)
    return ("stopped", port)


async def ensure_router(*, verify: bool = False) -> int | None:
    """Attach to a running Kiri router, or embed one. Returns its port."""
    global _router_server, _router_port, _probe_miss_until, _router_failed_until
    with _router_lock:
        known = _router_port
    if known is not None:
        if not verify:
            return known
        status, _port = await probe_router()
        if status == "ready":
            return known
        with _router_lock:
            if _router_port == known:
                _router_port = None
        _probe_miss_until = 0.0
        logger.info("router on %s is gone; re-attaching", known)

    _publish_status("starting", None)

    existing = await _probe_existing_router()
    if existing is None:
        stop_router()
    if existing is not None:
        _router_port = existing
        _publish_status("ready", existing)
        logger.info("router: attached to existing instance on %d", existing)
        return existing

    try:
        engine, how = await load_engine()
        logger.info("router: engine %s", how)
        server, port = engine.acquire_server(ROUTER_BASE_PORT, ROUTER_SPAN)
        if server is None:
            _router_port = port
            _probe_miss_until = 0.0
            _publish_status("ready", port)
            logger.info("router: attached to instance on %d", port)
            return port
        server.access_log = False
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with _router_lock:
            _router_server, _router_port = server, port
        _probe_miss_until = 0.0
        _publish_status("ready", port)
        logger.info("router: embedded on %s:%d", ROUTER_HOST, port)
        return port
    except EngineUnavailable as exc:
        logger.warning("router: %s", exc)
        _publish_status("unavailable", None)
        return None
    except SystemExit:
        logger.warning("router: no free port in %d..%d", ROUTER_BASE_PORT, ROUTER_BASE_PORT + ROUTER_SPAN)
        _publish_status("unavailable", None)
        return None
    except Exception as exc:
        logger.warning("router: failed to start: %r", exc)
        _publish_status("unavailable", None)
        return None


def _publish_status(status: str, port: int | None) -> None:
    """Write router lifecycle to observable state, only on a real change."""
    if state.router_status != status or state.router_port != port:
        state.router_status = status
        state.router_port = port


def stop_router() -> None:
    """Stop ONLY an embedded router (never the user's own instance)."""
    global _router_server, _router_port
    with _router_lock:
        server, _router_server = _router_server, None
        _router_port = None
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
            logger.info("router: stopped embedded instance")
        except Exception:
            pass
        _publish_status("stopped", None)


def shutdown() -> None:
    stop_router()


def _mark_router_failed() -> None:
    global _router_failed_until
    _router_failed_until = time.monotonic() + ROUTER_STICKY_COOLDOWN


async def router_base() -> str | None:
    """The /v1 base every engine uses, or None during the sticky cooldown."""
    if time.monotonic() < _router_failed_until:
        return None
    port = await ensure_router()
    if port is None:
        return None
    return f"http://{ROUTER_HOST}:{port}/v1"


# ── Catalog (picker display only — never used to pick) ──────────────────────


async def _fetch_catalog(client: httpx.AsyncClient, base: str) -> list[dict]:
    """Refresh the picker's snapshot of ACTIVE chat-completion models."""
    global _catalog, _catalog_fetched_at
    data: list[dict] = []
    for attempt in range(2):
        try:
            resp = await client.get(f"{base}/models", timeout=30.0)
            data = resp.json().get("data", [])
            break
        except Exception as exc:
            logger.warning("catalog failed (attempt %d): %r", attempt + 1, exc)
            if attempt == 0:
                import asyncio

                await asyncio.sleep(1.0)
    if not data:
        return _catalog
    _catalog_fetched_at = time.monotonic()
    _catalog = [m for m in data if m.get("id") and str(m.get("status") or "active") == "active" and "chat.completion" in str(m.get("endpoint_type") or "")]
    _catalog.sort(
        key=lambda m: (
            0 if str(m.get("id")).lower() == "auto" else 1,
            m.get("latency_ms") if isinstance(m.get("latency_ms"), int) else 10**9,
        )
    )
    return _catalog


async def refresh_catalog() -> list[dict]:
    """Attach if needed, then pull a fresh active-model snapshot (picker)."""
    try:
        port = await ensure_router()
        if port is None:
            return snapshot_models()
        async with httpx.AsyncClient(http2=False) as client:
            await _fetch_catalog(client, f"http://{ROUTER_HOST}:{port}/v1")
    except Exception as exc:
        logger.warning("catalog refresh failed: %r", exc)
    snapshot = snapshot_models()
    state.model_catalog = snapshot
    return snapshot


def _hint(entry: dict) -> str:
    """Human hint: latency + rate-limit info from the router catalog."""
    parts: list[str] = []
    latency = entry.get("latency_ms")
    if isinstance(latency, int) and latency >= 0:
        parts.append(f"{latency}ms" if latency < 1000 else f"{latency / 1000:.1f}s")
    rate = entry.get("rate_hint") or {}
    if isinstance(rate, dict) and rate.get("label"):
        parts.append(str(rate["label"]))
    status = str(entry.get("status") or "active")
    if status == "rate limited":
        parts.append("rate limited right now")
    elif status == "failed":
        parts.append("failing right now")
    if entry.get("id") == "auto" and not parts:
        parts.append("Rotates across available models")
    return " · ".join(parts) or "free tier"


def snapshot_models() -> list[dict]:
    """Active chat-completion models (auto first, then by latency) with hints."""
    return [{"id": m.get("id"), "hint": _hint(m), "status": m.get("status", "active")} for m in _catalog]


def model_hint(model_id: str) -> str:
    for entry in _catalog:
        if entry.get("id") == model_id:
            return _hint(entry)
    return ""


def catalog_fetched() -> bool:
    """True once a catalog fetch has succeeded (even if empty)."""
    return _catalog_fetched_at > 0.0


# ── Candidate walk (ported from DDGS ai_service.py) ─────────────────────────
# One sick upstream must not end the turn: the walk tries the user's pick
# first, then the active high/medium pool by latency, skipping models with
# an open circuit breaker. The router's own `auto` rides last — it may
# still reach a model the catalog missed.

PICKABLE_TIERS = ("high", "medium")
MODEL_CIRCUIT_TTL = 300.0
_model_failed_until: dict[str, float] = {}


def _tier(entry: dict) -> str:
    rate = entry.get("rate_hint") or {}
    tier = str(rate.get("tier") or "").lower() if isinstance(rate, dict) else ""
    return tier or "low"


def mark_model_failed(model_id: str) -> None:
    """Open the circuit for one model after a walk-worthy failure."""
    if model_id and model_id.lower() != "auto":
        _model_failed_until[model_id] = time.monotonic() + MODEL_CIRCUIT_TTL


def model_circuit_open(model_id: str) -> bool:
    """True while a recent failure keeps this model out of the walk."""
    return _model_failed_until.get(model_id, 0.0) > time.monotonic()


def candidate_models(*, exclude: tuple[str, ...] = ()) -> list[str]:
    """Fallback order: high tier first, then medium, each by latency.

    "auto" is the router's own pick, never a fallback candidate. An
    explicit exclude skips models that just failed this turn; an open
    circuit breaker skips a model that failed recently.
    """
    skipped = {str(e) for e in exclude}
    ranked: list[tuple[int, int, str]] = []
    for m in _catalog:
        mid = str(m.get("id") or "")
        if not mid or mid.lower() == "auto" or mid in skipped:
            continue
        if str(m.get("status") or "active") != "active":
            continue
        if model_circuit_open(mid):
            continue
        if _tier(m) not in PICKABLE_TIERS:
            continue
        lat = m.get("latency_ms")
        ranked.append(
            (
                0 if _tier(m) == "high" else 1,
                lat if isinstance(lat, int) else 10**9,
                mid,
            )
        )
    ranked.sort()
    return [mid for _, _, mid in ranked]


def turn_candidates(chosen: str) -> list[str]:
    """The order a turn walks its candidates.

    An explicit pick goes first, verbatim. `auto` means "the ranked best
    right now": the tier-then-latency pool leads and the router's own
    `auto` rides last as the final resort.
    """
    pool = candidate_models()
    if str(chosen or "").strip().lower() == "auto":
        return [*pool, "auto"]
    return [chosen, *[m for m in pool if m != chosen]]
