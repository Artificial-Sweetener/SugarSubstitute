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

"""Prove saved workflows are rechecked without a fresh file import."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from substitute.application.comfy_nodepacks.workflow_node_definition_assessment import (
    WorkflowNodeDefinitionAssessment,
)
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)
from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem
from substitute.domain.onboarding import ComfyTargetMode
from substitute.presentation.shell.direct_workflow_nodepack_recovery import (
    DirectWorkflowNodepackRecoveryController,
)
from substitute.presentation.shell.main_window import MainWindow
from substitute.presentation.shell.open_workflow_nodepack_reassessment import (
    OpenWorkflowNodepackReassessment,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _change(
    previous: ComfyConnectionPhase,
    current: ComfyConnectionPhase,
) -> ComfyConnectionStateChange:
    """Describe one monitor-confirmed Comfy state change."""

    return ComfyConnectionStateChange(
        previous=ComfyConnectionState(previous, ComfyTargetMode.MANAGED_LOCAL, True),
        current=ComfyConnectionState(current, ComfyTargetMode.MANAGED_LOCAL, True),
    )


def test_existing_workflow_reassesses_after_restore_and_reconnect() -> None:
    """Restore and reconnect must reproject a missing saved node and offer repair."""

    workflow: dict[str, object] = {"nodes": [{"id": 1, "type": "Missing"}]}
    state = SimpleNamespace(direct_workflow=SimpleNamespace(source_workflow=workflow))
    refreshes: list[tuple[str, ...]] = []
    panel = SimpleNamespace(
        refresh_projection_after_node_definition_update=lambda *, refreshed_node_classes: (
            refreshes.append(refreshed_node_classes)
        )
    )
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="workflow-a",
            workflows={"workflow-a": state},
        ),
        editor_panels={"workflow-a": panel},
    )
    requests: list[object] = []
    missing = WorkflowNodeInventoryItem("1", "Missing", "Missing", "Cube", None)

    def reassess_open_workflow(**kwargs: object) -> None:
        """Deliver a live missing-node assessment to the production coordinator."""

        requests.append(kwargs)
        assert kwargs["workflow"] is workflow
        assert kwargs["target_workflow_id"] == "workflow-a"
        refresh = kwargs["refresh_projection"]
        assert callable(refresh)
        refresh(WorkflowNodeDefinitionAssessment(available=(), missing=(missing,)))

    coordinator = OpenWorkflowNodepackReassessment(
        shell=cast(MainWindow, shell),
        recovery=cast(
            DirectWorkflowNodepackRecoveryController,
            SimpleNamespace(reassess_open_workflow=reassess_open_workflow),
        ),
    )

    coordinator.reassess_active()
    coordinator.observe_connection(
        _change(ComfyConnectionPhase.DISCONNECTED, ComfyConnectionPhase.READY)
    )
    coordinator.observe_connection(
        _change(ComfyConnectionPhase.READY, ComfyConnectionPhase.READY)
    )

    assert len(requests) == 2
    assert refreshes == [("Missing",), ("Missing",)]


def test_replaced_workflow_is_not_reprojected_from_stale_assessment() -> None:
    """A late result cannot overwrite the currently open document's node cards."""

    original: dict[str, object] = {"nodes": []}
    state = SimpleNamespace(direct_workflow=SimpleNamespace(source_workflow=original))
    refreshes: list[tuple[str, ...]] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="workflow-a",
            workflows={"workflow-a": state},
        ),
        editor_panels={
            "workflow-a": SimpleNamespace(
                refresh_projection_after_node_definition_update=lambda *, refreshed_node_classes: (
                    refreshes.append(refreshed_node_classes)
                )
            )
        },
    )
    pending: list[dict[str, object]] = []
    recovery = SimpleNamespace(
        reassess_open_workflow=lambda **kwargs: pending.append(kwargs)
    )
    coordinator = OpenWorkflowNodepackReassessment(
        shell=cast(MainWindow, shell),
        recovery=cast(DirectWorkflowNodepackRecoveryController, recovery),
    )
    coordinator.reassess_active()
    state.direct_workflow.source_workflow = {"nodes": []}
    refresh = pending[0]["refresh_projection"]
    assert callable(refresh)
    refresh(
        WorkflowNodeDefinitionAssessment(
            available=(),
            missing=(WorkflowNodeInventoryItem("1", "Missing", "Missing", None, None),),
        )
    )

    assert refreshes == []


def test_restored_workflow_reassessment_waits_for_owner_event_loop(
    qt_application_owner: QApplication,
) -> None:
    """Defer the restored workflow check until the owning Qt shell can paint."""

    _ = qt_application_owner
    shell = QObject()
    shell.workflow_session_service = SimpleNamespace(  # type: ignore[attr-defined]
        active_workflow_id="workflow-a",
        workflows={
            "workflow-a": SimpleNamespace(
                direct_workflow=SimpleNamespace(source_workflow={"nodes": []})
            )
        },
    )
    shell.editor_panels = {}  # type: ignore[attr-defined]
    requests: list[object] = []
    coordinator = OpenWorkflowNodepackReassessment(
        shell=cast(MainWindow, shell),
        recovery=cast(
            DirectWorkflowNodepackRecoveryController,
            SimpleNamespace(
                reassess_open_workflow=lambda **kwargs: requests.append(kwargs)
            ),
        ),
    )

    coordinator.schedule_after_restore()
    assert requests == []
    wait_for_qt_condition(lambda: len(requests) == 1)
