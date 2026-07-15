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

"""Prepare saved output images through the shared execution runtime."""

from __future__ import annotations

from collections.abc import Callable
from itertools import count
from pathlib import Path
from time import perf_counter
from typing import Protocol

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    FailedOutputImagePreparation,
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.output_image_preparation_dispatcher")


class OutputImageLoader(Protocol):
    """Describe the narrow image-loading boundary used by output preparation."""

    def load_output_image(self, path: Path) -> QImage | None:
        """Load one output image from disk."""


class CanvasIoOutputImageLoader:
    """Adapt the canvas IO service to the output-image loader protocol."""

    def __init__(self, canvas_io_service: object) -> None:
        """Capture the application service that owns output image loading."""

        self._canvas_io_service = canvas_io_service

    def load_output_image(self, path: Path) -> QImage | None:
        """Load one output image through the canvas IO service."""

        loader = getattr(self._canvas_io_service, "load_output_image", None)
        if not callable(loader):
            return None
        image = loader(path)
        return image if isinstance(image, QImage) else None


class OutputImagePreparationDispatcher(QObject):
    """Dispatch output-image preparation through the shared execution layer."""

    prepared = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        loader: OutputImageLoader,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize execution-backed output image preparation."""

        super().__init__(parent)
        self._loader = loader
        self._request_ids = count(1)
        self._close_submitter = close_submitter
        self._task_scope = TaskScope(
            submitter=submitter,
            scope_id=f"output_image_preparation_{id(self):x}",
        )
        self.destroyed.connect(lambda: self.shutdown())

    def submit(self, request: OutputImageCommitRequest) -> None:
        """Prepare one saved output image off the GUI thread."""

        task_request = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._request_ids),
                domain="output_image_preparation",
                parts=(
                    ("workflow_id", request.workflow_id),
                    ("source_key", request.source_key),
                    ("scene_key", request.scene_key),
                ),
            ),
            context=ExecutionContext(
                operation="output_image_preparation",
                reason="generation_output_update",
                lane="image_decode",
                safe_fields=(
                    ("workflow_id", request.workflow_id),
                    ("node_id", request.node_id),
                    ("source_key", request.source_key),
                    ("scene_key", request.scene_key),
                ),
            ),
            work=lambda _token: prepare_output_image(request, loader=self._loader),
        )
        try:
            handle = self._task_scope.submit(task_request)
        except Exception as error:
            log_exception(
                _LOGGER,
                "Output image preparation submission failed",
                workflow_id=request.workflow_id,
                node_id=request.node_id,
                path=request.file_path,
                source_key=request.source_key,
                scene_key=request.scene_key,
                error=error,
            )
            self.failed.emit(
                FailedOutputImagePreparation(
                    request=request,
                    message="Failed to load generated image.",
                    detail=str(error),
                )
            )
            return
        handle.add_done_callback(
            lambda outcome: self._publish_outcome(outcome, request),
            reason="output_image_preparation_complete",
        )

    def shutdown(self) -> None:
        """Cancel pending preparation work and release dispatcher ownership."""

        self._task_scope.close(reason="output_image_preparation_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _publish_outcome(
        self,
        outcome: TaskOutcome[PreparedOutputImage | FailedOutputImagePreparation],
        request: OutputImageCommitRequest,
    ) -> None:
        """Emit the prepared or failed signal represented by an execution outcome."""

        if outcome.status == "cancelled":
            return
        if outcome.status == "failed":
            self.failed.emit(
                FailedOutputImagePreparation(
                    request=request,
                    message="Failed to load generated image.",
                    detail=str(outcome.error),
                )
            )
            return
        result = outcome.result
        if isinstance(result, PreparedOutputImage):
            self.prepared.emit(result)
            return
        if isinstance(result, FailedOutputImagePreparation):
            self.failed.emit(result)


def prepare_output_image(
    request: OutputImageCommitRequest,
    *,
    loader: OutputImageLoader,
) -> PreparedOutputImage | FailedOutputImagePreparation:
    """Load and detach one output image without touching widgets."""

    started_at = perf_counter()
    try:
        image = loader.load_output_image(request.file_path)
        if image is None or image.isNull():
            log_warning(
                _LOGGER,
                "Failed to prepare output image because decode returned null",
                workflow_id=request.workflow_id,
                node_id=request.node_id,
                path=request.file_path,
                source_key=request.source_key,
                scene_key=request.scene_key,
            )
            return FailedOutputImagePreparation(
                request=request,
                message="Failed to load generated image.",
                detail="Image decoder returned no image data.",
            )

        detached = image.copy()
        log_timing(
            _LOGGER,
            "Prepared output image",
            started_at=started_at,
            workflow_id=request.workflow_id,
            node_id=request.node_id,
            path=request.file_path,
            source_key=request.source_key,
            scene_key=request.scene_key,
        )
        return PreparedOutputImage(
            request=request,
            image=detached,
        )
    except Exception as error:
        log_exception(
            _LOGGER,
            "Output image preparation failed",
            workflow_id=request.workflow_id,
            node_id=request.node_id,
            path=request.file_path,
            source_key=request.source_key,
            scene_key=request.scene_key,
            error=error,
        )
        return FailedOutputImagePreparation(
            request=request,
            message="Failed to load generated image.",
            detail=str(error),
        )


__all__ = [
    "CanvasIoOutputImageLoader",
    "OutputImageLoader",
    "OutputImagePreparationDispatcher",
    "prepare_output_image",
]
