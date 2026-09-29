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

"""Qualify node availability changes against a mounted production editor."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    WorkflowNodepackCatalog,
    WorkflowNodepackResolutionService,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessmentService,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlanService,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
)
from substitute.presentation.shell.direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)
from substitute.presentation.shell.open_workflow_nodepack_reassessment import (
    OpenWorkflowNodepackReassessment,
)
from substitute.presentation.shell.main_window import MainWindow
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.workflows import (
    direct_section_view,
    load_direct_workflow,
)
from tests.qualification.comfy.bundled_workflows.direct_workflow_scenarios.support import (
    deterministic_sdxl_fixture,
)
from tests.support.execution import ImmediateTaskSubmitter

pytest_plugins = ("tests.support.qt.rendering_font",)


class _NoMatches:
    """Leave the render proof independent of external package catalogs."""

    def infer_nodepack(self, _class_type: str) -> None:
        """Report no trusted match for the deliberately removed fixture class."""

        return None


def test_open_sdxl_workflow_marks_only_removed_node_and_recovers(
    qt_application_owner: QApplication,
    tmp_path: Path,
    offscreen_rendering_font: None,
) -> None:
    """An open workflow must repaint one missing node without a fresh file load."""

    _ = qt_application_owner
    _ = offscreen_rendering_font
    harness = DirectWorkflowShell(tmp_path)
    try:
        failures: list[BaseException] = []
        fixture = deterministic_sdxl_fixture()
        load_direct_workflow(
            harness,
            fixture.path,
            node_definitions=fixture.node_definitions,
            expected_node_names=frozenset(
                prompt.node_name for prompt in fixture.expected_prompts
            )
            | {"11"},
        )
        gateway = harness.shell.node_definition_gateway
        panel = harness.shell.editor_panels[harness.direct_workflow_id]
        assert not panel.findChildren(QWidget, "DegradedNodeCard")
        remaining = {
            name: definition
            for name, definition in fixture.node_definitions.items()
            if name != "KSamplerAdvanced"
        }
        gateway.install_recorded_definitions(remaining)
        controller = DirectWorkflowNodepackRecoveryController(
            plan_service=WorkflowNodepackRecoveryPlanService(
                assessment=WorkflowNodeDefinitionAssessmentService(
                    cast(NodeDefinitionGateway, gateway)
                ),
                resolution=WorkflowNodepackResolutionService(
                    cast(WorkflowNodepackCatalog, _NoMatches())
                ),
            ),
            installer=WorkflowNodepackInstaller(),
            workspace=None,
            python_executable=None,
            present_review=lambda _plan, _approved, _cancelled: None,
            present_failure=lambda _workflow_id, _stage, error: failures.append(error),
            can_restart=lambda: False,
            handoff_provider=lambda: None,
            request_restart=lambda: False,
            route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
                submitter=ImmediateTaskSubmitter(),
                close=lambda: None,
                publish=lambda callback, _reason: callback(),
            ),
        )
        reassessment = OpenWorkflowNodepackReassessment(
            shell=cast(MainWindow, harness.shell),
            recovery=controller,
        )

        reassessment.reassess_active()
        harness.wait_until(
            lambda: (
                bool(panel.findChildren(QWidget, "DegradedNodeCard"))
                and not panel.is_projection_active()
            ),
            description="removed node appears as a degraded card",
            timeout_ms=30_000,
        )
        degraded = panel.findChildren(QWidget, "DegradedNodeCard")
        assert len(degraded) == 2
        assert direct_section_view(harness).issueSeverity() is None
        assert any(
            widget.property("node_class_type") == "CheckpointLoaderSimple"
            for widget in panel.findChildren(QWidget)
        )
        assert degraded[0].grab().save(str(tmp_path / "missing-node-card.png"))

        gateway.install_recorded_definitions(fixture.node_definitions)
        reassessment.reassess_active()
        harness.wait_until(
            lambda: (
                not panel.findChildren(QWidget, "DegradedNodeCard")
                and not panel.is_projection_active()
            ),
            description="restored node returns to a normal card",
            timeout_ms=30_000,
        )
        assert direct_section_view(harness).issueSeverity() is None
        assert failures == []
        controller.close()
    finally:
        harness.close()
