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

"""Coordinate editor busy presentation across workflow-scoped cube operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("presentation.shell.editor_busy_coordinator")


@dataclass(frozen=True)
class EditorBusyToken:
    """Identify one workflow-scoped editor busy operation."""

    workflow_id: str
    operation_id: str


@dataclass
class EditorBusyDownloadState:
    """Describe workflow-scoped download progress for the busy overlay."""

    title: ApplicationText
    message: ApplicationText
    detail: ApplicationText
    progress_per_mille: int | None
    cancel_enabled: bool = True


@dataclass
class _EditorBusyEntry:
    """Store one active workflow busy operation."""

    message: ApplicationText
    download_state: EditorBusyDownloadState | None = None
    cancel_callback: Callable[[], None] | None = None


class EditorBusyOverlayProtocol(Protocol):
    """Describe the overlay behavior required by the busy coordinator."""

    def show_loading(self, message: ApplicationText = app_text("Loading")) -> None:
        """Show the busy overlay with a base loading message."""

    def hide_loading(self) -> None:
        """Hide the busy overlay."""

    def show_download_progress(
        self,
        *,
        title: ApplicationText,
        message: ApplicationText,
        detail: ApplicationText,
        progress_per_mille: int | None,
        cancel_enabled: bool = True,
    ) -> None:
        """Show workflow-scoped download progress."""


class EditorBusyControllerProtocol(Protocol):
    """Describe editor busy operations exposed to shell collaborators."""

    def begin(
        self,
        workflow_id: str,
        *,
        message: ApplicationText = app_text("Loading"),
    ) -> EditorBusyToken:
        """Begin one editor busy operation for a workflow."""

    def end(self, token: EditorBusyToken | object) -> None:
        """End one editor busy operation if the token is still active."""

    def update_download(
        self,
        token: EditorBusyToken | object,
        state: EditorBusyDownloadState,
    ) -> None:
        """Update progress for one workflow-scoped download operation."""

    def set_cancel_callback(
        self,
        token: EditorBusyToken | object,
        callback: Callable[[], None] | None,
    ) -> None:
        """Set the cancel callback for one active download operation."""

    def refresh_active_surface(self) -> None:
        """Refresh the active workflow's busy presentation."""

    def shutdown(self) -> None:
        """Release busy presentation during shell disposal."""


class EditorBusyCoordinator:
    """Reference-count editor busy state and project it onto the active workflow."""

    def __init__(
        self,
        *,
        active_workflow_id: Callable[[], str],
        is_editor_surface_active: Callable[[], bool],
        overlay: EditorBusyOverlayProtocol,
    ) -> None:
        """Store workflow lookup and overlay collaborators."""

        self._active_workflow_id = active_workflow_id
        self._is_editor_surface_active = is_editor_surface_active
        self._overlay = overlay
        self._tokens_by_workflow: dict[str, dict[str, _EditorBusyEntry]] = {}
        self._is_shutdown = False

    def begin(
        self,
        workflow_id: str,
        *,
        message: ApplicationText = app_text("Loading"),
    ) -> EditorBusyToken:
        """Begin one editor busy operation for a workflow."""

        token = EditorBusyToken(workflow_id=workflow_id, operation_id=uuid4().hex)
        if self._is_shutdown:
            return token
        self._tokens_by_workflow.setdefault(workflow_id, {})[token.operation_id] = (
            _EditorBusyEntry(message=message)
        )
        log_debug(
            _LOGGER,
            "Began editor busy operation",
            workflow_id=workflow_id,
            operation_id=token.operation_id,
            busy_message=message,
        )
        self.refresh_active_surface()
        return token

    def update_download(
        self,
        token: EditorBusyToken | object,
        state: EditorBusyDownloadState,
    ) -> None:
        """Update progress for one workflow-scoped download operation."""

        entry = self._entry_for_token(token)
        if entry is None:
            return
        entry.download_state = state
        self.refresh_active_surface()

    def set_cancel_callback(
        self,
        token: EditorBusyToken | object,
        callback: Callable[[], None] | None,
    ) -> None:
        """Set the cancel callback for one active download operation."""

        entry = self._entry_for_token(token)
        if entry is None:
            return
        entry.cancel_callback = callback

    def request_active_cancel(self) -> None:
        """Invoke the cancel callback for the active workflow's newest operation."""

        workflow_id = self._active_workflow_id()
        workflow_tokens = self._tokens_by_workflow.get(workflow_id, {})
        if not workflow_tokens:
            return
        entry = next(reversed(workflow_tokens.values()))
        if entry.cancel_callback is not None:
            entry.cancel_callback()

    def end(self, token: EditorBusyToken | object) -> None:
        """End one editor busy operation if the token is still active."""

        if self._is_shutdown:
            return
        if not isinstance(token, EditorBusyToken):
            log_warning(
                _LOGGER,
                "Ignored invalid editor busy token",
                token_type=type(token).__name__,
            )
            return
        workflow_tokens = self._tokens_by_workflow.get(token.workflow_id)
        if workflow_tokens is None or token.operation_id not in workflow_tokens:
            log_warning(
                _LOGGER,
                "Ignored stale editor busy token",
                workflow_id=token.workflow_id,
                operation_id=token.operation_id,
            )
            return
        workflow_tokens.pop(token.operation_id, None)
        if not workflow_tokens:
            self._tokens_by_workflow.pop(token.workflow_id, None)
        log_debug(
            _LOGGER,
            "Ended editor busy operation",
            workflow_id=token.workflow_id,
            operation_id=token.operation_id,
        )
        self.refresh_active_surface()

    def clear_workflow(self, workflow_id: str) -> None:
        """Clear all busy tokens for one workflow and refresh the active overlay."""

        if self._tokens_by_workflow.pop(workflow_id, None) is None:
            return
        log_debug(_LOGGER, "Cleared editor busy workflow", workflow_id=workflow_id)
        self.refresh_active_surface()

    def refresh_active_surface(self) -> None:
        """Show or hide the overlay according to the active workflow's busy state."""

        if self._is_shutdown or not self._is_editor_surface_active():
            self._overlay.hide_loading()
            return
        workflow_id = self._active_workflow_id()
        workflow_tokens = self._tokens_by_workflow.get(workflow_id, {})
        if not workflow_tokens:
            is_loading = getattr(self._overlay, "is_loading", None)
            if not callable(is_loading) or bool(is_loading()):
                trace_mark(
                    "editor_projection.loading_wash_removed",
                    workflow_id=workflow_id,
                    projection_mode="live",
                )
            self._overlay.hide_loading()
            return
        entry = next(reversed(workflow_tokens.values()))
        if entry.download_state is not None:
            self._overlay.show_download_progress(
                title=entry.download_state.title,
                message=entry.download_state.message,
                detail=entry.download_state.detail,
                progress_per_mille=entry.download_state.progress_per_mille,
                cancel_enabled=entry.download_state.cancel_enabled,
            )
            return
        self._overlay.show_loading(entry.message)

    def shutdown(self) -> None:
        """Release busy presentation and reject work after shell disposal."""

        if self._is_shutdown:
            return
        self._is_shutdown = True
        self._tokens_by_workflow.clear()
        self._overlay.hide_loading()

    def has_pending_workflow(self, workflow_id: str) -> bool:
        """Return whether a workflow currently has active busy operations."""

        return bool(self._tokens_by_workflow.get(workflow_id))

    def _entry_for_token(
        self,
        token: EditorBusyToken | object,
    ) -> _EditorBusyEntry | None:
        """Return a mutable entry for a valid active token."""

        if not isinstance(token, EditorBusyToken):
            return None
        workflow_tokens = self._tokens_by_workflow.get(token.workflow_id)
        if workflow_tokens is None:
            return None
        return workflow_tokens.get(token.operation_id)


__all__ = [
    "EditorBusyControllerProtocol",
    "EditorBusyCoordinator",
    "EditorBusyDownloadState",
    "EditorBusyToken",
]
