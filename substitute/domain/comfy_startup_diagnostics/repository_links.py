#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Normalize trusted repository links for Comfy startup diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse, urlunparse

_GITHUB_ID_PATTERN = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_GITHUB_SSH_PATTERN = re.compile(
    r"^git@github\.com:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtensionRepositoryLinks:
    """Describe trusted external links for a startup extension."""

    repository_url: str
    issues_url: str | None
    source: str


def repository_links_from_github_id(
    github_id: str,
    *,
    source: str,
) -> ExtensionRepositoryLinks | None:
    """Return repository links from an owner/repo identifier."""

    match = _GITHUB_ID_PATTERN.match(github_id.strip())
    if match is None:
        return None
    return _github_links(
        owner=match.group("owner"),
        repo=match.group("repo"),
        source=source,
    )


def normalize_repository_links(
    url: str,
    *,
    source: str,
) -> ExtensionRepositoryLinks | None:
    """Return repository links from a trusted repository URL."""

    stripped = url.strip()
    if not stripped or _looks_like_local_path(stripped):
        return None
    ssh_match = _GITHUB_SSH_PATTERN.match(stripped)
    if ssh_match is not None:
        return _github_links(
            owner=ssh_match.group("owner"),
            repo=ssh_match.group("repo"),
            source=source,
        )
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.netloc.casefold() == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return None
        return _github_links(
            owner=parts[0],
            repo=parts[1],
            source=source,
        )
    if parsed.scheme == "https":
        return ExtensionRepositoryLinks(
            repository_url=urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path.rstrip("/"),
                    "",
                    "",
                    "",
                )
            ),
            issues_url=None,
            source=source,
        )
    return None


def _github_links(
    *,
    owner: str,
    repo: str,
    source: str,
) -> ExtensionRepositoryLinks | None:
    """Return normalized GitHub links for a validated owner/repo pair."""

    normalized_repo = repo.removesuffix(".git").strip("/")
    normalized_owner = owner.strip("/")
    if not normalized_owner or not normalized_repo:
        return None
    repository_url = f"https://github.com/{normalized_owner}/{normalized_repo}"
    return ExtensionRepositoryLinks(
        repository_url=repository_url,
        issues_url=f"{repository_url}/issues",
        source=source,
    )


def _looks_like_local_path(value: str) -> bool:
    """Return whether a value looks like a local filesystem path."""

    return (
        re.match(r"^[A-Za-z]:[\\/]", value) is not None
        or value.startswith("\\\\")
        or value.startswith("/")
        or value.startswith(".\\")
        or value.startswith("./")
    )


__all__ = [
    "ExtensionRepositoryLinks",
    "normalize_repository_links",
    "repository_links_from_github_id",
]
