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

"""Resolve immutable revisions for catalog-confirmed GitHub repositories."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from sugarsubstitute_shared.tls import SystemTrustTlsContext

_REQUEST_TIMEOUT_SECONDS = 30
_MAX_RESPONSE_BYTES = 1024 * 1024
_GITHUB_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+\Z")
_COMMIT_ID = re.compile(r"[0-9a-fA-F]{40}\Z")


class InvalidGitHubRepositoryRevisionError(RuntimeError):
    """Report repository metadata that cannot establish an immutable revision."""


class GitHubRepositoryRevisionClient:
    """Resolve a repository's current default-branch head to an exact commit."""

    def resolve_head(self, repository_url: str) -> str:
        """Return the immutable commit currently addressed by repository HEAD."""

        identity = canonical_github_repository_identity(repository_url)
        if identity is None:
            raise InvalidGitHubRepositoryRevisionError(
                "Repository URL is not a canonical public GitHub repository."
            )
        owner, repository = identity
        endpoint = (
            "https://api.github.com/repos/"
            f"{urllib.parse.quote(owner, safe='')}/"
            f"{urllib.parse.quote(repository, safe='')}/commits/HEAD"
        )
        payload = _request_json(endpoint)
        commit_id = payload.get("sha") if isinstance(payload, dict) else None
        if not isinstance(commit_id, str) or not _COMMIT_ID.fullmatch(commit_id):
            raise InvalidGitHubRepositoryRevisionError(
                "GitHub did not return an exact repository HEAD commit."
            )
        return commit_id.casefold()


def canonical_github_repository_url(value: object) -> str | None:
    """Return a credential-free two-segment HTTPS GitHub repository URL."""

    identity = canonical_github_repository_identity(value)
    if identity is None:
        return None
    owner, repository = identity
    return f"https://github.com/{owner}/{repository}"


def canonical_github_repository_identity(value: object) -> tuple[str, str] | None:
    """Return validated owner and repository segments for one public URL."""

    if not isinstance(value, str):
        return None
    parsed = urllib.parse.urlsplit(value.strip())
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.hostname.casefold() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) != 2:
        return None
    owner, repository = segments
    repository = repository.removesuffix(".git")
    if not _GITHUB_SEGMENT.fullmatch(owner) or not _GITHUB_SEGMENT.fullmatch(
        repository
    ):
        return None
    return owner, repository


def _request_json(url: str) -> object:
    """Fetch one bounded JSON document from the fixed GitHub API origin."""

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SugarSubstitute",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(  # noqa: S310 - fixed GitHub API origin.
        request,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        context=SystemTrustTlsContext.create(),
    ) as response:
        raw_payload = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw_payload) > _MAX_RESPONSE_BYTES:
        raise InvalidGitHubRepositoryRevisionError(
            "GitHub repository metadata exceeds the size limit."
        )
    try:
        return json.loads(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidGitHubRepositoryRevisionError(
            "GitHub returned invalid repository revision metadata."
        ) from error


__all__ = [
    "GitHubRepositoryRevisionClient",
    "InvalidGitHubRepositoryRevisionError",
    "canonical_github_repository_identity",
    "canonical_github_repository_url",
]
