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

"""Materialize restored workflow tabs and workflow-scoped widgets."""

from __future__ import annotations

from typing import Any
from typing import cast

from substitute.application.workflows import WorkflowState
from substitute.domain.workflow import WorkflowDocumentKind
from substitute.application.workspace_state import WorkspaceAppendService
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeTabIconResolver,
)
from substitute.presentation.shell.main_window_startup_trace import (
    workflow_snapshot_trace_fields,
)
from substitute.presentation.shell.workflow_ui_factory import workflow_ui_factory_for
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.shared.logging.logger import get_logger, log_info
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("presentation.shell.restored_workflow_materializer")


class RestoredWorkflowMaterializer:
    """Own restored workflow UI materialization for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose restored workflows should be materialized."""

        self._shell = shell

    def add_prehydrated_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Create workflow session and tab chrome without editor projection."""

        trace_mark(
            "main_window.add_prehydrated_workflow.start",
            activate=activate,
            **workflow_snapshot_trace_fields(snapshot),
        )
        self._shell.workflow_session_service.add_existing_workflow(
            snapshot.workflow_id,
            WorkflowState(),
            activate=activate,
        )
        self._shell.workflow_tabbar.addTab(snapshot.workflow_id, snapshot.tab_label)
        self._shell._pending_restored_workflow_snapshots[snapshot.workflow_id] = (
            snapshot
        )
        restored_snapshots = getattr(
            self._shell,
            "_restored_workflow_snapshots_by_id",
            None,
        )
        if not isinstance(restored_snapshots, dict):
            restored_snapshots = {}
            self._shell._restored_workflow_snapshots_by_id = restored_snapshots
        restored_snapshots[snapshot.workflow_id] = snapshot
        trace_mark(
            "main_window.add_prehydrated_workflow.end",
            workflow_id=snapshot.workflow_id,
        )

    def reset_restored_workspace(self) -> None:
        """Clear workflow UI and session state before snapshot materialization."""

        trace_mark(
            "main_window.reset_restored_workspace.start",
            cube_stack_count=len(getattr(self._shell, "cube_stacks", {})),
            editor_panel_count=len(getattr(self._shell, "editor_panels", {})),
        )
        log_info(
            _LOGGER,
            "mainwindow reset restored workspace started",
            cube_stack_ids=tuple(getattr(self._shell, "cube_stacks", {})),
            editor_panel_ids=tuple(getattr(self._shell, "editor_panels", {})),
            override_manager_ids=tuple(getattr(self._shell, "override_managers", {})),
            session_workflow_ids=tuple(self._shell.workflow_session_service.workflows),
            active_workflow_id=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
        )
        for workflow_id, cube_stack in list(self._shell.cube_stacks.items()):
            self._shell.cube_stack_container.removeWidget(cube_stack)
            cube_stack.deleteLater()
            self._shell.cube_stacks.pop(workflow_id, None)
        for workflow_id, editor_panel in list(self._shell.editor_panels.items()):
            self._shell.editor_panel_container.removeWidget(editor_panel)
            editor_panel.deleteLater()
            self._shell.editor_panels.pop(workflow_id, None)
        for workflow_id, manager in list(self._shell.override_managers.items()):
            if workflow_id == SETTINGS_WORKSPACE_ROUTE:
                continue
            dispose = getattr(manager, "dispose", None)
            if callable(dispose):
                dispose()
            self._shell.override_managers.pop(workflow_id, None)

        remove_workflow_tab = getattr(
            self._shell.workflow_tabbar,
            "remove_workflow_tab",
            None,
        )
        if callable(remove_workflow_tab):
            for workflow_id in list(
                self._shell.workflow_tabbar.workflow_ids_in_order()
            ):
                remove_workflow_tab(workflow_id, emit=False)
        self._shell.workflow_session_service.replace_workflows(
            {},
            active_workflow_id="",
        )
        self._shell._pending_restored_workflow_snapshots.clear()
        self._shell._restored_workflow_snapshots_by_id.clear()
        self._shell.cube_stack = None
        self._shell.editor_panel = None
        log_info(
            _LOGGER,
            "mainwindow reset restored workspace completed",
            cube_stack_ids=tuple(getattr(self._shell, "cube_stacks", {})),
            editor_panel_ids=tuple(getattr(self._shell, "editor_panels", {})),
            session_workflow_ids=tuple(self._shell.workflow_session_service.workflows),
            active_workflow_id=self._shell.workflow_session_service.active_workflow_id,
        )
        trace_mark("main_window.reset_restored_workspace.end")

    def add_restored_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Create workflow UI from one normalized workflow snapshot."""

        trace_mark(
            "main_window.add_restored_workflow.start",
            activate=activate,
            **workflow_snapshot_trace_fields(snapshot),
        )
        log_info(
            _LOGGER,
            "mainwindow add restored workflow started",
            workflow_id=snapshot.workflow_id,
            tab_label=snapshot.tab_label,
            activate=activate,
            active_cube_alias=snapshot.active_cube_alias,
            stack_order=tuple(snapshot.workflow.stack_order),
            cube_count=len(snapshot.workflow.cubes),
            session_active_before=self._shell.workflow_session_service.active_workflow_id,
        )
        restored_snapshots = getattr(
            self._shell,
            "_restored_workflow_snapshots_by_id",
            None,
        )
        if not isinstance(restored_snapshots, dict):
            restored_snapshots = {}
            self._shell._restored_workflow_snapshots_by_id = restored_snapshots
        restored_snapshots[snapshot.workflow_id] = snapshot
        transition = self._shell.workflow_session_service.add_existing_workflow(
            snapshot.workflow_id,
            snapshot.workflow,
            activate=activate,
        )
        if bool(getattr(transition, "active_changed", False)):
            outgoing_manager = self._shell.override_managers.get(
                str(getattr(transition, "previous_active_workflow_id", ""))
            )
            if outgoing_manager is not None:
                outgoing_manager._clear_all_override_widgets()
            clear_model_load_progress = getattr(
                self._shell,
                "_clear_all_model_field_load_progress",
                None,
            )
            if callable(clear_model_load_progress):
                clear_model_load_progress()
        self._shell.workflow_tabbar.addTab(snapshot.workflow_id, snapshot.tab_label)
        if not activate:
            self._shell._pending_restored_workflow_snapshots[snapshot.workflow_id] = (
                snapshot
            )
            log_info(
                _LOGGER,
                "mainwindow deferred inactive restored workflow UI",
                workflow_id=snapshot.workflow_id,
                pending_restored_workflow_count=len(
                    self._shell._pending_restored_workflow_snapshots
                ),
            )
            trace_mark(
                "main_window.add_restored_workflow.deferred",
                workflow_id=snapshot.workflow_id,
            )
            return
        with trace_span(
            "main_window.add_restored_workflow.ensure_workflow_ui",
            workflow_id=snapshot.workflow_id,
        ):
            surfaces = self.ensure_workflow_ui(
                snapshot.workflow_id,
                set_as_current=True,
            )
        if snapshot.workflow_id not in self._shell._pending_restored_workflow_snapshots:
            self.materialize_restored_cube_stack(snapshot)
        self._shell.cube_stack = surfaces.cube_stack
        self._shell.editor_panel = surfaces.editor_panel
        log_info(
            _LOGGER,
            "mainwindow add restored workflow completed",
            workflow_id=snapshot.workflow_id,
            activate=activate,
            session_active_after=self._shell.workflow_session_service.active_workflow_id,
            cube_stack_count=len(self._shell.cube_stacks),
            editor_panel_count=len(self._shell.editor_panels),
            active_cube_stack_present=getattr(
                self._shell,
                "active_cube_stack",
                None,
            )
            is not None,
            active_editor_panel_present=getattr(
                self._shell,
                "active_editor_panel",
                None,
            )
            is not None,
        )
        trace_mark(
            "main_window.add_restored_workflow.end",
            workflow_id=snapshot.workflow_id,
        )

    def ensure_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Ensure the editor and document-kind-specific optional cube stack exist."""

        trace_mark(
            "main_window.ensure_workflow_ui.start",
            workflow_id=workflow_id,
            set_as_current=set_as_current,
            cube_stack_exists=workflow_id in self._shell.cube_stacks,
            editor_panel_exists=workflow_id in self._shell.editor_panels,
        )
        cube_stack = self._shell.cube_stacks.get(workflow_id)
        editor_panel = self._shell.editor_panels.get(workflow_id)
        created = editor_panel is None
        if editor_panel is None:
            with trace_span(
                "main_window.ensure_workflow_ui.create_new",
                workflow_id=workflow_id,
            ):
                surfaces = self._create_workflow_ui(
                    workflow_id,
                    set_as_current=set_as_current,
                )
                cube_stack = surfaces.cube_stack
                editor_panel = surfaces.editor_panel
            snapshot = self._shell._pending_restored_workflow_snapshots.pop(
                workflow_id,
                None,
            )
            if snapshot is not None:
                with trace_span(
                    "main_window.ensure_workflow_ui.materialize_deferred_cube_stack",
                    workflow_id=workflow_id,
                ):
                    self.materialize_restored_cube_stack(snapshot)
                log_info(
                    _LOGGER,
                    "mainwindow hydrated deferred restored workflow UI",
                    workflow_id=workflow_id,
                    cube_count=len(snapshot.workflow.cubes),
                    stack_order=tuple(snapshot.workflow.stack_order),
                )
        else:
            workflows = getattr(
                self._shell.workflow_session_service,
                "workflows",
                {},
            )
            workflow = workflows.get(workflow_id)
            needs_reconciliation = cube_stack is None or (
                isinstance(workflow, WorkflowState)
                and workflow.document_kind is WorkflowDocumentKind.DIRECT_COMFY
            )
            if needs_reconciliation:
                cube_stack = workflow_ui_factory_for(
                    self._shell
                ).reconcile_cube_stack_surface(
                    workflow_id,
                    set_as_current=set_as_current,
                )
        if set_as_current and not created:
            self._shell.editor_panel_container.setCurrentWidget(editor_panel)
            self._shell.editor_panel = editor_panel
            if cube_stack is not None:
                self._shell.cube_stack_container.setCurrentWidget(cube_stack)
            self._shell.cube_stack = cube_stack
        trace_mark(
            "main_window.ensure_workflow_ui.end",
            workflow_id=workflow_id,
        )
        return WorkflowUiSurfaces(
            cube_stack=cube_stack,
            editor_panel=editor_panel,
            created=created,
        )

    def _create_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool,
    ) -> WorkflowUiSurfaces:
        """Create workflow widgets through the composed workflow UI owner."""

        factory = getattr(self._shell, "workflow_ui_factory", None)
        create_workflow_ui = getattr(factory, "create_workflow_ui", None)
        if callable(create_workflow_ui):
            return cast(
                WorkflowUiSurfaces,
                create_workflow_ui(workflow_id, set_as_current=set_as_current),
            )
        return workflow_ui_factory_for(self._shell).create_workflow_ui(
            workflow_id,
            set_as_current=set_as_current,
        )

    def snapshot_with_unique_open_ids(
        self,
        snapshot: WorkspaceSnapshot,
    ) -> WorkspaceSnapshot:
        """Return a copy whose workflow ids and labels do not collide."""

        existing_labels = {item.text() for item in self._shell.workflow_tabbar.items}
        return WorkspaceAppendService().snapshot_with_unique_open_ids(
            snapshot,
            existing_workflow_ids=set(self._shell.workflow_session_service.workflows),
            existing_tab_labels=existing_labels,
        )

    @staticmethod
    def unique_restored_workflow_id(
        workflow_id: str,
        existing_ids: set[str],
    ) -> str:
        """Return a workflow id that is not currently open."""

        return WorkspaceAppendService.unique_restored_workflow_id(
            workflow_id,
            existing_ids,
        )

    @staticmethod
    def unique_restored_workflow_label(
        tab_label: str,
        existing_labels: set[str],
    ) -> str:
        """Return a workflow tab label that is not currently open."""

        return WorkspaceAppendService.unique_restored_workflow_label(
            tab_label,
            existing_labels,
        )

    def materialize_restored_cube_stack(self, snapshot: WorkflowSnapshot) -> None:
        """Populate cube-stack tabs from restored workflow cube state."""

        trace_mark(
            "main_window.materialize_restored_cube_stack.start",
            **workflow_snapshot_trace_fields(snapshot),
        )
        cube_stack = self._shell.cube_stacks.get(snapshot.workflow_id)
        if cube_stack is None:
            trace_mark(
                "main_window.materialize_restored_cube_stack.skip",
                reason="missing_cube_stack",
                workflow_id=snapshot.workflow_id,
            )
            log_info(
                _LOGGER,
                "mainwindow materialize restored cube stack skipped missing stack",
                workflow_id=snapshot.workflow_id,
                stack_order=tuple(snapshot.workflow.stack_order),
            )
            return
        log_info(
            _LOGGER,
            "mainwindow materialize restored cube stack started",
            workflow_id=snapshot.workflow_id,
            stack_order=tuple(snapshot.workflow.stack_order),
            active_cube_alias=snapshot.active_cube_alias,
            cube_count=len(snapshot.workflow.cubes),
        )
        result = CubeStackPresenter(
            icon_resolver=CubeTabIconResolver(
                cube_icon_factory=getattr(self._shell, "cube_icon_factory", None),
            ),
        ).rebuild_stack(
            cube_stack,
            workflow_id=snapshot.workflow_id,
            workflow=snapshot.workflow,
            active_cube_alias=snapshot.active_cube_alias,
        )
        log_info(
            _LOGGER,
            "mainwindow materialize restored cube stack completed",
            workflow_id=snapshot.workflow_id,
            final_stack_count=cube_stack.count(),
            final_current_index=cube_stack.currentIndex(),
            active_cube_alias=snapshot.active_cube_alias,
            inserted_count=result.inserted_count,
            warning_count=len(result.warnings),
        )
        trace_mark(
            "main_window.materialize_restored_cube_stack.end",
            workflow_id=snapshot.workflow_id,
            final_stack_count=cube_stack.count(),
            active_cube_alias=snapshot.active_cube_alias,
        )


def restored_workflow_materializer_for(shell: Any) -> RestoredWorkflowMaterializer:
    """Return the composed restored workflow materializer for a shell."""

    materializer = getattr(shell, "restored_workflow_materializer", None)
    if isinstance(materializer, RestoredWorkflowMaterializer):
        return materializer
    materializer = RestoredWorkflowMaterializer(shell)
    setattr(shell, "restored_workflow_materializer", materializer)
    return materializer


__all__ = [
    "RestoredWorkflowMaterializer",
    "restored_workflow_materializer_for",
]
