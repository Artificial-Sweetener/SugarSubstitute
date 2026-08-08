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

"""Coordinate full-window synthetic canvas resolution transactions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from cutecanvas import CanvasContentReference

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)
from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
    SyntheticCanvasResolutionRoleService,
)
from substitute.application.workflows.synthetic_canvas_resolution_transaction_service import (
    SyntheticCanvasResolutionProjectionError,
    SyntheticCanvasResolutionStaleError,
    SyntheticCanvasResolutionTransactionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    CanvasDimensions,
    SyntheticCanvasResizeRequest,
    WorkflowState,
)
from substitute.presentation.canvas.input.synthetic_canvas_geometry_adapter import (
    SyntheticCanvasGeometryAdapter,
    SyntheticCanvasGeometryOperation,
    SyntheticCanvasGeometryResult,
    SyntheticCanvasGeometryStatus,
)
from substitute.presentation.dialogs.synthetic_canvas_resolution_dialog import (
    SyntheticCanvasResolutionDialog,
)
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
    log_warning_exception,
)

_LOGGER = get_logger("presentation.shell.synthetic_canvas_resolution_controller")


@dataclass(slots=True)
class _ResolutionSession:
    """Retain one dialog and its guarded canvas identity while it is active."""

    workflow_id: str
    role: SyntheticCanvasResolutionRole
    composition_id: UUID
    canvas_revision: CanvasContentReference
    dialog: SyntheticCanvasResolutionDialog
    operation: SyntheticCanvasGeometryOperation | None = None
    transaction_active: bool = False


class SyntheticCanvasResolutionController(QObject):
    """Own modal lifetime and canvas-to-graph commit ordering."""

    def __init__(
        self,
        *,
        geometry: SyntheticCanvasGeometryAdapter,
        roles: SyntheticCanvasResolutionRoleService,
        transactions: SyntheticCanvasResolutionTransactionService,
        graph_sections: WorkflowGraphSectionService,
        workflows: Callable[[], Mapping[str, WorkflowState]],
        modal_parent: Callable[[], QWidget | None],
        preset_source: Callable[[str], DimensionPresetCatalogSource | None],
        refresh_editor: Callable[[str], None],
        mark_changed: Callable[[str], None],
        request_autosave: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        """Bind graph, canvas, shell, and dialog owners."""

        super().__init__(parent)
        self._geometry = geometry
        self._roles = roles
        self._transactions = transactions
        self._graph_sections = graph_sections
        self._workflows = workflows
        self._modal_parent = modal_parent
        self._preset_source = preset_source
        self._refresh_editor = refresh_editor
        self._mark_changed = mark_changed
        self._request_autosave = request_autosave
        self._session: _ResolutionSession | None = None
        geometry.operationCompleted.connect(self._on_operation_completed)
        geometry.geometryChanged.connect(self._on_geometry_changed)

    def open_for_role(
        self,
        workflow_id: str,
        role: SyntheticCanvasResolutionRole,
    ) -> SyntheticCanvasResolutionDialog | None:
        """Open one full-window dialog after validating graph and canvas identity."""

        if self._session is not None:
            self._session.dialog.raise_()
            self._session.dialog.activateWindow()
            return self._session.dialog
        workflow = self._workflows().get(workflow_id)
        if workflow is None:
            return None
        try:
            current_role = self._transactions.validate(workflow, role)
        except SyntheticCanvasResolutionStaleError:
            return None
        image_entry = workflow.canvas.image_entry(
            f"{current_role.section_key}:{current_role.surface_key}"
        )
        if image_entry is None:
            log_warning(
                _LOGGER,
                "Synthetic resolution dialog has no materialized canvas surface",
                workflow_id=workflow_id,
                section_key=current_role.section_key,
                canvas_surface_key=current_role.surface_key,
            )
            return None
        composition_id = image_entry.image_id
        try:
            canvas_revision = self._geometry.capture_revision(composition_id)
        except (KeyError, RuntimeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Synthetic resolution dialog could not capture canvas revision",
                workflow_id=workflow_id,
                section_key=current_role.section_key,
                canvas_surface_key=current_role.surface_key,
                composition_id=str(composition_id),
                error_type=type(error).__name__,
            )
            return None
        dialog = SyntheticCanvasResolutionDialog(
            role=current_role,
            preset_source=self._preset_source(workflow_id),
            parent=self._modal_parent(),
        )
        session = _ResolutionSession(
            workflow_id=workflow_id,
            role=current_role,
            composition_id=composition_id,
            canvas_revision=canvas_revision,
            dialog=dialog,
        )
        self._session = session
        dialog.resizeRequested.connect(self._begin_resize)
        dialog.cancellationRequested.connect(self._cancel_resize)
        dialog.finished.connect(lambda _result: self._release_dialog(dialog))
        dialog.show()
        return dialog

    def _begin_resize(self, request: object) -> None:
        """Revalidate authority and start CuteCanvas before touching graph values."""

        session = self._session
        workflow = self._workflow_for_session(session)
        if (
            session is None
            or workflow is None
            or not isinstance(request, SyntheticCanvasResizeRequest)
        ):
            return
        try:
            self._transactions.validate(workflow, session.role)
        except SyntheticCanvasResolutionStaleError:
            session.dialog.show_error(_stale_message())
            return
        session.transaction_active = True
        try:
            session.operation = self._geometry.begin(
                composition_id=session.composition_id,
                expected_revision=session.canvas_revision,
                request=request,
            )
        except Exception as error:
            session.transaction_active = False
            session.dialog.show_error(_resize_failed_message())
            log_warning_exception(
                _LOGGER,
                "Synthetic canvas resize could not start",
                error=error,
                workflow_id=session.workflow_id,
                section_key=session.role.section_key,
                composition_id=str(session.composition_id),
            )

    def _cancel_resize(self) -> None:
        """Forward modal cancellation to an in-flight CuteCanvas request."""

        session = self._session
        if session is None or session.operation is None:
            return
        self._geometry.cancel(session.operation)

    def _on_operation_completed(self, result: object) -> None:
        """Commit graph dimensions only after the matching canvas operation succeeds."""

        session = self._session
        if not isinstance(result, SyntheticCanvasGeometryResult) or session is None:
            return
        operation = session.operation
        if operation is None or result.operation != operation:
            return
        workflow = self._workflow_for_session(session)
        if result.status is SyntheticCanvasGeometryStatus.CANCELLED:
            session.transaction_active = False
            session.dialog.finish_cancelled()
            return
        if not result.succeeded or workflow is None:
            if result.changed:
                self._geometry.undo_last_geometry_edit()
                session.canvas_revision = self._geometry.capture_revision(
                    session.composition_id
                )
            session.transaction_active = False
            session.dialog.show_error(
                _stale_message()
                if result.status is SyntheticCanvasGeometryStatus.STALE
                else _resize_failed_message()
            )
            return
        mask_ids_remapped = False
        try:
            mask_ids_remapped = workflow.canvas.remap_mask_ids(
                session.composition_id,
                result.mask_id_remap,
            )
            self._transactions.project(
                workflow,
                expected=session.role,
                dimensions=result.dimensions,
            )
        except (
            SyntheticCanvasResolutionStaleError,
            SyntheticCanvasResolutionProjectionError,
            ValueError,
        ) as error:
            rolled_back = self._geometry.undo_last_geometry_edit()
            if mask_ids_remapped:
                workflow.canvas.remap_mask_ids(
                    session.composition_id,
                    tuple((new_id, old_id) for old_id, new_id in result.mask_id_remap),
                )
            session.transaction_active = False
            session.canvas_revision = self._geometry.capture_revision(
                session.composition_id
            )
            session.dialog.show_error(_projection_failed_message())
            log_warning(
                _LOGGER,
                "Rolled back canvas after graph dimension projection failure",
                workflow_id=session.workflow_id,
                section_key=session.role.section_key,
                composition_id=str(session.composition_id),
                rollback_succeeded=rolled_back,
                error_type=type(error).__name__,
            )
            return
        session.transaction_active = False
        self._publish_change(session.workflow_id)
        log_info(
            _LOGGER,
            "Completed synthetic canvas resolution transaction",
            workflow_id=session.workflow_id,
            section_key=session.role.section_key,
            canvas_surface_key=session.role.surface_key,
            composition_id=str(session.composition_id),
            width=result.dimensions.width,
            height=result.dimensions.height,
        )
        session.dialog.finish_successfully()

    def _on_geometry_changed(
        self,
        composition: object,
        dimensions: object,
        mask_id_remap: object,
    ) -> None:
        """Mirror external CuteCanvas geometry history into synthetic graph authority."""

        resolved_mask_remap = _validated_mask_remap(mask_id_remap)
        if (
            not isinstance(composition, UUID)
            or not isinstance(dimensions, CanvasDimensions)
            or resolved_mask_remap is None
        ):
            return
        session = self._session
        if session is not None and session.transaction_active:
            return
        for workflow_id, workflow in self._workflows().items():
            image_entry = workflow.canvas.image_entry_for_id(composition)
            if image_entry is None:
                continue
            try:
                masks_remapped = workflow.canvas.remap_mask_ids(
                    composition,
                    resolved_mask_remap,
                )
            except ValueError:
                log_warning(
                    _LOGGER,
                    "Rejected external canvas mask identity remap",
                    workflow_id=workflow_id,
                    composition_id=str(composition),
                )
                return
            section_key, separator, surface_key = image_entry.input_key.partition(":")
            if not separator or not surface_key.startswith("@synthetic/"):
                continue
            graph = self._graph_sections.graph(workflow, section_key)
            if graph is None:
                continue
            role = self._roles.resolve_for_surface(
                section_key=section_key,
                graph=graph,
                surface_key=surface_key,
            )
            if role is None or role.authority.dimensions == dimensions:
                if masks_remapped:
                    self._publish_change(workflow_id)
                return
            try:
                self._transactions.project(
                    workflow,
                    expected=role,
                    dimensions=dimensions,
                )
            except (
                SyntheticCanvasResolutionStaleError,
                SyntheticCanvasResolutionProjectionError,
            ):
                return
            self._publish_change(workflow_id)
            return

    def _publish_change(self, workflow_id: str) -> None:
        """Refresh card projection and persist one completed resolution mutation."""

        self._mark_changed(workflow_id)
        self._refresh_editor(workflow_id)
        self._request_autosave()

    def _workflow_for_session(
        self,
        session: _ResolutionSession | None,
    ) -> WorkflowState | None:
        """Return the live workflow still owning an active dialog session."""

        return self._workflows().get(session.workflow_id) if session else None

    def _release_dialog(self, dialog: SyntheticCanvasResolutionDialog) -> None:
        """Release only the currently owned dialog lifetime."""

        if self._session is not None and self._session.dialog is dialog:
            self._session = None


def _stale_message() -> str:
    """Return localized copy for stale graph or canvas state."""

    return render_application_text(
        app_text(
            "The canvas changed while this dialog was open. Review the current size and try again."
        )
    )


def _resize_failed_message() -> str:
    """Return localized copy for a rejected CuteCanvas operation."""

    return render_application_text(
        app_text("The canvas could not be resized. Nothing was changed.")
    )


def _projection_failed_message() -> str:
    """Return localized copy for a rolled-back graph projection failure."""

    return render_application_text(
        app_text(
            "The workflow dimensions could not be updated, so the canvas change was undone."
        )
    )


def _validated_mask_remap(
    value: object,
) -> tuple[tuple[UUID, UUID], ...] | None:
    """Return a strongly typed mask remap from the Qt signal boundary."""

    if not isinstance(value, tuple) or not all(
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], UUID)
        and isinstance(item[1], UUID)
        for item in value
    ):
        return None
    return tuple((item[0], item[1]) for item in value)


__all__ = ["SyntheticCanvasResolutionController"]
