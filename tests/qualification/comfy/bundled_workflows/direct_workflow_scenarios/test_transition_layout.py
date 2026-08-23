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

"""Qualify direct-workflow transition and layout ownership in the real shell."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.editor.panel.content_gutter_controller import (
    DIRECT_WORKFLOW_LEFT_GUTTER,
)
from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPresentationMode,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.rendering import (
    capture_layout,
    layout_probe,
    write_layout_report,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)


def test_real_shell_cube_direct_animation_and_artifacts(tmp_path: Path) -> None:
    """Rendered endpoints must preserve editor width and transfer stack width to canvas."""

    artifact_root = tmp_path
    harness = DirectWorkflowShell(artifact_root)
    try:
        cube = capture_layout(harness, artifact_root / "cube.png", "cube")
        harness.activate_direct(animated=True)
        harness.wait_for_intermediate_transition()
        mid = capture_layout(harness, artifact_root / "mid.png", "mid")
        harness.wait_for_transition()
        direct = capture_layout(harness, artifact_root / "direct.png", "direct")

        harness.activate_cube(animated=True)
        harness.wait_for_transition()
        restored = capture_layout(harness, artifact_root / "restored.png", "restored")
        probes = [cube, mid, direct, restored]
        write_layout_report(artifact_root / "geometry.json", probes)

        assert cube.mode == CubeStackPresentationMode.EXPANDED.value
        assert (cube.editor_left_gutter, cube.editor_right_gutter) == (6, 14)
        assert mid.animating
        assert 0 < mid.container_width < CUBE_STACK_EXPANDED_WIDTH
        assert 6 <= mid.editor_left_gutter <= DIRECT_WORKFLOW_LEFT_GUTTER
        assert mid.editor_right_gutter == 14
        assert direct.mode == CubeStackPresentationMode.UNAVAILABLE.value
        assert direct.container_width == 0
        assert not direct.container_visible
        assert not direct.button_enabled
        assert (direct.editor_left_gutter, direct.editor_right_gutter) == (
            DIRECT_WORKFLOW_LEFT_GUTTER,
            14,
        )
        assert abs(direct.editor_width - cube.editor_width) <= 2
        assert (
            cube.editor_global_left - direct.editor_global_left
            == CUBE_STACK_EXPANDED_WIDTH
        )
        assert direct.canvas_width - cube.canvas_width == CUBE_STACK_EXPANDED_WIDTH
        assert restored.mode == CubeStackPresentationMode.EXPANDED.value
        assert (restored.editor_left_gutter, restored.editor_right_gutter) == (6, 14)
        assert abs(restored.editor_width - cube.editor_width) <= 2
        assert restored.splitter_sizes == cube.splitter_sizes
        assert restored.generation > direct.generation

        payload = json.loads((artifact_root / "geometry.json").read_text("utf-8"))
        assert [row["label"] for row in payload] == [
            "cube",
            "mid",
            "direct",
            "restored",
        ]
        assert all(
            (artifact_root / name).stat().st_size > 1000
            for name in ("cube.png", "mid.png", "direct.png", "restored.png")
        )
    finally:
        harness.close()


def test_real_shell_rapid_reversal_settings_reduced_motion_and_restore(
    tmp_path: Path,
) -> None:
    """Retargeting and non-animated paths must retain mode and chrome ownership."""

    harness = DirectWorkflowShell(tmp_path)
    app = harness.app
    previous_reduced_motion = app.property("substitute.reduce_motion")
    try:
        harness.activate_direct(animated=True)
        harness.wait_for_intermediate_transition()
        before_reverse = layout_probe(harness, "before-reverse")
        harness.activate_cube(animated=True)
        after_reverse = layout_probe(harness, "after-reverse")
        assert (
            before_reverse.container_width
            <= after_reverse.container_width
            < CUBE_STACK_EXPANDED_WIDTH
        )
        assert (
            6
            <= after_reverse.editor_left_gutter
            <= before_reverse.editor_left_gutter
            <= DIRECT_WORKFLOW_LEFT_GUTTER
        )
        harness.wait_for_transition()
        assert (
            layout_probe(harness, "reversed").mode
            == CubeStackPresentationMode.EXPANDED.value
        )

        harness.activate_direct(animated=True)
        harness.wait_for_transition()
        controller = harness.shell.cube_stack_presentation_controller
        controller.set_workflow_route_active(False)
        assert not harness.shell.cubeStackModeButton.isEnabled()
        controller.set_workflow_route_active(True)
        assert not harness.shell.cubeStackModeButton.isEnabled()

        app.setProperty("substitute.reduce_motion", True)
        harness.activate_cube(animated=True)
        assert not controller.is_animating
        controller.restore_preference(True)
        harness.activate_direct(animated=False)
        restored_direct = layout_probe(harness, "restored-direct")
        assert restored_direct.mode == CubeStackPresentationMode.UNAVAILABLE.value
        assert restored_direct.container_width == 0
        harness.activate_cube(animated=False)
        restored_compact = layout_probe(harness, "restored-compact")
        assert restored_compact.mode == CubeStackPresentationMode.COMPACT.value
        assert restored_compact.container_width == CUBE_STACK_COMPACT_WIDTH
        assert restored_compact.button_checked
    finally:
        app.setProperty("substitute.reduce_motion", previous_reduced_motion)
        harness.close()
