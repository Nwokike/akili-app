"""Never-blocking token counting.

Ported from DDGS tokenizer.py (the house standard).

The router serves models whose tokenizer tiktoken does not know
(`auto`, the free catalog). kani's lazy `tokenizer` property calls
tiktoken.get_encoding() for unknown models, which DOWNLOADS the BPE ranks
with no timeout — a 30-60s stall inside the first turn. Hand kani an
encoding our own bounded loader resolved, or a heuristic.

Context budgeting only needs approximations.
"""

from __future__ import annotations

import math
import os


class HeuristicTokenizer:
    """~4 chars/token. Format-compatible with tiktoken's Encoding."""

    def encode(self, text: str) -> list[int]:
        if not text:
            return []
        return [0] * max(1, math.ceil(len(text) / 4))

    def encode_ordinary(self, text: str) -> list[int]:
        return self.encode(text)

    def decode(self, tokens) -> str:
        return ""


def _tiktoken_warm() -> bool:
    """True only when a real tiktoken BPE cache exists and is non-empty."""
    cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR", "")
    if not cache_dir or not os.path.isdir(cache_dir):
        return False
    try:
        return any(os.scandir(cache_dir))
    except Exception:
        return False


def tokenizer_or_heuristic(model_id: str):
    """Real tiktoken only when the cache is warm; else the heuristic.

    Never lets a cold BPE download sit on the turn path.
    """
    if not _tiktoken_warm():
        return HeuristicTokenizer()
    try:
        import tiktoken

        return tiktoken.encoding_for_model(model_id)
    except Exception:
        try:
            import tiktoken

            return tiktoken.get_encoding("o200k_base")
        except Exception:
            return HeuristicTokenizer()
