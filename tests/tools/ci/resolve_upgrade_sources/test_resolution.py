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
from sugarsubstitute_shared.update_compatibility import UpdateCompatibilityContract


def test_upgrade_sources_follow_declared_boundaries_not_release_count() -> None:
    """Release qualification should remain finite as ordinary versions accumulate."""

    releases = [
        _release("v0.23.0", prerelease=True),
        _release("v0.22.0"),
        _release("v0.21.2"),
        _release("v0.21.1"),
        _release("v0.20.1"),
        _release("v0.12.2"),
    ]

    matrix = resolve_upgrade_sources(
        repository="example/repository",
        candidate_version="0.23.0",
        fetch_releases=lambda _repository: releases,
        compatibility=_compatibility(),
    )

    assert matrix == [
        {
            "published_at": "2026-09-01T00:00:00Z",
            "tag": "v0.22.0",
            "version": "0.22.0",
            "boundary": "previous-stable+latest-pre-bootstrap",
        },
        {
            "published_at": "2026-07-18T02:41:03Z",
            "tag": "v0.12.2",
            "version": "0.12.2",
            "boundary": "legacy-pid-only+legacy-state",
        },
    ]


def test_upgrade_sources_need_only_previous_release_and_declared_boundaries() -> None:
    """Do not impose an arbitrary minimum count of historical releases."""

    matrix = resolve_upgrade_sources(
        repository="example/repository",
        candidate_version="0.23.0",
        fetch_releases=lambda _repository: [
            _release("v0.22.0"),
            _release("v0.12.2"),
        ],
        compatibility=_compatibility(),
    )

    assert [item["tag"] for item in matrix] == ["v0.22.0", "v0.12.2"]


def test_upgrade_sources_fail_when_declared_boundary_is_missing() -> None:
    """Complete qualification must never silently omit a contract boundary."""

    with pytest.raises(UpgradeSourceResolutionError, match="legacy-pid-only"):
        resolve_upgrade_sources(
            repository="example/repository",
            candidate_version="0.23.0",
            fetch_releases=lambda _repository: [
                _release("v0.22.0"),
            ],
            compatibility=_compatibility(),
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
            "boundary": "previous-stable",
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
        "v0.23.0": "2026-09-18T00:00:00Z",
        "v0.22.0": "2026-09-01T00:00:00Z",
        "v0.21.2": "2026-08-22T00:00:00Z",
        "v0.21.1": "2026-08-20T00:00:00Z",
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


def _compatibility() -> UpdateCompatibilityContract:
    """Return a finite protocol/data boundary contract for matrix tests."""

    return UpdateCompatibilityContract.from_json(
        {
            "schema_version": 1,
            "delegation_protocol": 1,
            "update_protocol": 1,
            "minimum_direct_launcher_version": "0.23.0",
            "supported_manifest_schema_versions": [1, 2],
            "historical_boundaries": [
                {
                    "id": "legacy-pid-only",
                    "representative_version": "0.12.2",
                    "route": "legacy_baseline_bridge",
                    "platforms": ["windows_x64"],
                },
                {
                    "id": "latest-pre-bootstrap",
                    "representative_version": "0.22.0",
                    "route": "legacy_baseline_bridge",
                    "platforms": ["windows_x64"],
                },
            ],
            "data_compatibility": {
                "schema_epoch": 1,
                "migrations": [
                    {
                        "id": "adopt-epoch-1",
                        "from_epoch": 0,
                        "to_epoch": 1,
                    }
                ],
                "migration_boundaries": [
                    {
                        "id": "legacy-state",
                        "representative_version": "0.12.2",
                    }
                ],
            },
        }
    )
