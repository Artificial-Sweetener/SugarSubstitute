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

"""Verify the committed qualification Comfy compatibility matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci.comfy_support_matrix import (
    COMFY_RELEASE_CONTRACTS,
    COMFY_SUPPORT_MATRIX,
    COMFY_UPDATE_MATRIX,
    matrix_entry,
)


def test_comfy_release_contracts_pin_exact_upstream_commits() -> None:
    """Make source-cache identity independent of movable upstream tag refs."""

    assert {
        entry.comfyui_tag: entry.commit_sha for entry in COMFY_RELEASE_CONTRACTS
    } == {
        "v0.15.0": "b874bd2b8c324d58cfc37bff0754dd16815a8f3c",
        "v0.17.0": "63d1bbdb407c69370d407ce5ced6ca3f917528a8",
        "v0.18.0": "dc719cde9c448c65242ae2d4ba400ba18c36846f",
        "v0.19.0": "acd718598eca0b944a1a7a82072a9dec40d3d4f7",
        "v0.20.0": "75143eeb06b14bc93db71de207945f6f888be4e0",
        "v0.24.0": "f49bdb655707b97952dcef40e12e5af1f08d2007",
        "v0.25.0": "135abed8da169e33ab0b86550e05e3ae55d6df8c",
        "v0.28.2": "306af3a8771a8232d26bd20acbfc6b07f862ad2b",
    }


def test_comfy_support_matrix_starts_at_explicit_floor_and_ends_at_current() -> None:
    """Keep the declared proof range anchored at floor and reviewed current tag."""

    assert COMFY_SUPPORT_MATRIX[0].comfyui_tag == "v0.15.0"
    assert COMFY_SUPPORT_MATRIX[-1].comfyui_tag == "v0.28.2"


def test_comfy_support_matrix_covers_manager_contract_transitions() -> None:
    """Represent every reviewed 4.1 and 4.2 pin/capability transition."""

    assert [
        (entry.manager_version, entry.supports_pygit2) for entry in COMFY_SUPPORT_MATRIX
    ] == [
        ("4.1b1", False),
        ("4.1b2", False),
        ("4.1b6", False),
        ("4.1", False),
        ("4.2.1", True),
        ("4.2.2", True),
    ]


def test_unknown_matrix_tag_is_rejected() -> None:
    """Prevent unreviewed tags from silently using guessed expectations."""

    with pytest.raises(ValueError, match="Unknown ComfyUI matrix tag"):
        matrix_entry("v0.14.0")


def test_update_matrix_covers_incremental_and_direct_manager_transitions() -> None:
    """Keep real update proof anchored at every reviewed Manager pin boundary."""

    assert [(entry.source_tag, entry.target_tag) for entry in COMFY_UPDATE_MATRIX] == [
        ("v0.15.0", "v0.19.0"),
        ("v0.19.0", "v0.20.0"),
        ("v0.20.0", "v0.24.0"),
        ("v0.24.0", "v0.25.0"),
        ("v0.25.0", "v0.28.2"),
        ("v0.15.0", "v0.24.0"),
    ]
    assert matrix_entry("v0.24.0").manager_version == "4.2.1"
    assert matrix_entry("v0.25.0").manager_version == "4.2.2"


def test_canary_promotion_preserves_its_completed_compatibility_proof() -> None:
    """A Main promotion must not cancel or duplicate its Canary push matrix."""

    workflow_text = Path(".github/workflows/comfy-compatibility.yml").read_text(
        encoding="utf-8"
    )
    assert (
        "group: comfy-compatibility-${{ github.workflow }}-${{ github.event_name }}-"
        "${{ github.event.pull_request.head.sha || github.sha }}" in workflow_text
    )
    promotion_guard = (
        "    if: github.event_name != 'pull_request' || github.head_ref != 'canary' || "
        "github.base_ref != 'main'"
    )
    assert workflow_text.count(promotion_guard) == 2
    assert "./.github/workflows/comfy-runtime-compatibility.yml" in workflow_text
    assert "./.github/workflows/comfy-update-compatibility.yml" in workflow_text
