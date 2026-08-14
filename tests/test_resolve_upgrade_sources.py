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
        {"tag": "v0.20.1", "version": "0.20.1"},
        {"tag": "v0.20.0", "version": "0.20.0"},
        {"tag": "v0.19.2", "version": "0.19.2"},
        {"tag": "v0.12.2", "version": "0.12.2"},
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

    assert matrix == [{"tag": "v0.20.1", "version": "0.20.1"}]


def _release(tag: str, *, prerelease: bool = False) -> dict[str, object]:
    """Return one GitHub-shaped release fixture."""

    return {
        "draft": False,
        "prerelease": prerelease,
        "tag_name": tag,
    }
