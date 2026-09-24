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

"""Own asynchronous Output preparation submission and failure presentation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from PySide6.QtWidgets import QMessageBox
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.application.ports import OutputImageUpdate
from substitute.presentation.shell.output_image_commit_pipeline import (
    FailedOutputImagePreparation,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.workspace_output_preparation_actions")


class MessageBoxProtocol(Protocol):
    """Describe fallback message-box behavior for preparation failures."""

    def critical(self, parent: object, title: str, text: str) -> None:
        """Show a critical error dialog."""


class OutputPreparationErrorPresenterProtocol(Protocol):
    """Present structured Output preparation failures."""

    def show_error_report(self, report: ErrorReport) -> None:
        """Present one structured failure report."""


class WorkspaceOutputPreparationView(Protocol):
    """Describe the shell surface used by Output preparation actions."""

    output_image_pipeline: object


class WorkspaceOutputPreparationActions:
    """Submit Output preparation work and present asynchronous failures."""

    def __init__(
        self,
        view: WorkspaceOutputPreparationView,
        *,
        error_presenter: OutputPreparationErrorPresenterProtocol | None = None,
    ) -> None:
        """Store the Output pipeline view and structured error presenter."""

        self._view = view
        self._error_presenter = error_presenter

    def handle_output_image_preparation_failed(
        self,
        failure: FailedOutputImagePreparation,
        *,
        message_box: MessageBoxProtocol | None = None,
    ) -> None:
        """Present one failed asynchronous output image preparation."""

        request = failure.request
        self._show_generated_image_load_error(
            workflow_id=request.workflow_id,
            node_id=request.node_id,
            file_path=str(request.file_path),
            source_key=request.source_key,
            source_label=request.source_label,
            scene_run_id=request.scene_run_id,
            scene_key=request.scene_key,
            scene_title=request.scene_title,
            scene_order=request.scene_order,
            scene_count=request.scene_count,
            fallback_message_box=(
                message_box
                if message_box is not None
                else cast(MessageBoxProtocol, QMessageBox)
            ),
        )

    def prepare_output_image_commit(self, output_update: OutputImageUpdate) -> None:
        """Submit a final output image for asynchronous preparation."""

        submit = getattr(
            getattr(self._view, "output_image_pipeline", None),
            "submit_output_update",
            None,
        )
        if callable(submit):
            submit(output_update)
            return
        log_warning(
            _LOGGER,
            "Output image pipeline unavailable for generated output",
            workflow_id=output_update.workflow_id,
            node_id=output_update.node_id,
            path=output_update.file_path,
        )

    def prepare_legacy_output_image_commit(
        self,
        output_update: OutputImageUpdate,
    ) -> None:
        """Submit a non-live output image through explicit fallback semantics."""

        pipeline = getattr(self._view, "output_image_pipeline", None)
        submit_legacy = getattr(pipeline, "submit_legacy_output_update", None)
        if callable(submit_legacy):
            submit_legacy(output_update)
            return
        log_warning(
            _LOGGER,
            "Output image pipeline unavailable for legacy generated output",
            workflow_id=output_update.workflow_id,
            node_id=output_update.node_id,
            path=output_update.file_path,
        )

    def update_canvas_callback(
        self,
        workflow_id: str,
        workflow: dict[str, object],
        file_path: str,
        node_id: str,
        *,
        source_key: str = "",
        source_label: str = "",
        scene_run_id: str | None = None,
        scene_key: str | None = None,
        scene_title: str | None = None,
        scene_order: int | None = None,
        scene_count: int | None = None,
        message_box: MessageBoxProtocol | None = None,
    ) -> None:
        """Delegate generated image commits to the asynchronous output pipeline."""

        _ = message_box
        self.prepare_legacy_output_image_commit(
            OutputImageUpdate(
                workflow_id=workflow_id,
                workflow_payload=workflow,
                file_path=Path(file_path),
                node_id=node_id,
                source_key=source_key,
                source_label=source_label,
                scene_run_id=scene_run_id,
                scene_key=scene_key,
                scene_title=scene_title,
                scene_order=scene_order,
                scene_count=scene_count,
            )
        )

    def _show_generated_image_load_error(
        self,
        *,
        workflow_id: str,
        node_id: str,
        file_path: str,
        source_key: str,
        source_label: str,
        scene_run_id: str | None,
        scene_key: str | None,
        scene_title: str | None,
        scene_order: int | None,
        scene_count: int | None,
        fallback_message_box: MessageBoxProtocol,
    ) -> None:
        """Show an output-image load failure through the structured modal surface."""

        message = app_text("Could not load image: %1", file_path)
        if self._error_presenter is None:
            fallback_message_box.critical(
                self._view,
                render_application_text(app_text("Load Error")),
                render_application_text(message),
            )
            return

        self._error_presenter.show_error_report(
            ErrorReport(
                kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
                title=app_text("Generated image load failed"),
                message=message,
                stage="canvas",
                workflow_id=workflow_id,
                technical_detail=message,
                operation_context=SubstituteOperationContext(
                    operation="load_generated_output_image",
                    workflow_id=workflow_id,
                    path=file_path,
                    node_id=node_id,
                    values={
                        "source_key": source_key,
                        "source_label": source_label,
                        "scene_run_id": scene_run_id,
                        "scene_key": scene_key,
                        "scene_title": scene_title,
                        "scene_order": scene_order,
                        "scene_count": scene_count,
                    },
                ),
            )
        )


__all__ = ["WorkspaceOutputPreparationActions", "WorkspaceOutputPreparationView"]
