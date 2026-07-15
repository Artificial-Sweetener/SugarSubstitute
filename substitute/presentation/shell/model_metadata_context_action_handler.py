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

"""Schedule model metadata context-menu actions outside the Qt UI thread."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from substitute.application.execution import (
    CancellationToken as ExecutionCancellationToken,
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.model_metadata import (
    ManualModelMetadataRefreshRequest,
    ManualModelMetadataRefreshResult,
    RefreshCancellationToken,
    SetModelThumbnailFromOutputRequest,
    SetModelThumbnailFromOutputResult,
)
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
    OutputCanvasThumbnailChoiceProvider,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_warning,
)

if TYPE_CHECKING:
    from substitute.presentation.widgets.model_metadata_context_menu import (
        ModelMetadataContextMenuTarget,
    )

_LOGGER = get_logger("presentation.shell.model_metadata_context_action_handler")


class ManualModelMetadataRefreshRunner(Protocol):
    """Describe the manual refresh application use case."""

    def refresh_model(
        self,
        request: ManualModelMetadataRefreshRequest,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> ManualModelMetadataRefreshResult:
        """Refresh one selected local model's CivitAI metadata."""


class SetModelThumbnailFromOutputRunner(Protocol):
    """Describe the local output-thumbnail assignment use case."""

    def set_thumbnail(
        self,
        request: SetModelThumbnailFromOutputRequest,
        *,
        cancellation_token: RefreshCancellationToken,
    ) -> SetModelThumbnailFromOutputResult:
        """Assign one output canvas image as a model thumbnail."""


class _ExecutionRefreshCancellationToken:
    """Adapt execution cancellation tokens to metadata refresh cancellation."""

    def __init__(self, token: ExecutionCancellationToken) -> None:
        """Store the execution token backing refresh cancellation checks."""

        self._token = token

    def is_cancelled(self) -> bool:
        """Return whether the owning execution task has been cancelled."""

        return self._token.is_cancelled


class ModelMetadataContextActionScheduler:
    """Schedule model metadata menu commands without blocking Qt widgets."""

    def __init__(
        self,
        *,
        refresh_service: ManualModelMetadataRefreshRunner,
        output_thumbnail_service: SetModelThumbnailFromOutputRunner | None = None,
        output_thumbnail_choices: OutputCanvasThumbnailChoiceProvider | None = None,
        submitter: TaskSubmitter | None = None,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Store the refresh service and initialize duplicate request tracking."""

        self._refresh_service = refresh_service
        self._output_thumbnail_service = output_thumbnail_service
        self._output_thumbnail_choices = output_thumbnail_choices
        if submitter is None:
            raise TypeError("submitter is required for model metadata context actions.")
        self._scope = TaskScope(
            submitter=submitter,
            scope_id=f"model_metadata_context_actions_{id(self):x}",
        )
        self._close_submitter = close_submitter
        self._running_keys: set[tuple[str, str]] = set()
        self._running_thumbnail_keys: set[tuple[str, str, UUID]] = set()
        self._shutdown_requested = False
        self._lock = RLock()
        self._request_id = 0

    def refresh_civitai_metadata(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> None:
        """Schedule a manual CivitAI metadata refresh for the target model."""

        kind = (target.model_kind or "").strip()
        value = (target.backend_value or "").strip()
        if not kind or not value:
            log_warning(
                _LOGGER,
                "Manual metadata refresh rejected for incomplete target",
                title=target.title,
                model_kind=kind,
                backend_value=value,
            )
            return
        key = (kind, value)
        with self._lock:
            if self._shutdown_requested:
                return
            if key in self._running_keys:
                log_debug(
                    _LOGGER,
                    "Manual metadata refresh request coalesced",
                    kind=kind,
                    value=value,
                )
                return
            self._running_keys.add(key)
        try:
            identity = self._next_identity(
                operation_key="manual_refresh",
                kind=kind,
            )
            self._scope.submit(
                TaskRequest(
                    identity=identity,
                    context=self._context(
                        operation="manual_model_metadata_refresh",
                        operation_key="manual_refresh",
                        kind=kind,
                        request_id=identity.request_id,
                    ),
                    work=lambda token: self._run_refresh(
                        key,
                        cancellation=_ExecutionRefreshCancellationToken(token),
                    ),
                )
            )
        except Exception:
            with self._lock:
                self._running_keys.discard(key)
            log_exception(
                _LOGGER,
                "Failed to schedule manual metadata refresh",
                kind=kind,
                value=value,
            )

    def configure_output_thumbnail_assignment(
        self,
        *,
        output_thumbnail_service: SetModelThumbnailFromOutputRunner,
        output_thumbnail_choices: OutputCanvasThumbnailChoiceProvider,
    ) -> None:
        """Install output-thumbnail collaborators once canvas state exists."""

        with self._lock:
            if self._shutdown_requested:
                return
            self._output_thumbnail_service = output_thumbnail_service
            self._output_thumbnail_choices = output_thumbnail_choices

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return selectable final output images for thumbnail assignment."""

        if self._output_thumbnail_choices is None:
            return ()
        return self._output_thumbnail_choices.choices()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return the active final output image for thumbnail assignment."""

        if self._output_thumbnail_choices is None:
            return None
        return self._output_thumbnail_choices.active_choice()

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Schedule assigning one output image as the target model thumbnail."""

        service = self._output_thumbnail_service
        if service is None:
            log_warning(
                _LOGGER,
                "Output thumbnail assignment rejected without service",
                title=target.title,
                image_id=str(image_id),
            )
            return
        kind = (target.model_kind or "").strip()
        value = (target.backend_value or "").strip()
        if not kind or not value:
            log_warning(
                _LOGGER,
                "Output thumbnail assignment rejected for incomplete target",
                title=target.title,
                model_kind=kind,
                backend_value=value,
                image_id=str(image_id),
            )
            return
        key = (kind, value, image_id)
        with self._lock:
            if self._shutdown_requested:
                return
            if key in self._running_thumbnail_keys:
                log_debug(
                    _LOGGER,
                    "Output thumbnail assignment request coalesced",
                    kind=kind,
                    value=value,
                    image_id=str(image_id),
                )
                return
            self._running_thumbnail_keys.add(key)
        try:
            identity = self._next_identity(
                operation_key="output_thumbnail_assignment",
                kind=kind,
            )
            self._scope.submit(
                TaskRequest(
                    identity=identity,
                    context=self._context(
                        operation="output_thumbnail_assignment",
                        operation_key="output_thumbnail_assignment",
                        kind=kind,
                        request_id=identity.request_id,
                    ),
                    work=lambda token: self._run_output_thumbnail_assignment(
                        key,
                        cancellation=_ExecutionRefreshCancellationToken(token),
                    ),
                )
            )
        except Exception:
            with self._lock:
                self._running_thumbnail_keys.discard(key)
            log_exception(
                _LOGGER,
                "Failed to schedule output thumbnail assignment",
                kind=kind,
                value=value,
                image_id=str(image_id),
            )

    def shutdown(self) -> None:
        """Stop accepting work and release owned execution resources."""

        with self._lock:
            self._shutdown_requested = True
            self._running_keys.clear()
            self._running_thumbnail_keys.clear()
        self._scope.close(reason="model_metadata_context_actions_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _next_identity(self, *, operation_key: str, kind: str) -> TaskIdentity:
        """Return the next task identity for one metadata menu action."""

        with self._lock:
            self._request_id += 1
            request_id = self._request_id
        return TaskIdentity(
            request_id=request_id,
            domain="model_metadata",
            parts=(("operation_key", operation_key), ("kind", kind)),
        )

    def _context(
        self,
        *,
        operation: str,
        operation_key: str,
        kind: str,
        request_id: int,
    ) -> ExecutionContext:
        """Return sanitized execution context for one metadata menu action."""

        return ExecutionContext(
            operation=operation,
            reason="model_metadata_context_menu",
            lane="model_metadata",
            safe_fields=(
                ("operation_key", operation_key),
                ("kind", kind),
                ("request_id", request_id),
            ),
        )

    def _run_refresh(
        self,
        key: tuple[str, str],
        *,
        cancellation: RefreshCancellationToken,
    ) -> None:
        """Run one scheduled refresh and release duplicate tracking."""

        kind, value = key
        try:
            result = self._refresh_service.refresh_model(
                ManualModelMetadataRefreshRequest(kind=kind, value=value),
                cancellation_token=cancellation,
            )
            log_info(
                _LOGGER,
                "Manual metadata refresh action completed",
                kind=kind,
                value=value,
                status=result.status.value,
                provider_status=result.provider_status,
                thumbnail_updated=result.thumbnail_updated,
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Manual metadata refresh action failed",
                kind=kind,
                value=value,
            )
        finally:
            with self._lock:
                self._running_keys.discard(key)

    def _run_output_thumbnail_assignment(
        self,
        key: tuple[str, str, UUID],
        *,
        cancellation: RefreshCancellationToken,
    ) -> None:
        """Run one scheduled output thumbnail assignment."""

        kind, value, image_id = key
        service = self._output_thumbnail_service
        if service is None:
            with self._lock:
                self._running_thumbnail_keys.discard(key)
            return
        try:
            result = service.set_thumbnail(
                SetModelThumbnailFromOutputRequest(
                    kind=kind,
                    value=value,
                    image_id=image_id,
                ),
                cancellation_token=cancellation,
            )
            log_info(
                _LOGGER,
                "Output thumbnail assignment action completed",
                kind=kind,
                value=value,
                image_id=str(image_id),
                status=result.status.value,
                relative_path=result.relative_path,
                sha256=result.sha256,
                thumbnail_updated=result.thumbnail_updated,
                result_message=result.message,
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Output thumbnail assignment action failed",
                kind=kind,
                value=value,
                image_id=str(image_id),
            )
        finally:
            with self._lock:
                self._running_thumbnail_keys.discard(key)


__all__ = [
    "ManualModelMetadataRefreshRunner",
    "ModelMetadataContextActionScheduler",
    "SetModelThumbnailFromOutputRunner",
]
