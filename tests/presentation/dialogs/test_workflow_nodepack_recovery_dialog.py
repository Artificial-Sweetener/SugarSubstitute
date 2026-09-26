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

"""Tests for the non-blocking missing-nodepack review surface."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    UnresolvedWorkflowNode,
    UnresolvedWorkflowNodeReason,
    WorkflowNodepackInstallCandidate,
    WorkflowNodepackResolutionPlan,
    WorkflowNodepackSourceKind,
)
from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
)
from substitute.application.comfy_nodepacks.workflow_nodepack_recovery_plan import (
    WorkflowNodepackRecoveryPlan,
)
from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem
from substitute.presentation.dialogs.workflow_nodepack_recovery_dialog import (
    WorkflowNodepackRecoveryDialog,
    WorkflowNodepackRecoveryPresenter,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _plan() -> WorkflowNodepackRecoveryPlan:
    """Build a review containing Registry, Manager, and unresolved evidence."""

    registry_node = WorkflowNodeInventoryItem("1", "RegistryNode", "One", None, None)
    legacy_node = WorkflowNodeInventoryItem("2", "LegacyNode", "Two", None, None)
    unresolved_node = WorkflowNodeInventoryItem("3", "UnknownNode", "Three", None, None)
    return WorkflowNodepackRecoveryPlan(
        assessment=WorkflowNodeDefinitionAssessment(
            available=(),
            missing=(registry_node, legacy_node, unresolved_node),
        ),
        resolution=WorkflowNodepackResolutionPlan(
            candidates=(
                WorkflowNodepackInstallCandidate(
                    nodepack=ResolvedWorkflowNodepack(
                        identifier="registry-pack",
                        display_name="Registry Pack",
                        source_kind=WorkflowNodepackSourceKind.REGISTRY,
                        repository_url=None,
                        version="1.0.0",
                    ),
                    nodes=(registry_node,),
                    persisted_versions=(),
                ),
                WorkflowNodepackInstallCandidate(
                    nodepack=ResolvedWorkflowNodepack(
                        identifier="https://github.com/example/legacy",
                        display_name="Legacy Pack",
                        source_kind=WorkflowNodepackSourceKind.GIT_REPOSITORY,
                        repository_url="https://github.com/example/legacy",
                        version="1" * 40,
                    ),
                    nodes=(legacy_node,),
                    persisted_versions=(),
                ),
            ),
            unresolved=(
                UnresolvedWorkflowNode(
                    node=unresolved_node,
                    reason=UnresolvedWorkflowNodeReason.NOT_IN_CATALOG,
                ),
            ),
        ),
    )


def test_dialog_truthfully_lists_sources_classes_and_unresolved_nodes(
    qt_application_owner: QApplication,
) -> None:
    """The visual review should expose every fact behind the install decision."""

    _ = qt_application_owner
    parent = QWidget()
    parent.resize(1200, 800)
    parent.show()
    qt_application_owner.processEvents()
    dialog = WorkflowNodepackRecoveryDialog(_plan(), parent=parent)

    labels = {label.text() for label in dialog.findChildren(QLabel)}

    assert "Registry Pack" in labels
    assert "Legacy Pack" in labels
    assert "Provides: RegistryNode" in labels
    assert "Provides: LegacyNode" in labels
    assert "Source: Comfy Registry" in labels
    assert "Source: ComfyUI-Manager catalog" in labels
    assert "Version: 1.0.0" in labels
    assert f"Revision: {'1' * 40}" in labels
    assert "No trusted package match was found for: UnknownNode" in labels
    assert dialog.install_action.isEnabled()
    assert dialog.candidates == _plan().resolution.candidates


def test_presenter_opens_without_nested_exec_and_dispatches_cancellation(
    qt_application_owner: QApplication,
) -> None:
    """Review presentation must return immediately and keep cancellation usable."""

    _ = qt_application_owner
    parent = QWidget()
    parent.resize(1200, 800)
    parent.show()
    qt_application_owner.processEvents()
    dialogs: list[WorkflowNodepackRecoveryDialog] = []
    approved: list[object] = []
    cancelled: list[str] = []

    def factory(
        plan: WorkflowNodepackRecoveryPlan,
        *,
        parent: object | None,
    ) -> WorkflowNodepackRecoveryDialog:
        """Capture the concrete dialog created by the presenter."""

        dialog = WorkflowNodepackRecoveryDialog(plan, parent=parent)
        dialogs.append(dialog)
        return dialog

    presenter = WorkflowNodepackRecoveryPresenter(
        parent=parent,
        dialog_factory=factory,
    )

    presenter.present(_plan(), approved.append, lambda: cancelled.append("cancel"))
    qt_application_owner.processEvents()

    assert len(dialogs) == 1
    assert dialogs[0].isVisible()
    dialogs[0].reject()
    wait_for_qt_condition(lambda: cancelled == ["cancel"])
    assert approved == []
    assert cancelled == ["cancel"]
