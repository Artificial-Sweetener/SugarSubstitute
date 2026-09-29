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

"""Exercise missing-node recovery through live assessment and fresh editor behavior."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast

from sugarsubstitute_shared.localization import ApplicationText
from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    WorkflowNodepackCatalog,
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackResolutionService,
    WorkflowNodepackSourceKind,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessmentService,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
    WorkflowNodepackRecoveryPlanService,
)
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    NodeBehaviorService,
)
from substitute.application.node_behavior.runtime_state import CubeStateProtocol
from substitute.application.ports import (
    NodeDefinitionGateway,
    NodeDefinitionHydrationResult,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)
from substitute.domain.onboarding import ComfyTargetMode
from substitute.infrastructure.comfy.workflow_nodepack_installer import (
    WorkflowNodepackInstaller,
    WorkflowNodepackInstallItemResult,
    WorkflowNodepackInstallResult,
    WorkflowNodepackInstallStatus,
    WorkflowNodepackInstallProgress,
    WorkflowNodepackInstallStage,
)
from substitute.presentation.shell.direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
)
from tests.support.execution import ImmediateTaskSubmitter
from tests.support.node_behavior import cube_state

_NODE_CLASS = "ApplyKrea2NegPiP"


class _ComfyDefinitions:
    """Expose newly installed definitions only after the simulated Comfy restart."""

    def __init__(self) -> None:
        """Begin with the custom class absent from the running server."""

        self.installed = False
        self.restarted = False

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return current server metadata in Comfy's object-info shape."""

        if node_class != _NODE_CLASS or not (self.installed and self.restarted):
            return {}
        return {
            node_class: {
                "input": {"required": {"strength": ["FLOAT", {"default": 1.0}]}},
                "output": [],
            }
        }

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Use the same current metadata for required lookup."""

        return self.get_node_definition(node_class)

    def ensure_node_definitions(
        self, node_classes: Iterable[str]
    ) -> NodeDefinitionHydrationResult:
        """Classify requested classes against the running server generation."""

        requested = tuple(sorted(set(node_classes)))
        available = tuple(node for node in requested if self.get_node_definition(node))
        return NodeDefinitionHydrationResult(
            requested=requested,
            available=available,
            unavailable=tuple(node for node in requested if node not in available),
        )


class _Catalog:
    """Resolve the test node through an authoritative catalog boundary."""

    def infer_nodepack(self, class_type: str) -> ResolvedWorkflowNodepack | None:
        """Return the one trusted package that owns NegPiP."""

        if class_type != _NODE_CLASS:
            return None
        return ResolvedWorkflowNodepack(
            identifier="comfyui-krea2-negpip",
            display_name="Krea2 NegPiP",
            source_kind=WorkflowNodepackSourceKind.REGISTRY,
            repository_url=None,
            version="1.0.0",
        )


class _Installer:
    """Model package acquisition without mutating a shared Comfy workspace."""

    def __init__(self, server: _ComfyDefinitions) -> None:
        """Retain the external server boundary whose next restart activates code."""

        self.server = server
        self.calls: list[tuple[WorkflowNodepackInstallCandidate, ...]] = []

    def install(
        self,
        candidates: tuple[WorkflowNodepackInstallCandidate, ...],
        *,
        workspace: Path,
        python_executable: Path,
        on_progress: Callable[[WorkflowNodepackInstallProgress], None] | None = None,
    ) -> WorkflowNodepackInstallResult:
        """Install the approved package but leave the running server unchanged."""

        assert workspace == python_executable.parent
        self.calls.append(candidates)
        if on_progress is not None:
            on_progress(
                WorkflowNodepackInstallProgress(
                    WorkflowNodepackInstallStage.SOURCE,
                    "Krea2 NegPiP",
                    1,
                    1,
                )
            )
        self.server.installed = True
        return WorkflowNodepackInstallResult(
            items=(
                WorkflowNodepackInstallItemResult(
                    package_id="comfyui-krea2-negpip",
                    version="1.0.0",
                    source_kind=WorkflowNodepackSourceKind.REGISTRY,
                    status=WorkflowNodepackInstallStatus.INSTALLED,
                ),
            )
        )


class _Handoff:
    """Record the shell's splash and fresh-GUI transition."""

    def __init__(self, fresh_editor: Callable[[], None]) -> None:
        """Retain the post-restart editor assertion."""

        self._fresh_editor = fresh_editor
        self.events: list[str] = []

    def begin(self) -> bool:
        """Record the visible editor being covered before installation."""

        self.events.append("splash")
        return True

    def report(self, _message: ApplicationText) -> None:
        """Record Comfy restart progress under the splash."""

        self.events.append("comfy_restart")

    def reload(self) -> bool:
        """Build a fresh editor and verify its node is no longer degraded."""

        self._fresh_editor()
        self.events.append("gui_reload")
        return True

    def cancel(self) -> None:
        """Record an unexpected fallback to the old editor."""

        self.events.append("cancel")


def test_installed_negpip_becomes_normal_only_after_comfy_and_gui_restart(
    tmp_path: Path,
) -> None:
    """Reopen the same saved node with live controls after approved recovery."""

    server = _ComfyDefinitions()
    workflow: dict[str, object] = {
        "nodes": [{"id": 1, "type": _NODE_CLASS, "title": "NegPiP"}],
        "links": [],
    }
    cube = cube_state(
        nodes={"negpip": {"class_type": _NODE_CLASS, "inputs": {"strength": 1.0}}}
    )

    def editor_snapshot() -> EditorBehaviorSnapshot:
        """Build real node behavior against the current Comfy generation."""

        return NodeBehaviorService(
            node_definition_gateway=cast(NodeDefinitionGateway, server)
        ).build_snapshot(
            cube_states={"Krea": cast(CubeStateProtocol, cube)},
            stack_order=["Krea"],
        )

    before = editor_snapshot()
    assert "negpip" in before.degraded_nodes_by_alias["Krea"]
    installer = _Installer(server)
    handoff = _Handoff(fresh_editor=lambda: _assert_recovered_editor(editor_snapshot()))
    failures: list[BaseException] = []
    reviews: list[WorkflowNodepackRecoveryPlan] = []

    def present_review(
        plan: WorkflowNodepackRecoveryPlan,
        approve: Callable[[tuple[WorkflowNodepackInstallCandidate, ...]], None],
        _cancel: Callable[[], None],
    ) -> None:
        """Approve only the resolved package after inspecting its missing class."""

        reviews.append(plan)
        approve(plan.resolution.candidates)

    controller = DirectWorkflowNodepackRecoveryController(
        plan_service=WorkflowNodepackRecoveryPlanService(
            assessment=WorkflowNodeDefinitionAssessmentService(
                cast(NodeDefinitionGateway, server)
            ),
            resolution=WorkflowNodepackResolutionService(
                cast(WorkflowNodepackCatalog, _Catalog())
            ),
        ),
        installer=cast(WorkflowNodepackInstaller, installer),
        workspace=tmp_path,
        python_executable=tmp_path / "python.exe",
        present_review=present_review,
        present_failure=lambda _id, _stage, error: failures.append(error),
        can_restart=lambda: True,
        handoff_provider=lambda: handoff,
        request_restart=lambda: _restart(server),
        route_factory=lambda **_kwargs: WorkflowNodepackRecoveryRoute(
            submitter=ImmediateTaskSubmitter(),
            close=lambda: None,
            publish=lambda callback, _reason: callback(),
        ),
    )

    controller.recover(workflow=workflow, target_workflow_id="wf-krea")

    assert len(reviews) == 1
    assert reviews[0].assessment.missing_class_types == (_NODE_CLASS,)
    assert len(installer.calls) == 1
    assert handoff.events == ["splash", "comfy_restart", "comfy_restart"]
    assert "negpip" in before.degraded_nodes_by_alias["Krea"]

    controller.observe_connection(
        ComfyConnectionStateChange(
            previous=ComfyConnectionState(
                ComfyConnectionPhase.RESTARTING, ComfyTargetMode.MANAGED_LOCAL, True
            ),
            current=ComfyConnectionState(
                ComfyConnectionPhase.READY, ComfyTargetMode.MANAGED_LOCAL, True
            ),
        )
    )

    assert handoff.events == [
        "splash",
        "comfy_restart",
        "comfy_restart",
        "comfy_restart",
        "gui_reload",
    ]
    assert failures == []


def _restart(server: _ComfyDefinitions) -> bool:
    """Activate installed code in the simulated new Comfy generation."""

    assert server.installed
    server.restarted = True
    return True


def _assert_recovered_editor(snapshot: EditorBehaviorSnapshot) -> None:
    """Require the production editor snapshot to expose normal live controls."""

    assert "negpip" not in snapshot.degraded_nodes_by_alias.get("Krea", {})
    assert "strength" in snapshot.field_specs_by_alias["Krea"]["negpip"]
