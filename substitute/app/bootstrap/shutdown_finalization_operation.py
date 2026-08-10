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

"""Compose terminal session persistence with managed application cleanup."""

from __future__ import annotations

from collections.abc import Callable

from substitute.app.bootstrap.lifecycle import ManagedComfyCleanupResult
from substitute.application.workspace_state import (
    PreparedSessionSave,
    SessionSaveResult,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("app.bootstrap.shutdown_finalization_operation")


class ShutdownFinalizationOperation:
    """Prepare on the UI thread and finalize durably on the shutdown lane."""

    def __init__(
        self,
        *,
        prepare_session: Callable[[object | None], PreparedSessionSave],
        persist_session: Callable[[PreparedSessionSave], SessionSaveResult],
        cleanup_managed_comfy: Callable[[], ManagedComfyCleanupResult],
    ) -> None:
        """Store terminal collaborators with explicit thread-phase ownership."""

        self._prepare_session = prepare_session
        self._persist_session = persist_session
        self._cleanup_managed_comfy = cleanup_managed_comfy
        self._prepared: PreparedSessionSave | None = None
        self._preparation_error: Exception | None = None

    def prepare(self, source_shell: object | None) -> None:
        """Capture terminal authority from the shell requesting shutdown."""

        try:
            prepared = self._prepare_session(source_shell)
        except Exception as error:
            self._prepared = None
            self._preparation_error = error
            log_exception(
                _LOGGER,
                "Shutdown session finalization preparation failed",
                error=error,
            )
            return
        self._prepared = prepared
        self._preparation_error = None
        log_info(
            _LOGGER,
            "Shutdown session finalization prepared",
            workflow_count=len(prepared.snapshot.workspace.workflows),
            prerequisite_count=len(prepared.prerequisites),
        )

    def run(self) -> ManagedComfyCleanupResult:
        """Persist the prepared session before managed Comfy cleanup."""

        prepared = self._prepared
        preparation_error = self._preparation_error
        self._prepared = None
        self._preparation_error = None
        if preparation_error is not None:
            raise RuntimeError(
                "shutdown session preparation failed"
            ) from preparation_error
        if prepared is None:
            raise RuntimeError("shutdown session finalization was not prepared")
        result = self._persist_session(prepared)
        log_info(
            _LOGGER,
            "Shutdown session finalization persisted",
            elapsed_ms=result.elapsed_ms,
            workflow_count=result.workflow_count,
            prerequisite_count=result.prerequisite_count,
        )
        return self._cleanup_managed_comfy()


__all__ = ["ShutdownFinalizationOperation"]
