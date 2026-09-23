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

"""Compose and release shell-owned Output document collaborators."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from .generation_progress_strip_registry import GenerationProgressStripRegistry
from .output_image_pipeline import (
    OutputCanvasProjectionCoordinatorProtocol,
    OutputImagePipeline,
)
from .output_image_preparation_dispatcher import (
    CanvasIoOutputImageLoader,
    OutputImagePreparationDispatcher,
)
from substitute.presentation.canvas.output.output_transfer_composition import (
    OutputTransferLifecycle,
    compose_output_transfer_lifecycle,
)
from substitute.presentation.canvas.output.output_context_menu_composition import (
    compose_output_context_menu,
)
from substitute.presentation.canvas.output.output_transfer_failure_presenter import (
    OutputTransferFailurePresenter,
)
from substitute.presentation.canvas.output.output_transfer_clipboard_publisher import (
    publish_output_transfer_mime_data,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.main_window_output_composition")


@dataclass(frozen=True)
class MainWindowOutputCanvasComposition:
    """Hold output-canvas collaborators composed after canvas widgets exist."""

    output_image_pipeline: Any
    generation_progress_strip_registry: Any
    output_transfer_lifecycle: OutputTransferLifecycle


def compose_output_canvas_controllers(shell: Any) -> MainWindowOutputCanvasComposition:
    """Own Output cleanup in reverse dependency order before native shell teardown."""

    output_canvas = shell.canvas_host.canvas_for("Output")
    if output_canvas is None:
        raise RuntimeError("Canvas tabs must include an Output canvas.")
    shell.shell_resource_lifecycle.register(
        "output_document", output_canvas.document.close
    )

    preparation_dispatcher = _output_image_preparation_dispatcher(shell)
    pipeline_kwargs: dict[str, Any] = {
        "workflow_session_service": shell.workflow_session_service,
        "canvas_io_service": shell.canvas_io_service,
        "output_commit_handler": shell.workspace_canvas_actions,
        "output_preparation_failure_handler": (
            shell.workspace_controller.output_preparation_actions
        ),
        "output_canvas_projection_coordinator": cast(
            OutputCanvasProjectionCoordinatorProtocol,
            shell.output_canvas_projection_coordinator,
        ),
        "canvas_host": shell.canvas_host,
        "generation_timing_lookup": shell.generation_job_queue_service,
        "prompt_interaction_active": (
            shell.prompt_interaction_activity_tracker.is_prompt_interaction_active
        ),
        "prompt_interaction_elapsed_ms": (
            shell.prompt_interaction_activity_tracker.ms_since_last_prompt_interaction
        ),
        "preparation_dispatcher": preparation_dispatcher,
        "parent": shell,
    }
    output_image_pipeline = OutputImagePipeline(**pipeline_kwargs)
    shell.shell_resource_lifecycle.register(
        "output_image_pipeline", output_image_pipeline.shutdown
    )
    output_transfer_lifecycle = _compose_output_transfer_lifecycle(shell)
    generation_progress_strip_registry = GenerationProgressStripRegistry(shell)
    shell.output_floating_chrome_factory.set_progress_strip_registry(
        generation_progress_strip_registry
    )
    composition = MainWindowOutputCanvasComposition(
        output_image_pipeline=output_image_pipeline,
        generation_progress_strip_registry=generation_progress_strip_registry,
        output_transfer_lifecycle=output_transfer_lifecycle,
    )
    shell.output_image_pipeline = composition.output_image_pipeline
    shell.generation_progress_strip_registry = (
        composition.generation_progress_strip_registry
    )
    shell.output_transfer_lifecycle = composition.output_transfer_lifecycle
    return composition


def _compose_output_transfer_lifecycle(shell: Any) -> OutputTransferLifecycle:
    """Install the Output workspace's captured-subject outbound transfer provider."""

    output_canvas = shell.canvas_host.canvas_for("Output")
    if output_canvas is None:
        raise RuntimeError("Canvas tabs must include an Output canvas.")
    drag_submitter = shell.execution_runtime.submitter(
        "image_decode",
        owner_id=f"output_transfer_drag_{id(shell):x}",
        dispatcher=QtOwnerThreadDispatcher(shell),
    )
    clipboard_submitter = shell.execution_runtime.submitter(
        "image_decode",
        owner_id=f"output_transfer_clipboard_{id(shell):x}",
        dispatcher=QtOwnerThreadDispatcher(shell),
    )
    failure_presenter = OutputTransferFailurePresenter(output_canvas)
    lifecycle = compose_output_transfer_lifecycle(
        document=output_canvas.document,
        is_image_authorized=output_canvas.route_projector.is_image_allowed_for_transfer,
        preference_service=shell.output_preference_service,
        drag_submitter=drag_submitter,
        close_drag_submitter=drag_submitter.close,
        clipboard_submitter=clipboard_submitter,
        close_clipboard_submitter=clipboard_submitter.close,
        publish_clipboard_mime_data=publish_output_transfer_mime_data,
        report_clipboard_failure=lambda message: _report_output_transfer_failure(
            failure_presenter.report_copy_failure,
            message,
            operation="output_transfer_clipboard",
        ),
        staging_directory=Path(shell.path_bundle.user_dir)
        / "cache"
        / "output-transfer",
    )
    output_canvas.install_transfer_drag_provider(lifecycle.drag_provider)
    output_canvas.workspace.outboundDragFailed.connect(
        lambda _subject, message: _report_output_transfer_failure(
            failure_presenter.report_drag_failure,
            message,
            operation="output_transfer_drag",
        )
    )
    shell.output_context_menu = compose_output_context_menu(
        output_canvas,
        request_copy=lifecycle.clipboard_controller.copy,
    )
    shell.shell_resource_lifecycle.register("output_transfer", lifecycle.close)
    return lifecycle


def _report_output_transfer_failure(
    present: Callable[[str], None],
    message: str,
    *,
    operation: str,
) -> None:
    """Log technical transfer failure context before localized user feedback."""

    log_warning(
        _LOGGER,
        "Output transfer failed",
        operation=operation,
        reason=message,
    )
    present(message)


def _output_image_preparation_dispatcher(
    shell: Any,
) -> OutputImagePreparationDispatcher:
    """Create the runtime route for output image preparation."""

    execution_runtime = getattr(shell, "execution_runtime", None)
    if execution_runtime is None:
        raise RuntimeError(
            "execution_runtime is required for output image preparation."
        )
    submitter = execution_runtime.submitter(
        "image_decode",
        owner_id=f"output_image_preparation_{id(shell):x}",
        dispatcher=QtOwnerThreadDispatcher(shell),
    )
    return OutputImagePreparationDispatcher(
        loader=CanvasIoOutputImageLoader(shell.canvas_io_service),
        submitter=submitter,
        close_submitter=submitter.close,
        parent=shell,
    )


__all__ = ["MainWindowOutputCanvasComposition", "compose_output_canvas_controllers"]
