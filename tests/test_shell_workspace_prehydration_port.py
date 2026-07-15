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

"""Cover the narrow shell adapter used by workspace prehydration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.domain.workflow import ImageMeta, WorkflowState
from substitute.domain.workspace_snapshot import (
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    ImageMetaSnapshot,
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.presentation.shell.shell_workspace_prehydration_port import (
    ShellWorkspacePrehydrationPort,
)


def test_shell_workspace_prehydration_port_delegates_to_restore_owners() -> None:
    """Prehydration should target composed owners instead of the MainWindow surface."""

    calls: list[tuple[str, object]] = []
    workspace = _workspace()
    workflow = workspace.workflows[0]
    layout = ShellLayoutSnapshot(main_splitter_sizes=(1, 2))
    input_reference = InputImageReference(
        image_id="input",
        path=Path("input.png"),
        sequence=0,
    )
    mask_reference = InputMaskReference(
        mask_id="mask",
        image_id="input",
        path=Path("mask.png"),
        association_key=("Cube", "mask"),
    )
    output_reference = OutputImageReference(
        image_id="output",
        path=Path("output.png"),
        sequence=0,
        metadata=ImageMetaSnapshot(
            workflow_name="Workflow",
            cube_name="Cube",
            image_number=1,
            suffix="",
            path=Path("output.png"),
        ),
    )
    output_meta = ImageMeta(
        workflow_name="Workflow",
        cube_name="Cube",
        image_number=1,
        suffix="",
        path="output.png",
    )
    input_payload = object()
    output_payload = object()

    def load_input(path: Path) -> object:
        """Record input image loading and return the fake payload."""

        calls.append(("load_input", path))
        return input_payload

    def restore_input(reference: InputImageReference, image: object) -> None:
        """Record input image restore."""

        calls.append(("restore_input", (reference, image)))

    def restore_mask(reference: InputMaskReference) -> bool:
        """Record input mask restore."""

        calls.append(("restore_mask", reference))
        return True

    def load_output(path: Path) -> object:
        """Record output image loading and return the fake payload."""

        calls.append(("load_output", path))
        return output_payload

    def restore_output(
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: ImageMeta,
    ) -> None:
        """Record output image restore."""

        calls.append(("restore_output", (workflow_id, reference, image, image_meta)))

    shell = SimpleNamespace(
        shell_prehydrated_restore_controller=SimpleNamespace(
            begin_prehydrated_restore=lambda snapshot: calls.append(
                ("begin", snapshot)
            ),
            remember_prehydrated_shell_layout=lambda snapshot: calls.append(
                ("layout", snapshot)
            ),
            finish_prehydrated_restore=lambda snapshot: calls.append(
                ("finish", snapshot)
            ),
        ),
        restored_workflow_materializer=SimpleNamespace(
            reset_restored_workspace=lambda: calls.append(("reset", "")),
            add_prehydrated_workflow=lambda snapshot, *, activate: calls.append(
                ("workflow", (snapshot, activate))
            ),
        ),
        workspace_restore_image_adapter=SimpleNamespace(
            load_restored_input_image=load_input,
            restore_input_image=restore_input,
            restore_input_mask=restore_mask,
            load_restored_output_image=load_output,
            restore_output_image=restore_output,
        ),
    )

    port = ShellWorkspacePrehydrationPort(shell)

    port.begin_prehydrated_restore(workspace)
    port.reset_restored_workspace()
    port.add_prehydrated_workflow(workflow, activate=True)
    assert port.load_restored_input_image(input_reference.path) is input_payload
    port.restore_input_image(input_reference, input_payload)
    assert port.restore_input_mask(mask_reference) is True
    assert port.load_restored_output_image(output_reference.path) is output_payload
    port.restore_output_image("wf-a", output_reference, output_payload, output_meta)
    port.remember_prehydrated_shell_layout(layout)
    port.finish_prehydrated_restore(workspace)

    assert calls == [
        ("begin", workspace),
        ("reset", ""),
        ("workflow", (workflow, True)),
        ("load_input", Path("input.png")),
        ("restore_input", (input_reference, input_payload)),
        ("restore_mask", mask_reference),
        ("load_output", Path("output.png")),
        ("restore_output", ("wf-a", output_reference, output_payload, output_meta)),
        ("layout", layout),
        ("finish", workspace),
    ]


def _workspace() -> WorkspaceSnapshot:
    """Build one workflow snapshot for port tests."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=WorkflowState(),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
    )
