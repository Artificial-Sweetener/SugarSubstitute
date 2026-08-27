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

"""Qualify persisted direct-workflow restoration through the production shell."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

from substitute.application.workspace_state import WorkspaceMaterializationService
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)
from substitute.presentation.shell.restored_workflow_materializer import (
    RestoredWorkflowMaterializer,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)
from tests.application.workspace_state.restoration.fixture_harness import (
    HarnessNodeDefinitionGateway,
    HeadlessWorkspaceRestoreHarness,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.rendering import (
    wait_for_rendered_node_names,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)


def test_real_shell_materializes_persisted_direct_workflow_without_cube_stack(
    tmp_path: Path,
) -> None:
    """The real shell should restore direct cards through the unified materializer."""

    restore_harness = HeadlessWorkspaceRestoreHarness(tmp_path / "restore")
    assert restore_harness.force_save() is True
    plan = restore_harness.build_restore_plan()
    assert plan.workspace is not None
    hydrated = restore_harness.hydrate(plan.workspace)
    shell_harness = DirectWorkflowShell(tmp_path)
    try:
        shell_harness.shell.node_definition_gateway.install_recorded_definitions(
            HarnessNodeDefinitionGateway.definitions
        )
        setattr(
            shell_harness.shell,
            "restored_workflow_materializer",
            RestoredWorkflowMaterializer(shell_harness.shell),
        )
        setattr(
            shell_harness.shell,
            "restore_projection_controller",
            RestoreProjectionController(shell_harness.shell),
        )
        setattr(
            shell_harness.shell,
            "workspace_controller",
            shell_harness.shell.workflow_workspace,
        )
        setattr(
            shell_harness.shell,
            "workspace_restore_image_adapter",
            SimpleNamespace(),
        )
        setattr(
            shell_harness.shell,
            "shell_layout_restore_controller",
            SimpleNamespace(apply_restored_shell_layout=lambda _snapshot: None),
        )
        WorkspaceMaterializationService().materialize(
            hydrated,
            ShellWorkspaceMaterializationPort(shell_harness.shell),
        )
        panel = shell_harness.shell.editor_panels["direct"]
        wait_for_rendered_node_names(
            shell_harness,
            frozenset({"10"}),
            workflow_id="direct",
        )

        restored = shell_harness.shell.workflow_session_service.get_workflow("direct")
        assert restored is not None
        assert restored.direct_workflow is not None
        assert restored.direct_workflow.buffer["nodes"]["10"]["mode"] == 4  # type: ignore[index]
        assert (
            shell_harness.shell.workflow_session_service.active_workflow_id == "direct"
        )
        assert "direct" in shell_harness.shell.editor_panels
        assert "direct" not in shell_harness.shell.cube_stacks
        rendered_cards = {
            (str(node_name), str(class_type))
            for widget in panel.findChildren(QWidget)
            if (node_name := widget.property("node_name"))
            and (class_type := widget.property("node_class_type"))
        }
        assert rendered_cards == {("10", "KSampler")}
    finally:
        shell_harness.close()
