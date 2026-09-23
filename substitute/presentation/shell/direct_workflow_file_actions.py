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

"""Materialize direct Comfy workflow documents into workflow tabs."""

from __future__ import annotations

from substitute.presentation.workflows.workflow_tabs_view import (
    set_workflow_tab_source_text,
    workflow_tab_source_text,
)

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.application.recipes import RecipeModelDownloadResolutionError
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.common import JsonObject
from substitute.application.errors import SubstituteOperationContext
from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.shared.logging.logger import get_logger, log_exception, log_info

from .workflow_document_target import (
    WorkflowDocumentTargetResolver,
    WorkflowDocumentTargetView,
)
from .workflow_surface_invalidation import (
    CUBE_STRUCTURE_SURFACES,
    WorkflowInvalidationReason,
)
from .direct_workflow_model_resolution import (
    DirectWorkflowModelResolutionController,
)

_LOGGER = get_logger("presentation.shell.direct_workflow_file_actions")


class DirectWorkflowTabItem(Protocol):
    """Expose visible tab-label mutation for a loaded workflow."""

    def text(self) -> str:
        """Return the current label."""

    def setText(self, text: str) -> None:
        """Replace the visible label."""


class DirectWorkflowFileActionView(WorkflowDocumentTargetView, Protocol):
    """Describe shell state used to materialize a direct workflow."""

    workflow_tab_service: object
    workflow_surface_invalidation_service: object


class DirectWorkflowFileActions:
    """Load one complete Comfy graph without entering recipe materialization."""

    def __init__(
        self,
        *,
        view: DirectWorkflowFileActionView,
        load_service: DirectWorkflowLoadService,
        add_workflow_tab: Callable[[], object],
        refresh_active_workflow: Callable[[], None],
        materialize_loaded_section: Callable[[str, str], None] | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        target_resolver: WorkflowDocumentTargetResolver | None = None,
        model_resolution_controller_provider: (
            Callable[[], DirectWorkflowModelResolutionController | None] | None
        ) = None,
    ) -> None:
        """Store document loading and shell projection collaborators."""

        self._view = view
        self._load_service = load_service
        self._add_workflow_tab = add_workflow_tab
        self._refresh_active_workflow = refresh_active_workflow
        self._materialize_loaded_section = materialize_loaded_section
        self._error_presenter = error_presenter
        self._target_resolver = target_resolver or WorkflowDocumentTargetResolver()
        self._model_resolution_controller_provider = (
            model_resolution_controller_provider
        )

    def load_document(self, source_path: Path) -> str | None:
        """Load a direct Comfy workflow into a blank or newly created tab."""

        path = source_path.resolve()
        target_workflow_id = self._view.workflow_session_service.active_workflow_id
        try:
            controller = (
                self._model_resolution_controller_provider()
                if self._model_resolution_controller_provider is not None
                else None
            )
            if controller is not None:
                loaded_workflow = self._load_service.read(path)
                target_workflow_id = self._resolve_target_workflow_id()
                controller.resolve(
                    workflow=loaded_workflow,
                    target_workflow_id=target_workflow_id,
                    completed=lambda workflow: self._materialize_resolved_workflow(
                        path,
                        workflow,
                        target_workflow_id=target_workflow_id,
                    ),
                    cancelled=lambda: log_info(
                        _LOGGER,
                        "Direct Comfy workflow load cancelled during model review",
                        workflow_id=target_workflow_id,
                        source_path=path,
                    ),
                    failed=lambda error: self._handle_load_failure(
                        error,
                        path=path,
                        workflow_id=target_workflow_id,
                    ),
                )
                return target_workflow_id
            document = self._load_service.load(path)
            target_workflow_id = self._resolve_target_workflow_id()
            return self._materialize_document(
                path,
                document,
                target_workflow_id=target_workflow_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                _LOGGER,
                "Failed to load direct Comfy workflow",
                workflow_id=target_workflow_id,
                source_path=path,
                error=error,
            )
            self._present_failure(error, path=path, workflow_id=target_workflow_id)
            return None

    def _materialize_resolved_workflow(
        self,
        path: Path,
        workflow: JsonObject,
        *,
        target_workflow_id: str,
    ) -> None:
        """Convert and mount a model-resolved canonical graph on the owner thread."""

        try:
            document = self._load_service.materialize(path, workflow)
            self._materialize_document(
                path,
                document,
                target_workflow_id=target_workflow_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._handle_load_failure(
                error,
                path=path,
                workflow_id=target_workflow_id,
            )

    def _materialize_document(
        self,
        path: Path,
        document: DirectWorkflowState,
        *,
        target_workflow_id: str,
    ) -> str:
        """Mount one fully resolved direct workflow into its document target."""

        session = self._view.workflow_session_service
        workflows = getattr(session, "workflows", None)
        if not isinstance(workflows, Mapping):
            raise RuntimeError("Workflow session has no workflow mapping.")
        workflow = workflows.get(target_workflow_id)
        load_direct_workflow = getattr(workflow, "load_direct_workflow", None)
        if not callable(load_direct_workflow):
            raise RuntimeError("Target workflow cannot load direct documents.")
        load_direct_workflow(document)
        self._rename_target_tab(path.stem, target_workflow_id)
        self._mark_surfaces_dirty(target_workflow_id)
        unsaved_work_service = getattr(self._view, "unsaved_work_service", None)
        mark_saved = getattr(unsaved_work_service, "mark_saved", None)
        if callable(mark_saved):
            mark_saved(target_workflow_id, path)
        if target_workflow_id == session.active_workflow_id:
            self._refresh_active_workflow()
            if self._materialize_loaded_section is not None:
                self._materialize_loaded_section(
                    target_workflow_id,
                    DIRECT_WORKFLOW_SECTION_KEY,
                )
        nodes = document.buffer.get("nodes")
        log_info(
            _LOGGER,
            "Direct Comfy workflow materialized",
            workflow_id=target_workflow_id,
            source_path=path,
            node_count=len(nodes) if isinstance(nodes, Mapping) else 0,
        )
        return target_workflow_id

    def _resolve_target_workflow_id(self) -> str:
        """Reserve the stable workflow target before asynchronous model work."""

        return self._target_resolver.resolve(
            self._view,
            add_workflow_tab=self._add_workflow_tab,
        )

    def _handle_load_failure(
        self,
        error: BaseException,
        *,
        path: Path,
        workflow_id: str,
    ) -> None:
        """Log and present a synchronous or deferred direct-workflow failure."""

        log_exception(
            _LOGGER,
            "Failed to load direct Comfy workflow",
            workflow_id=workflow_id,
            source_path=path,
            error=error,
        )
        self._present_failure(error, path=path, workflow_id=workflow_id)

    def can_load_document(self, source_path: Path) -> bool:
        """Return whether the source exposes an available direct Comfy workflow."""

        return self._load_service.can_load(source_path)

    def _rename_target_tab(self, base_name: str, workflow_id: str) -> None:
        """Apply a unique visible document label without changing the session key."""

        tabbar = self._view.workflow_tabbar
        item_map = getattr(tabbar, "itemMap", None)
        if not isinstance(item_map, Mapping):
            raise RuntimeError("Workflow tab bar has no item map.")
        tab_service = self._view.workflow_tab_service
        resolve_unique_label = getattr(tab_service, "resolve_unique_label", None)
        if not callable(resolve_unique_label):
            raise RuntimeError("Workflow tab service cannot resolve document labels.")
        existing_labels = {
            workflow_tab_source_text(item)
            for key, item in item_map.items()
            if key != workflow_id and hasattr(item, "text")
        }
        label = resolve_unique_label(base_name, existing_labels)
        target_item = item_map.get(workflow_id)
        if target_item is None or not hasattr(target_item, "setText"):
            raise RuntimeError("Target workflow tab item is unavailable.")
        set_workflow_tab_source_text(target_item, label)

    def _mark_surfaces_dirty(self, workflow_id: str) -> None:
        """Request shared workflow surfaces after document state changes."""

        mark_dirty = getattr(
            self._view.workflow_surface_invalidation_service,
            "mark_dirty",
            None,
        )
        if callable(mark_dirty):
            mark_dirty(
                workflow_id,
                CUBE_STRUCTURE_SURFACES,
                WorkflowInvalidationReason.DIRECT_WORKFLOW_LOADED,
            )

    def _present_failure(
        self,
        error: BaseException,
        *,
        path: Path,
        workflow_id: str,
    ) -> None:
        """Present a structured error when the shell has an error surface."""

        if self._error_presenter is None:
            return
        is_model_download_failure = isinstance(
            error,
            RecipeModelDownloadResolutionError,
        )
        self._error_presenter.show_exception_report(
            title=(
                app_text("Model download failed")
                if is_model_download_failure
                else app_text("Workflow could not be loaded")
            ),
            message=(
                app_text(
                    "Substitute could not download and verify every model this workflow needs."
                )
                if is_model_download_failure
                else app_text(
                    "Substitute could not read this ComfyUI workflow document."
                )
            ),
            stage="load",
            error=error,
            context=SubstituteOperationContext(
                operation="load_direct_comfy_workflow",
                workflow_id=workflow_id,
                path=str(path),
            ),
        )


__all__ = ["DirectWorkflowFileActions", "DirectWorkflowFileActionView"]
