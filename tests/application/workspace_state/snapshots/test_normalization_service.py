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

"""Tests for workspace snapshot normalization repair policy."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workspace_state import SnapshotNormalizationService
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    CanvasLayoutSnapshot,
    EditorViewportSnapshot,
    FloatingCanvasWindowSnapshot,
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


def test_snapshot_normalization_repairs_workflow_order_and_active_route(
    tmp_path: Path,
) -> None:
    """Normalizer should drop duplicate workflows and repair tab references."""

    image_path = tmp_path / "output.png"
    image_path.write_bytes(b"image")
    output_id = UUID("33333333-3333-3333-3333-333333333333")
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            _workflow("wf-1", output_id=output_id, output_path=image_path),
            _workflow("wf-1", output_id=output_id, output_path=image_path),
            _workflow("", output_id=output_id, output_path=image_path),
        ),
        tab_order=("missing", "wf-1", "wf-1"),
        active_route="missing",
    )

    result = SnapshotNormalizationService().normalize(snapshot)

    assert [workflow.workflow_id for workflow in result.snapshot.workflows] == ["wf-1"]
    assert result.snapshot.tab_order == ("wf-1",)
    assert result.snapshot.active_route == "wf-1"
    assert "Dropped duplicate workflow id wf-1." in result.warnings
    assert "Dropped workflow with missing id." in result.warnings
    assert "Removed stale workflow id missing from tab order." in result.warnings


def test_snapshot_normalization_drops_missing_images_and_stale_focus(
    tmp_path: Path,
) -> None:
    """Normalizer should clear output focus when referenced images are missing."""

    existing_input = tmp_path / "input.png"
    existing_input.write_bytes(b"image")
    missing_output = tmp_path / "missing-output.png"
    output_id = UUID("33333333-3333-3333-3333-333333333333")
    workflow = _workflow(
        "wf-1",
        output_id=output_id,
        output_path=missing_output,
        input_path=existing_input,
    )
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(workflow,),
        tab_order=("wf-1",),
        active_route="wf-1",
    )

    result = SnapshotNormalizationService().normalize(snapshot)
    normalized = result.snapshot.workflows[0]

    assert normalized.output_images == ()
    assert normalized.workflow.output_image_uuids == []
    assert normalized.workflow.active_output_uuid is None
    assert f"Dropped missing output image {output_id}." in result.warnings
    assert "Cleared stale active output UUID." in result.warnings


def test_snapshot_normalization_keeps_settings_route(tmp_path: Path) -> None:
    """Settings remains a known built-in active route."""

    output_path = tmp_path / "output.png"
    output_path.write_bytes(b"image")
    output_id = UUID("33333333-3333-3333-3333-333333333333")
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(_workflow("wf-1", output_id=output_id, output_path=output_path),),
        tab_order=("wf-1",),
        active_route="settings",
    )

    result = SnapshotNormalizationService().normalize(snapshot)

    assert result.snapshot.active_route == "settings"


def test_snapshot_normalization_repairs_editor_viewport() -> None:
    """Normalizer should clamp viewport scroll and repair invalid anchors."""

    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-1",
                tab_label="Workflow",
                workflow=WorkflowState(
                    cubes={
                        "Sampler": CubeState(
                            cube_id="ksampler",
                            version="1",
                            alias="Sampler",
                            original_cube={},
                            buffer={},
                        )
                    },
                    stack_order=["Sampler"],
                ),
                active_cube_alias="Sampler",
                editor_viewport=EditorViewportSnapshot(
                    scroll_value=250,
                    scroll_maximum=100,
                    anchor_cube_alias="Missing",
                ),
            ),
        ),
        tab_order=("wf-1",),
        active_route="wf-1",
    )

    result = SnapshotNormalizationService().normalize(snapshot)

    assert result.snapshot.workflows[0].editor_viewport == EditorViewportSnapshot(
        scroll_value=100,
        scroll_maximum=100,
        anchor_cube_alias="Sampler",
    )
    assert "Repaired editor viewport anchor for workflow wf-1." in result.warnings


def test_snapshot_normalization_clears_editor_viewport_anchor_for_empty_stack() -> None:
    """Viewport anchor should clear when no normalized cube remains."""

    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-1",
                tab_label="Workflow",
                workflow=WorkflowState(cubes={}, stack_order=[]),
                active_cube_alias=None,
                editor_viewport=EditorViewportSnapshot(
                    scroll_value=-20,
                    scroll_maximum=-1,
                    anchor_cube_alias="Missing",
                ),
            ),
        ),
        tab_order=("wf-1",),
        active_route="wf-1",
    )

    result = SnapshotNormalizationService().normalize(snapshot)

    assert result.snapshot.workflows[0].editor_viewport == EditorViewportSnapshot(
        scroll_value=0,
        scroll_maximum=0,
        anchor_cube_alias=None,
    )


def test_snapshot_normalization_preserves_shell_canvas_layout() -> None:
    """Normalizer should pass durable shell layout through unchanged."""

    canvas_layout = CanvasLayoutSnapshot(
        floating_windows=(FloatingCanvasWindowSnapshot(label="Output"),)
    )
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(),
        tab_order=(),
        active_route="",
        shell_layout=ShellLayoutSnapshot(canvas_layout=canvas_layout),
    )

    result = SnapshotNormalizationService().normalize(snapshot)

    assert result.snapshot.shell_layout is not None
    assert result.snapshot.shell_layout.canvas_layout is canvas_layout


def test_snapshot_normalization_preserves_direct_workflow_without_cube_repairs() -> (
    None
):
    """Direct documents should retain authored state without cube-only warnings."""

    direct_workflow = DirectWorkflowState(
        source_path=Path("workflows/direct.json"),
        source_workflow={"nodes": {"1": {"class_type": "KSampler"}}},
        buffer={
            "nodes": {
                "1": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 7},
                    "mode": 4,
                }
            }
        },
        ui={"expanded": {"1": True}},
        dirty=True,
    )
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="direct",
                tab_label="Direct",
                workflow=WorkflowState(direct_workflow=direct_workflow),
                editor_viewport=EditorViewportSnapshot(
                    scroll_value=45,
                    scroll_maximum=100,
                    anchor_cube_alias=None,
                ),
            ),
        ),
        tab_order=("direct",),
        active_route="direct",
        active_workflow_id="direct",
    )

    result = SnapshotNormalizationService().normalize(snapshot)

    normalized = result.snapshot.workflows[0]
    assert normalized.workflow.direct_workflow is direct_workflow
    assert normalized.active_cube_alias is None
    assert normalized.editor_viewport == EditorViewportSnapshot(
        scroll_value=45,
        scroll_maximum=100,
        anchor_cube_alias=None,
    )
    assert not any("cube" in warning.lower() for warning in result.warnings)


def _workflow(
    workflow_id: str,
    *,
    output_id: UUID,
    output_path: Path,
    input_path: Path | None = None,
) -> WorkflowSnapshot:
    """Build one workflow snapshot for normalization tests."""

    input_image_id = "input-1"
    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label="Workflow",
        workflow=WorkflowState(
            cubes={
                "Sampler": CubeState(
                    cube_id="ksampler",
                    version="1",
                    alias="Sampler",
                    original_cube={},
                    buffer={},
                )
            },
            stack_order=["Sampler", "Missing"],
            output_image_uuids=[output_id],
            active_output_uuid=output_id,
        ),
        active_cube_alias="Missing",
        input_images=(
            InputImageReference(
                image_id=input_image_id,
                path=input_path,
                sequence=1,
            ),
        )
        if input_path is not None
        else (),
        input_masks=(
            InputMaskReference(
                mask_id="mask-1",
                image_id=input_image_id,
                path=input_path,
                association_key=("Sampler", "mask"),
            ),
        )
        if input_path is not None
        else (),
        output_images=(
            OutputImageReference(
                image_id=str(output_id),
                path=output_path,
                metadata=ImageMetaSnapshot(
                    workflow_name="Workflow",
                    cube_name="Save",
                    image_number=1,
                    suffix="",
                    path=output_path,
                ),
                sequence=1,
            ),
        ),
    )
