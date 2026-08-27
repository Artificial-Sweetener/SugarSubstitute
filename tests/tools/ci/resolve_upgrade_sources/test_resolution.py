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

"""Tests for the release qualification upgrade-source matrix."""

from __future__ import annotations

import pytest

from tools.ci.resolve_upgrade_sources import (
    UpgradeSourceResolutionError,
    resolve_upgrade_sources,
)


def test_upgrade_sources_include_latest_three_and_fixed_canary() -> None:
    """Release qualification should follow recent history without losing depth."""

    releases = [
        _release("v0.21.0", prerelease=True),
        _release("v0.20.1"),
        _release("v0.20.0"),
        _release("v0.19.2"),
        _release("v0.19.1"),
        _release("v0.12.2"),
    ]

    matrix = resolve_upgrade_sources(
        repository="example/repository",
        candidate_version="0.21.0",
        fetch_releases=lambda _repository: releases,
    )

    assert matrix == [
        {
            "published_at": "2026-08-12T00:27:36Z",
            "tag": "v0.20.1",
            "version": "0.20.1",
        },
        {
            "published_at": "2026-08-11T23:24:27Z",
            "tag": "v0.20.0",
            "version": "0.20.0",
        },
        {
            "published_at": "2026-08-03T21:54:57Z",
            "tag": "v0.19.2",
            "version": "0.19.2",
        },
        {
            "published_at": "2026-07-18T02:41:03Z",
            "tag": "v0.12.2",
            "version": "0.12.2",
        },
    ]


def test_upgrade_sources_fail_when_history_is_too_shallow() -> None:
    """The release gate must not silently reduce its required upgrade depth."""

    with pytest.raises(UpgradeSourceResolutionError, match="at least 3"):
        resolve_upgrade_sources(
            repository="example/repository",
            candidate_version="0.21.0",
            fetch_releases=lambda _repository: [
                _release("v0.20.1"),
                _release("v0.20.0"),
            ],
        )


def test_upgrade_sources_fail_when_fixed_canary_metadata_is_missing() -> None:
    """Complete qualification must never silently omit its oldest upgrade proof."""

    with pytest.raises(UpgradeSourceResolutionError, match="Fixed canary"):
        resolve_upgrade_sources(
            repository="example/repository",
            candidate_version="0.21.0",
            fetch_releases=lambda _repository: [
                _release("v0.20.1"),
                _release("v0.20.0"),
                _release("v0.19.2"),
            ],
        )


def test_latest_only_upgrade_source_supports_focused_remediation() -> None:
    """Focused remote proof may select one latest history without weakening final depth."""

    matrix = resolve_upgrade_sources(
        repository="example/repository",
        candidate_version="0.21.0",
        selection="latest-only",
        fetch_releases=lambda _repository: [
            _release("v0.20.1"),
            _release("v0.20.0"),
        ],
    )

    assert matrix == [
        {
            "published_at": "2026-08-12T00:27:36Z",
            "tag": "v0.20.1",
            "version": "0.20.1",
        }
    ]


@pytest.mark.parametrize("published_at", [None, "", "not-a-timestamp"])
def test_upgrade_sources_reject_history_without_a_valid_publication_time(
    published_at: str | None,
) -> None:
    """Historical resolution must never silently fall back to today's index."""

    release = _release("v0.20.1")
    release["published_at"] = published_at

    with pytest.raises(UpgradeSourceResolutionError, match="published_at"):
        resolve_upgrade_sources(
            repository="example/repository",
            candidate_version="0.21.0",
            selection="latest-only",
            fetch_releases=lambda _repository: [release],
        )


def _release(tag: str, *, prerelease: bool = False) -> dict[str, object]:
    """Return one GitHub-shaped release fixture."""

    publication_times = {
        "v0.21.0": "2026-08-13T00:00:00Z",
        "v0.20.1": "2026-08-12T00:27:36Z",
        "v0.20.0": "2026-08-11T23:24:27Z",
        "v0.19.2": "2026-08-03T21:54:57Z",
        "v0.19.1": "2026-07-31T23:28:25Z",
        "v0.12.2": "2026-07-18T02:41:03Z",
    }
    return {
        "draft": False,
        "published_at": publication_times[tag],
        "prerelease": prerelease,
        "tag_name": tag,
    }
