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

"""Tests for version-only loaded Cube Library update detection."""

from __future__ import annotations

from substitute.application.cube_library import (
    CubeLibraryUpdateDetectionService,
    CubeLibraryUpdateReason,
    group_loaded_cube_update_candidates_by_current_version,
)
from substitute.application.cube_library.update_detection import (
    LoadedCubeUpdateCandidate,
)
from substitute.domain.cube_library import (
    CubeCatalog,
    CubeCatalogEntry,
    CubeSourceMetadata,
)
from substitute.domain.workflow import CubeState, WorkflowState


def test_version_drift_produces_candidate() -> None:
    """Loaded cube versions that differ from catalog versions should be candidates."""

    workflow = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.0",
                alias="Demo",
                original_cube={},
                buffer={},
                display_name="Demo",
                ui={"content_hash": "old-hash"},
            )
        },
        stack_order=["Demo"],
    )

    candidates = CubeLibraryUpdateDetectionService().detect_updates(
        workflows={"workflow-1": workflow},
        workflow_names={"workflow-1": "Workflow One"},
        catalog=_catalog(version="2.0", content_hash="new-hash"),
    )

    assert len(candidates) == 1
    assert candidates[0].workflow_id == "workflow-1"
    assert candidates[0].workflow_name == "Workflow One"
    assert candidates[0].cube_alias == "Demo"
    assert candidates[0].current_version == "1.0"
    assert candidates[0].latest_version == "2.0"
    assert candidates[0].reason == CubeLibraryUpdateReason.VERSION_DRIFT


def test_matching_versions_with_different_hashes_do_not_produce_candidate() -> None:
    """Hash-only changes are same-version changes and should stay silent."""

    workflow = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.0",
                alias="Demo",
                original_cube={},
                buffer={},
                ui={"content_hash": "old-hash"},
            )
        }
    )

    candidates = CubeLibraryUpdateDetectionService().detect_updates(
        workflows={"workflow-1": workflow},
        workflow_names={},
        catalog=_catalog(version="1.0", content_hash="new-hash"),
    )

    assert candidates == ()


def test_missing_catalog_cube_does_not_produce_candidate() -> None:
    """Loaded cubes absent from the current catalog should not prompt for updates."""

    workflow = WorkflowState(
        cubes={
            "Other": CubeState(
                cube_id="owner/repo/other.cube",
                version="1.0",
                alias="Other",
                original_cube={},
                buffer={},
            )
        }
    )

    candidates = CubeLibraryUpdateDetectionService().detect_updates(
        workflows={"workflow-1": workflow},
        workflow_names={},
        catalog=_catalog(version="2.0"),
    )

    assert candidates == ()


def test_empty_catalog_versions_are_ignored_conservatively() -> None:
    """Empty latest versions should not produce update prompts."""

    workflow = WorkflowState(
        cubes={
            "Demo": CubeState(
                cube_id="owner/repo/demo.cube",
                version="1.0",
                alias="Demo",
                original_cube={},
                buffer={},
            )
        }
    )

    candidates = CubeLibraryUpdateDetectionService().detect_updates(
        workflows={"workflow-1": workflow},
        workflow_names={},
        catalog=_catalog(version=""),
    )

    assert candidates == ()


def test_candidates_group_by_current_cube_version() -> None:
    """Update-all matching decisions should group by cube id and current version."""

    first = _candidate(alias="Demo", current_version="1.0")
    second = _candidate(alias="Copy", current_version="1.0")
    third = _candidate(alias="Other", current_version="1.1")

    groups = group_loaded_cube_update_candidates_by_current_version(
        (first, second, third)
    )

    assert len(groups) == 2
    assert groups[0].cube_id == "owner/repo/demo.cube"
    assert groups[0].current_version == "1.0"
    assert groups[0].candidates == (first, second)
    assert groups[1].current_version == "1.1"
    assert groups[1].candidates == (third,)


def _catalog(
    *,
    version: str,
    content_hash: str = "hash",
) -> CubeCatalog:
    """Build a catalog containing one demo cube."""

    return CubeCatalog(
        schema_version=1,
        catalog_revision="catalog-rev",
        generated_at="2026-05-15T19:00:00+00:00",
        cubes=(
            CubeCatalogEntry(
                cube_id="owner/repo/demo.cube",
                version=version,
                display_name="Demo Cube",
                description="",
                source=CubeSourceMetadata(kind="local", path="demo.cube"),
                content_hash=content_hash,
            ),
        ),
    )


def _candidate(
    *,
    alias: str,
    current_version: str,
) -> LoadedCubeUpdateCandidate:
    """Build one grouped update candidate."""

    return LoadedCubeUpdateCandidate(
        workflow_id="workflow-1",
        workflow_name="Workflow One",
        cube_alias=alias,
        cube_id="owner/repo/demo.cube",
        current_version=current_version,
        latest_version="2.0",
        catalog_revision="catalog-rev",
        display_name="Demo Cube",
        reason=CubeLibraryUpdateReason.VERSION_DRIFT,
    )
