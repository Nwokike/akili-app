"""Router engine tests — validation, cache fallback, discovery contract."""

import pytest

from agent import engine as router


def test_validate_accepts_valid_engine():
    data = b'VERSION = "1.0.0"\n\nif __name__ == "__main__":\n    pass\n'
    assert router._validate(data) == "1.0.0"


def test_validate_rejects_missing_main_guard():
    with pytest.raises(router.EngineUnavailable):
        router._validate(b'VERSION = "1.0.0"\nprint("hi")\n')


def test_validate_rejects_missing_version():
    with pytest.raises(router.EngineUnavailable):
        router._validate(b'if __name__ == "__main__":\n    pass\n')


def test_validate_sanitizes_label():
    data = b'VERSION = "v1.0<script>"\nif __name__ == "__main__": pass\n'
    assert "<" not in router._validate(data)


def test_publish_status_only_on_change(fake_storage):
    from core.state import state

    state.router_status = "starting"
    state.router_port = None
    router._publish_status("ready", 8082)
    assert state.router_status == "ready"
    assert state.router_port == 8082


def test_server_params_are_valid_objects():
    """build_server_params is in mcp_hub, but the router contract is the /v1 base."""
    base = f"http://{router.ROUTER_HOST}:{router.ROUTER_BASE_PORT}/v1"
    assert base == "http://127.0.0.1:8082/v1"


@pytest.mark.asyncio
async def test_probe_existing_router_respects_miss_ttl(monkeypatch):
    """A recorded miss short-circuits the 11-port scan."""
    router._probe_miss_until = 0.0
    monkeypatch.setattr(router, "_probe_miss_until", 10**12)
    assert await router._probe_existing_router() is None


def test_snapshot_models_shape():
    snap = router.snapshot_models()
    assert isinstance(snap, list)


def test_validate_accepts_single_quotes():
    # VERSION_RE tolerates single quotes; the main guard stays strict.
    data = b"VERSION = '2.3.4'\nif __name__ == \"__main__\": pass\n"
    assert router._validate(data) == "2.3.4"


def test_validate_rejects_oversize_download():
    with pytest.raises(router.EngineUnavailable):
        router._validate(b"x" * (router.MAX_ENGINE_BYTES + 1))


def _catalog_row(mid, *, tier="high", status="active", latency=100):
    return {
        "id": mid,
        "status": status,
        "endpoint_type": "chat.completion",
        "latency_ms": latency,
        "rate_hint": {"tier": tier, "label": f"{tier} tier"},
    }


def test_candidate_models_tier_filter_and_order():
    router._catalog = [
        _catalog_row("m-low", tier="low", latency=10),
        _catalog_row("m-high", tier="high", latency=200),
        _catalog_row("m-med", tier="medium", latency=50),
        _catalog_row("auto", tier="high", latency=1),
        _catalog_row("m-dead", tier="high", status="failed", latency=1),
    ]
    # auto excluded, failed excluded, low tier excluded; high before medium, latency within tier.
    assert router.candidate_models() == ["m-high", "m-med"]


def test_candidate_models_exclude_and_breaker():
    router._catalog = [_catalog_row("a"), _catalog_row("b")]
    assert router.candidate_models(exclude=("a",)) == ["b"]
    router.mark_model_failed("b")
    assert router.candidate_models() == ["a"]


def test_circuit_breaker_expires():
    import time

    router._model_failed_until.clear()
    router.mark_model_failed("x")
    assert router.model_circuit_open("x") is True
    # Simulate TTL elapsing.
    router._model_failed_until["x"] = time.monotonic() - 1.0
    assert router.model_circuit_open("x") is False


def test_mark_model_failed_ignores_auto():
    router.mark_model_failed("auto")
    assert router.model_circuit_open("auto") is False


def test_turn_candidates_explicit_pick_first():
    router._catalog = [_catalog_row("a"), _catalog_row("b")]
    assert router.turn_candidates("b") == ["b", "a"]


def test_turn_candidates_auto_pools_then_auto():
    router._catalog = [_catalog_row("a"), _catalog_row("b")]
    assert router.turn_candidates("auto") == ["a", "b", "auto"]


def test_turn_candidates_unknown_pick_still_first():
    router._catalog = [_catalog_row("a")]
    # An explicit pick is honored verbatim even if the catalog lacks it —
    # the router may still resolve it.
    assert router.turn_candidates("brand-new-model") == ["brand-new-model", "a"]
