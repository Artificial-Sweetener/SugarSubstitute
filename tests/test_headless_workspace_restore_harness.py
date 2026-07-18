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

"""Verify mixed cube/direct cold and warm restore through the real harness."""

from __future__ import annotations

from pathlib import Path

from substitute.application.workspace_state import RestoreProjectionCacheState
from tests.headless_workspace_restore_harness import HeadlessWorkspaceRestoreHarness


def test_mixed_workspace_survives_forced_save_and_cold_restore(tmp_path: Path) -> None:
    """Cold restore should preserve direct state and hydrate cubes normally."""

    harness = HeadlessWorkspaceRestoreHarness(tmp_path)

    assert harness.force_save() is True
    plan = harness.build_restore_plan()
    assert plan.workspace is not None
    assert plan.provisional_restore_projection is None
    assert plan.restore_projection_validation is not None
    assert (
        plan.restore_projection_validation.state is RestoreProjectionCacheState.MISSING
    )

    hydrated = harness.hydrate(plan.workspace)
    materialized = harness.materialize(hydrated)

    assert tuple(materialized.workflows) == ("cube", "direct")
    assert materialized.projected_workflow_id == "direct"
    assert materialized.workflows["cube"].workflow.cubes["Scene"].version == "1.0.0"
    direct_snapshot = materialized.workflows["direct"]
    direct = direct_snapshot.workflow.direct_workflow
    assert direct is not None
    assert direct.buffer["nodes"]["10"]["inputs"]["seed"] == 17  # type: ignore[index]
    assert direct.buffer["nodes"]["10"]["mode"] == 4  # type: ignore[index]
    assert direct.ui == {"expanded": {"10": False}}
    assert direct.dirty is True
    assert direct_snapshot.workflow.global_overrides == {"seed": {"value": 23}}
    assert direct_snapshot.workflow.canvas.active_canvas_route == "output:scene-2"
    assert direct_snapshot.active_cube_alias is None
    assert direct_snapshot.editor_viewport is not None
    assert direct_snapshot.editor_viewport.scroll_value == 73
    assert direct_snapshot.editor_viewport.anchor_cube_alias is None


def test_warm_restore_validates_both_document_kinds_against_backend(
    tmp_path: Path,
) -> None:
    """Warm restore should accept matching cube and direct-node identities."""

    harness = HeadlessWorkspaceRestoreHarness(tmp_path)
    assert harness.force_save() is True
    cold_plan = harness.build_restore_plan()
    assert cold_plan.workspace is not None
    hydrated = harness.hydrate(cold_plan.workspace)
    harness.capture_projection_cache(hydrated)

    warm_plan = harness.build_restore_plan()

    assert warm_plan.workspace is not None
    assert warm_plan.provisional_restore_projection is not None
    assert warm_plan.restore_projection_validation is not None
    assert (
        warm_plan.restore_projection_validation.state
        is RestoreProjectionCacheState.BACKEND_PENDING
    )
    backend_validation = harness.validate_after_backend(warm_plan)
    assert backend_validation.state is RestoreProjectionCacheState.VALID
    assert backend_validation.is_valid
    direct = warm_plan.workspace.workflows[1].workflow.direct_workflow
    assert direct is not None
    assert direct.buffer["nodes"]["10"]["mode"] == 4  # type: ignore[index]


def test_direct_edit_invalidates_and_clears_warm_projection_cache(
    tmp_path: Path,
) -> None:
    """A persisted direct graph edit should reject and clear the derived cache."""

    harness = HeadlessWorkspaceRestoreHarness(tmp_path)
    assert harness.force_save() is True
    cold_plan = harness.build_restore_plan()
    assert cold_plan.workspace is not None
    harness.capture_projection_cache(harness.hydrate(cold_plan.workspace))
    direct = harness.capture_port.workflows["direct"].direct_workflow
    assert direct is not None
    direct.buffer["nodes"]["10"]["inputs"]["seed"] = 99  # type: ignore[index]
    direct.dirty = True
    assert harness.force_save() is True

    changed_plan = harness.build_restore_plan()

    assert changed_plan.workspace is not None
    assert changed_plan.provisional_restore_projection is None
    assert changed_plan.restore_projection_validation is not None
    assert (
        changed_plan.restore_projection_validation.state
        is RestoreProjectionCacheState.WORKSPACE_MISMATCH
    )
    assert harness.cache_repository.load() is None
    restored_direct = changed_plan.workspace.workflows[1].workflow.direct_workflow
    assert restored_direct is not None
    assert restored_direct.buffer["nodes"]["10"]["inputs"]["seed"] == 99  # type: ignore[index]
