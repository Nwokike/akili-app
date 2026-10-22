"""In-memory log ring + telemetry for the settings terminal viewer.

Ported from Sherlock's logger_handler.py (the house standard).
"""

from __future__ import annotations

import contextlib
import logging
from collections import deque


class MemoryLogHandler(logging.Handler):
    """A 500-entry ring buffer of formatted log records."""

    _logs: deque[str] = deque(maxlen=500)

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            MemoryLogHandler._logs.append(self.format(record))

    @classmethod
    def get_logs(cls) -> list[str]:
        return list(cls._logs)

    @classmethod
    def clear_logs(cls) -> None:
        cls._logs.clear()


in_memory_log_handler = MemoryLogHandler()


def ensure_attached() -> None:
    """Attach the ring to the root logger once."""
    root = logging.getLogger()
    if in_memory_log_handler not in root.handlers:
        root.addHandler(in_memory_log_handler)


def get_telemetry_snapshot() -> str:
    """One-line device telemetry for the terminal header (best-effort)."""
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        try:
            battery = psutil.sensors_battery()
            bat = f"{int(battery.percent)}%" if battery else "n/a"
        except Exception:
            bat = "n/a"
        return f"CPU {cpu:.0f}% · RAM {mem.percent:.0f}% · BAT {bat}"
    except Exception:
        return "telemetry unavailable"
