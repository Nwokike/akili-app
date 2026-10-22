"""Update check — version.json fetch with build-number comparison.

Ported from Sherlock's update_service.py (the house standard).
4s fast-fail; offline or up-to-date returns None (never disturbs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class UpdateInfo:
    version: str
    build_number: int
    type: str  # "update" | "announcement"
    title: str
    release_notes: str
    mandatory: bool
    github_url: str
    playstore_url: str
    action_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "build_number": self.build_number,
            "type": self.type,
            "title": self.title,
            "release_notes": self.release_notes,
            "mandatory": bool(self.mandatory),
            "github_url": self.github_url,
            "playstore_url": self.playstore_url,
            "action_url": self.action_url,
        }


class UpdateService:
    """Fetches the remote version feed and reports newer builds."""

    def __init__(self, config_url: str, app_build_number: int, github_url: str, playstore_url: str):
        self.config_url = config_url
        self.app_build_number = app_build_number
        self.github_url = github_url
        self.playstore_url = playstore_url

    async def check_for_update(self) -> dict | None:
        """Return an UpdateInfo dict when a newer build exists, else None."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(self.config_url)
                if resp.status_code != 200:
                    return None
                data = resp.json()
        except Exception as exc:
            logger.debug("update check failed: %s", exc)
            return None
        if not isinstance(data, dict):
            return None
        try:
            server_build = int(data.get("build_number", 0))
        except (TypeError, ValueError):
            return None
        if server_build <= self.app_build_number:
            return None
        info = UpdateInfo(
            version=str(data.get("version", "")),
            build_number=server_build,
            type=str(data.get("type", "update")),
            title=str(data.get("title", "")),
            release_notes=str(data.get("release_notes", "")),
            mandatory=bool(data.get("mandatory", False)),
            github_url=str(data.get("github_url") or self.github_url),
            playstore_url=str(data.get("playstore_url") or self.playstore_url),
            action_url=data.get("action_url"),
        )
        return info.to_dict()
