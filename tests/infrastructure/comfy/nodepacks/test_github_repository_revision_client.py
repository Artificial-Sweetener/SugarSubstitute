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

"""Tests for immutable GitHub repository revision resolution."""

from __future__ import annotations

import json
from typing import Self

import pytest

from substitute.infrastructure.comfy.github_repository_revision_client import (
    GitHubRepositoryRevisionClient,
    InvalidGitHubRepositoryRevisionError,
    canonical_github_repository_url,
)

_REVISION = "3740add9dbdc9f254a2befda30e95ba95e3b115d"


class _Response:
    """Expose a bounded urllib response around one JSON fixture."""

    def __init__(self, payload: object) -> None:
        """Encode one response payload."""

        self._raw = json.dumps(payload).encode()

    def __enter__(self) -> Self:
        """Enter the response context."""

        return self

    def __exit__(self, *_args: object) -> None:
        """Leave the response context."""

    def read(self, _size: int) -> bytes:
        """Return the encoded response."""

        return self._raw


def test_resolves_canonical_repository_head_to_exact_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approval must retain an immutable commit rather than moving HEAD."""

    requested_urls: list[str] = []

    def fake_urlopen(request: object, **_kwargs: object) -> _Response:
        requested_urls.append(str(getattr(request, "full_url")))
        return _Response({"sha": _REVISION})

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.github_repository_revision_client.urllib.request.urlopen",
        fake_urlopen,
    )

    revision = GitHubRepositoryRevisionClient().resolve_head(
        "https://github.com/blue-pen5805/ComfyUI-krea2-negpip"
    )

    assert revision == _REVISION
    assert requested_urls == [
        "https://api.github.com/repos/blue-pen5805/ComfyUI-krea2-negpip/commits/HEAD"
    ]


def test_rejects_unsafe_urls_and_non_commit_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credentials, malformed ports, and symbolic responses must fail closed."""

    assert (
        canonical_github_repository_url("https://user:secret@github.com/owner/repo")
        is None
    )
    assert canonical_github_repository_url("https://github.com:bad/owner/repo") is None
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.github_repository_revision_client.urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response({"sha": "main"}),
    )
    with pytest.raises(InvalidGitHubRepositoryRevisionError, match="exact"):
        GitHubRepositoryRevisionClient().resolve_head(
            "https://github.com/owner/repository"
        )
