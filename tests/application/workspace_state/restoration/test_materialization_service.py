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

"""Tests for shared workspace snapshot materialization orchestration."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workspace_state import WorkspaceMaterializationService
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


class _MaterializationPort:
    """Record materialization calls for service tests."""

    def __init__(self) -> None:
        """Initialize deterministic image payloads and call logs."""

        self.loaded_inputs: list[Path] = []
        self.loaded_outputs: list[Path] = []
        self.restored_inputs: list[tuple[str, object]] = []
        self.restored_masks: list[str] = []
        self.restored_outputs: list[tuple[str, str, object, str]] = []
        self.added_workflows: list[tuple[str, str, bool]] = []
        self.projected_workflows: list[str] = []
        self.settings_projected = False
        self.layout_applied = False
        self.reset_calls = 0
        self.missing_paths: set[Path] = set()
        self.mask_restore_available = True
        self.events: list[str] = []

    def reset_restored_workspace(self) -> None:
        """Record workspace reset."""

        self.reset_calls += 1

    def add_restored_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Record restored workflow creation."""

        self.added_workflows.append(
            (snapshot.workflow_id, snapshot.tab_label, activate)
        )

    def load_restored_input_image(self, path: Path) -> object | None:
        """Return deterministic input payloads."""

        self.loaded_inputs.append(path)
        return None if path in self.missing_paths else f"input:{path.name}"

    def restore_input_image(
        self,
        reference: InputImageReference,
        image: object,
    ) -> None:
        """Record input restore."""

        self.restored_inputs.append((reference.image_id, image))

    def restore_input_mask(self, reference: InputMaskReference) -> bool:
        """Record mask restore availability."""

        if not self.mask_restore_available:
            return False
        self.restored_masks.append(reference.mask_id)
        return True

    def load_restored_output_image(self, path: Path) -> object | None:
        """Return deterministic output payloads."""

        self.loaded_outputs.append(path)
        return None if path in self.missing_paths else f"output:{path.name}"

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: object,
    ) -> None:
        """Record output restore."""

        self.restored_outputs.append(
            (
                workflow_id,
                reference.image_id,
                image,
                getattr(image_meta, "source_key", ""),
            )
        )

    def project_restored_workflow(self, workflow_id: str) -> None:
        """Record workflow projection."""

        self.projected_workflows.append(workflow_id)
        self.events.append(f"workflow:{workflow_id}")

    def project_restored_settings(self) -> None:
        """Record settings projection."""

        self.settings_projected = True
        self.events.append("settings")

    def apply_restored_shell_layout(self, snapshot: object | None) -> None:
        """Record layout application."""

        del snapshot
        self.layout_applied = True
        self.events.append("layout")


def test_workspace_materialization_creates_tabs_restores_images_and_projects_active() -> (
    None
):
    """Materializer should use one shared path for workflow and canvas restore."""

    port = _MaterializationPort()
    snapshot = _workspace(active_route="wf-2")

    result = WorkspaceMaterializationService().materialize(snapshot, port)

    assert result.warnings == ()
    assert port.reset_calls == 1
    assert port.added_workflows == [
        ("wf-1", "One", False),
        ("wf-2", "Two", True),
    ]
    assert port.loaded_inputs == [Path("input.png"), Path("input.png")]
    assert port.restored_inputs == [
        ("input-wf-1", "input:input.png"),
        ("input-wf-2", "input:input.png"),
    ]
    assert port.restored_masks == ["mask-wf-1", "mask-wf-2"]
    assert port.loaded_outputs == [Path("output.png"), Path("output.png")]
    assert port.restored_outputs == [
        (
            "wf-1",
            str(UUID("33333333-3333-3333-3333-333333333333")),
            "output:output.png",
            "Save",
        ),
        (
            "wf-2",
            str(UUID("33333333-3333-3333-3333-333333333333")),
            "output:output.png",
            "Save",
        ),
    ]
    assert port.projected_workflows == ["wf-2"]
    assert port.layout_applied is True


def test_workspace_materialization_projects_settings_route_after_workflows() -> None:
    """Settings route should restore after workflow widgets are available."""

    port = _MaterializationPort()
    snapshot = _workspace(active_route="settings", active_workflow_id="wf-2")

    WorkspaceMaterializationService().materialize(snapshot, port)

    assert port.added_workflows == [
        ("wf-1", "One", False),
        ("wf-2", "Two", True),
    ]
    assert port.settings_projected is True
    assert port.projected_workflows == ["wf-2"]
    assert port.events[-2:] == ["layout", "settings"]


def test_workspace_materialization_can_append_without_resetting_workspace() -> None:
    """Job replay should be able to reuse the materializer without clearing tabs."""

    port = _MaterializationPort()

    WorkspaceMaterializationService().materialize_into_existing_workspace(
        _workspace(active_route="wf-2"),
        port,
    )

    assert port.reset_calls == 0
    assert port.added_workflows == [
        ("wf-1", "One", False),
        ("wf-2", "Two", True),
    ]
    assert port.restored_outputs == [
        (
            "wf-1",
            str(UUID("33333333-3333-3333-3333-333333333333")),
            "output:output.png",
            "Save",
        ),
        (
            "wf-2",
            str(UUID("33333333-3333-3333-3333-333333333333")),
            "output:output.png",
            "Save",
        ),
    ]
    assert port.projected_workflows == ["wf-2"]


def test_workspace_materialization_warns_and_skips_missing_images() -> None:
    """Missing image payloads should not fail the whole workspace restore."""

    port = _MaterializationPort()
    port.missing_paths = {Path("output.png")}
    port.mask_restore_available = False

    result = WorkspaceMaterializationService().materialize(_workspace(), port)

    assert port.restored_outputs == []
    assert any("Skipped output image" in warning for warning in result.warnings)
    assert any("Skipped input mask" in warning for warning in result.warnings)


def _workspace(
    active_route: str = "wf-1",
    active_workflow_id: str | None = None,
) -> WorkspaceSnapshot:
    """Build a deterministic workspace snapshot for materialization tests."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(_workflow("wf-1", "One"), _workflow("wf-2", "Two")),
        tab_order=("wf-1", "wf-2"),
        active_route=active_route,
        active_workflow_id=active_workflow_id
        if active_workflow_id is not None
        else active_route,
        shell_layout=None,
    )


def _workflow(workflow_id: str, label: str) -> WorkflowSnapshot:
    """Build one workflow snapshot with input, mask, and output references."""

    output_id = UUID("33333333-3333-3333-3333-333333333333")
    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label=label,
        workflow=WorkflowState(output_image_uuids=[output_id]),
        input_images=(
            InputImageReference(
                image_id=f"input-{workflow_id}",
                path=Path("input.png"),
                sequence=1,
            ),
        ),
        input_masks=(
            InputMaskReference(
                mask_id=f"mask-{workflow_id}",
                image_id=f"input-{workflow_id}",
                path=Path("mask.png"),
                association_key=("Cube", "mask"),
            ),
        ),
        output_images=(
            OutputImageReference(
                image_id=str(output_id),
                path=Path("output.png"),
                metadata=ImageMetaSnapshot(
                    workflow_name=label,
                    cube_name="Save",
                    image_number=1,
                    suffix="",
                    path=Path("output.png"),
                    source_key="Save",
                    source_label="Save",
                ),
                sequence=1,
            ),
        ),
    )
