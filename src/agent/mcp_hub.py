"""MCP hub: user-registered servers become kani tools.

Ported from lm-router mcp.py (the house standard — the hard-won
cancel-scope safety must be preserved verbatim).

Enabled stdio/remote servers are connected ONCE and held open for the app
lifetime. The session context is owned by ONE long-lived task (serve()):
anyio cancel scopes MUST be entered and exited in the same task — closing
from a later portal task raises "Attempted to exit cancel scope in a
different task", which unwinds the portal's task group and permanently
bricks the agent. Callers only signal via threading events.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shlex
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
from kani.mcp import tools_from_mcp_servers
from mcp.client.session_group import (
    SseServerParameters,
    StdioServerParameters,
    StreamableHttpParameters,
)
from mcp.client.stdio import get_default_environment

from core.constants import MCP_CONNECT_TIMEOUT as CONNECT_TIMEOUT
from core.constants import MCP_DESC_CAP
from core.constants import MCP_DIAGNOSE_TIMEOUT as DIAGNOSE_TIMEOUT

logger = logging.getLogger(__name__)

# Track every client the SDK opens so WE can close it in the task that
# entered it, immediately, deterministically.
_PENDING_CLIENTS: list = []


class _TrackedClient:
    """Wraps an SDK client ACM just to remember it until it is closed."""

    def __init__(self, acm) -> None:
        self._acm = acm

    async def __aenter__(self):
        value = await self._acm.__aenter__()
        _PENDING_CLIENTS.append(self)
        return value

    async def __aexit__(self, *exc_info):
        try:
            return await self._acm.__aexit__(*exc_info)
        finally:
            with contextlib.suppress(ValueError):
                _PENDING_CLIENTS.remove(self)


def _track_client(factory):
    def tracked(*args, **kwargs):
        return _TrackedClient(factory(*args, **kwargs))

    return tracked


import mcp as _mcp_pkg  # noqa: E402
import mcp.client.session_group as _mcp_sg  # noqa: E402

_mcp_pkg.stdio_client = _track_client(_mcp_pkg.stdio_client)
_mcp_sg.sse_client = _track_client(_mcp_sg.sse_client)
_mcp_sg.streamable_http_client = _track_client(_mcp_sg.streamable_http_client)


async def _drain_pending_clients() -> None:
    """Close abandoned client generators IN THIS TASK (bounded)."""
    while _PENDING_CLIENTS:
        tracked = _PENDING_CLIENTS.pop()
        gen = getattr(tracked._acm, "gen", None)
        if gen is None:
            continue
        with contextlib.suppress(BaseException):
            async with asyncio.timeout(5.0):
                await gen.aclose()


@dataclass
class MCPServerConfig:
    """One user-registered MCP server."""

    name: str
    transport: str = "streamable_http"  # stdio | sse | streamable_http
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    timeout: float | None = None
    sse_read_timeout: float | None = None
    disabled_tools: list[str] = field(default_factory=list)
    enabled: bool = True
    builtin: bool = False  # built-in servers ship with the app and can't be deleted

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "transport": self.transport,
            "command": self.command,
            "args": list(self.args),
            "url": self.url,
            "headers": dict(self.headers),
            "env": dict(self.env),
            "cwd": self.cwd,
            "timeout": self.timeout,
            "sse_read_timeout": self.sse_read_timeout,
            "disabled_tools": list(self.disabled_tools),
            "enabled": self.enabled,
            "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MCPServerConfig:
        return cls(
            name=str(data.get("name") or ""),
            transport=str(data.get("transport") or "streamable_http"),
            command=str(data.get("command") or ""),
            args=list(data.get("args") or []),
            url=str(data.get("url") or ""),
            headers=dict(data.get("headers") or {}),
            env=dict(data.get("env") or {}),
            cwd=str(data.get("cwd") or ""),
            timeout=data.get("timeout"),
            sse_read_timeout=data.get("sse_read_timeout"),
            disabled_tools=list(data.get("disabled_tools") or []),
            enabled=bool(data.get("enabled", True)),
            builtin=bool(data.get("builtin", False)),
        )


def builtin_exa_server() -> MCPServerConfig:
    """The Exa search server, built in and non-removable.

    Seeded into the hub at boot. Users may toggle it on/off and disable
    individual tools from Settings, but it is never deleted and no custom
    servers can be added (per owner direction).
    """
    return MCPServerConfig(
        name="Exa",
        transport="streamable_http",
        url="https://mcp.exa.ai/mcp",
        builtin=True,
        enabled=True,
    )


def builtin_parallel_server() -> MCPServerConfig:
    """The Parallel web search server, built in and non-removable.

    Seeded alongside Exa at boot: Exa is primary (web_search_exa +
    web_fetch_exa), Parallel is the always-present independent fallback
    (web_search + web_fetch) for when Exa is down — two providers, no
    API keys, both free at the anonymous tier. Users may toggle it or
    per-tool it in Settings, never delete it.
    """
    return MCPServerConfig(
        name="Parallel",
        transport="streamable_http",
        url="https://search.parallel.ai/mcp",
        builtin=True,
        enabled=True,
    )


class MCPError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind  # unreachable | protocol | auth | tool | config | schema


_LAUNCHER_HINTS = {
    "uvx": "Install uv (https://docs.astral.sh/uv/) so `uvx` is on your PATH, or add a streamable_http server instead.",
    "uv": "Install uv (https://docs.astral.sh/uv/) or add a streamable_http server instead.",
    "npx": "Install Node.js so `npx` is on your PATH, or add a streamable_http server instead.",
    "node": "Install Node.js so `node` is on your PATH, or add a streamable_http server instead.",
    "deno": "Install Deno, or add a streamable_http server instead.",
    "bunx": "Install Bun, or add a streamable_http server instead.",
}


def _preflight_command(server: MCPServerConfig) -> str:
    """Fail fast, legibly, when the stdio launcher is not installed."""
    command = str(server.command or "").strip()
    if not command or any(ch in command for ch in "/\\"):
        return command
    resolved = shutil.which(command)
    if resolved:
        return resolved
    hint = _LAUNCHER_HINTS.get(command.lower(), f"Make sure `{command}` is installed and on your PATH.")
    raise MCPError(
        "config",
        f"`{command}` was not found on this device, so the {server.name!r} MCP server cannot start. {hint}",
    )


def split_stdio_command(target: str) -> tuple[str, list[str]]:
    """Split a pasted command line into command + args."""
    try:
        parts = shlex.split(str(target), posix=False)
    except ValueError:
        raise ValueError("Quotes are unbalanced in your command.") from None
    tokens = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    if not tokens:
        raise ValueError("Enter a command, for example: npx -y package-name")
    return tokens[0], tokens[1:]


def build_server_params(server: MCPServerConfig, is_mobile: bool = False) -> object:
    if server.transport == "stdio":
        if is_mobile:
            raise MCPError(
                "config",
                "stdio transport is not supported on mobile devices. Use streamable_http or sse.",
            )
        if not server.command:
            raise MCPError("config", "stdio server needs a command")
        env = None
        if server.env:
            env = {**get_default_environment(), **{str(k): str(v) for k, v in server.env.items()}}
        return StdioServerParameters(
            command=_preflight_command(server),
            args=list(server.args),
            env=env,
            cwd=str(server.cwd) if server.cwd else None,
        )
    url = str(server.url) if server.url else None
    if not url:
        raise MCPError("config", "remote server needs a url")
    headers = dict(server.headers) or None
    if server.transport == "sse":
        kwargs: dict = {"url": url, "headers": headers}
        if server.timeout is not None:
            kwargs["timeout"] = float(server.timeout)
        if server.sse_read_timeout is not None:
            kwargs["sse_read_timeout"] = float(server.sse_read_timeout)
        return SseServerParameters(**kwargs)
    kwargs = {"url": url, "headers": headers}
    if server.timeout is not None:
        kwargs["timeout"] = timedelta(seconds=server.timeout)
    if server.sse_read_timeout is not None:
        kwargs["sse_read_timeout"] = timedelta(seconds=server.sse_read_timeout)
    return StreamableHttpParameters(**kwargs)


def classify_exception(exc: Exception) -> MCPError:
    text = str(exc)
    if isinstance(exc, MCPError):
        return exc
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return classify_exception(exc.exceptions[0])
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return MCPError("unreachable", "Server unreachable. Check the URL or command.")
    lowered = text.lower()
    if "unauthorized" in lowered or "401" in text or "403" in text:
        return MCPError("auth", "Authentication failed. Check the headers or key.")
    if "protocol" in lowered or "-32601" in text or "-32602" in text or "unsupported protocol version" in lowered:
        return MCPError("protocol", "Server speaks an incompatible MCP protocol version.")
    return MCPError("tool", text[:400])


def _stderr_tail(data: object, limit: int = 240) -> str:
    if isinstance(data, bytes):
        text = data.decode("utf-8", "replace")
    elif isinstance(data, str):
        text = data
    else:
        return ""
    return " ".join(text.split())[-limit:]


async def _stdio_diagnose(server: MCPServerConfig, error: MCPError) -> str:
    """When a stdio child dies during connect, ask it why."""
    if server.transport != "stdio" or error.kind == "config":
        return str(error)
    command = str(server.command or "")
    cmd = shutil.which(command) or command
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            [cmd, *server.args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=DIAGNOSE_TIMEOUT,
        )
        tail = _stderr_tail(proc.stderr) or _stderr_tail(proc.stdout)
    except subprocess.TimeoutExpired as exc:
        tail = _stderr_tail(exc.stderr) or _stderr_tail(exc.stdout)
    except Exception:
        tail = ""
    if not tail:
        return str(error)
    return f"{str(error).rstrip('.')}. Server output: {tail}"


@dataclass
class MCPHub:
    servers: list[MCPServerConfig] = field(default_factory=list)
    is_mobile: bool = False
    tools: list = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    generation: int = 0
    on_status: Callable[[list[str] | None, str | None], None] | None = None
    _contexts: list = field(default_factory=list)
    _reconnect: threading.Event = field(default_factory=threading.Event)
    _stop: threading.Event = field(default_factory=threading.Event)

    def request_reconnect(self) -> None:
        """Thread-safe: wake the owner task to (re)connect the enabled set."""
        self._reconnect.set()

    def request_stop(self) -> None:
        self._stop.set()
        self._reconnect.set()

    def _status(self, error: str | None) -> None:
        if self.on_status is None:
            return
        try:
            self.on_status(list(self.names), error)
        except Exception as exc:
            logger.warning("mcp status callback failed: %s", exc)

    async def serve(self) -> None:
        """Owner task: enter/close the tools context in THIS task only."""
        try:
            while not self._stop.is_set():
                try:
                    await self._connect()
                except Exception as exc:
                    logger.warning("mcp apply failed: %s", exc)
                    self.tools = []
                    self.names = []
                    self.generation += 1
                    self._status(f"MCP connection failed: {str(exc)[:200]}")
                else:
                    self._status(None)
                self._reconnect.clear()
                try:
                    while not self._stop.is_set() and not self._reconnect.is_set():
                        await asyncio.to_thread(self._reconnect.wait, 0.5)
                except asyncio.CancelledError as exc:
                    if self._stop.is_set() or "cancel scope" not in str(exc):
                        raise
                    logger.warning("mcp owner absorbed a foreign cancel; continuing")
                    await asyncio.sleep(1.0)
                except Exception as exc:
                    name = str(exc) or type(exc).__name__
                    if "shutdown" in name or "closed" in name:
                        return
                    logger.warning("mcp owner wait failed: %s", name)
                    self._status(f"MCP error: {name[:150]}")
                    await asyncio.sleep(1.0)
        finally:
            try:
                await self._close_owned()
                await _drain_pending_clients()
            except Exception as exc:
                logger.warning("mcp owner cleanup failed: %s", exc)

    async def _connect(self) -> None:
        """Connect each enabled server on its own."""
        await self._close_owned()
        await _drain_pending_clients()
        servers = [s for s in self.servers if s.enabled]
        if not servers:
            self.generation += 1
            return

        all_tools: list = []
        all_names: list[str] = []
        contexts: list = []
        failed: list[str] = []
        blocked_count = 0

        for server in servers:
            try:
                params = build_server_params(server, is_mobile=self.is_mobile)
            except MCPError as exc:
                logger.warning("mcp %s skipped: %s", server.name, exc)
                failed.append(f"{server.name}: {exc}")
                continue

            blocked = [f"{server.name}.{tool}" for tool in server.disabled_tools]
            blocked_count += len(blocked)
            context = tools_from_mcp_servers(
                [params],
                blocked_tools=blocked or None,
                component_name_hook=lambda name, _info, label=server.name: f"{label}.{name}",
            )
            entered_at = time.monotonic()
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    tools = await context.__aenter__()
            except TimeoutError:
                await _drain_pending_clients()
                logger.warning("mcp %s timed out after %ss; other servers still load", server.name, CONNECT_TIMEOUT)
                failed.append(f"{server.name}: timed out (check your connection)")
                continue
            except asyncio.CancelledError as exc:
                if self._stop.is_set():
                    raise
                if time.monotonic() - entered_at >= CONNECT_TIMEOUT - 0.5:
                    failed.append(f"{server.name}: timed out (check your connection)")
                    continue
                if "cancel scope" not in str(exc):
                    raise
                error = MCPError("tool", "Connection closed") if server.transport == "stdio" else MCPError("unreachable", "Server unreachable. Check the URL or command.")
                detail = await _stdio_diagnose(server, error)
                logger.warning("mcp %s failed during connect: %s", server.name, detail)
                failed.append(f"{server.name}: {detail[:140]}")
                continue
            except Exception as exc:
                error = classify_exception(exc)
                detail = await _stdio_diagnose(server, error)
                logger.warning("mcp %s failed (%s): %s", server.name, error.kind, detail)
                failed.append(f"{server.name}: {detail[:140]}")
                continue
            contexts.append(context)
            all_tools.extend(tools)
            all_names.extend(str(getattr(t, "name", "?")) for t in tools)

        for tool in all_tools:
            desc = getattr(tool, "desc", None)
            if isinstance(desc, str) and len(desc) > MCP_DESC_CAP:
                tool.desc = desc[:MCP_DESC_CAP] + "...(truncated)"
        self._contexts = contexts
        self.tools = all_tools
        self.names = all_names
        self.generation += 1
        logger.info(
            "mcp connected: %d tools from %d/%d servers (%d blocked)",
            len(all_tools),
            len(contexts),
            len(servers),
            blocked_count,
        )
        if failed:
            self._status("Some MCP servers unavailable: " + "; ".join(failed)[:300])
        else:
            self._status(None)

    async def _close_owned(self) -> None:
        """Exit every context — MUST run in the same task that entered them."""
        contexts, self._contexts = self._contexts, []
        for context in contexts:
            try:
                await context.__aexit__(None, None, None)
            except Exception as exc:
                logger.warning("mcp disconnect: %s", exc)
        self._contexts = []
        self.tools = []
        self.names = []
        self.generation += 1

    async def close(self) -> None:
        await self._close_owned()

    async def test(self, server: MCPServerConfig) -> list[dict]:
        """Short-lived connect + list_tools with schema validation for the UI."""
        try:
            params = build_server_params(server, is_mobile=self.is_mobile)
        except MCPError:
            raise
        try:
            context = tools_from_mcp_servers([params])
            tools = await context.__aenter__()
            results: list[dict] = []
            try:
                for t in tools:
                    results.append(
                        {
                            "name": str(getattr(t, "name", "?")),
                            "description": str(getattr(t, "desc", "") or ""),
                            "input_schema": getattr(t, "json_schema", None),
                        }
                    )
                return results
            finally:
                await context.__aexit__(None, None, None)
        except asyncio.CancelledError as exc:
            if "cancel scope" not in str(exc):
                raise
            base = MCPError("tool", "Connection closed") if server.transport == "stdio" else MCPError("unreachable", "Server unreachable. Check the URL or command.")
            raise MCPError(base.kind, await _stdio_diagnose(server, base)) from exc
        except Exception as exc:
            error = classify_exception(exc)
            raise MCPError(error.kind, await _stdio_diagnose(server, error)) from exc
