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

"""Adapt the active shell to the terminal session-finalization use case."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from substitute.application.execution import TaskHandle
from substitute.application.workspace_state import (
    PreparedSessionSave,
    SessionFinalizationReason,
    SessionSaveResult,
)


class SessionFinalizationControllerProtocol(Protocol):
    """Describe terminal persistence exposed by one live shell controller."""

    def prepare_session_finalization(
        self,
        reason: SessionFinalizationReason,
    ) -> PreparedSessionSave:
        """Capture one terminal session save without file I/O."""

    def begin_session_finalization(
        self,
        reason: SessionFinalizationReason,
    ) -> TaskHandle[SessionSaveResult]:
        """Prepare and submit one terminal session save."""


class UnsavedWorkControllerProtocol(Protocol):
    """Authorize app shutdown after resolving dirty workflows."""

    def confirm_shutdown(self) -> bool:
        """Return whether shutdown may proceed."""


class ShellSessionFinalizationAdapter:
    """Resolve terminal persistence through the currently authoritative shell."""

    def __init__(
        self,
        *,
        current_shell: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
    ) -> None:
        """Store current-shell and main-window resolution ports."""

        self._current_shell = current_shell
        self._main_window_for_shell = main_window_for_shell

    def prepare_shutdown(self, source_shell: object | None) -> PreparedSessionSave:
        """Capture the exact source shell, falling back for app-level quit."""

        shell = source_shell if source_shell is not None else self._current_shell()
        if shell is None:
            raise RuntimeError("session finalization requires an active shell")
        controller = self._controller_for_shell(shell)
        return controller.prepare_session_finalization(
            SessionFinalizationReason.SHUTDOWN
        )

    def confirm_shutdown(self, source_shell: object | None) -> bool:
        """Resolve dirty workflows for window-close and external repair requests."""

        shell = source_shell if source_shell is not None else self._current_shell()
        if shell is None:
            return True
        main_window = self._main_window_for_shell(shell)
        if main_window is None:
            return True
        controller = getattr(main_window, "unsaved_work_controller", None)
        confirm = getattr(controller, "confirm_shutdown", None)
        if not callable(confirm):
            return True
        return bool(confirm())

    def begin_gui_reload(
        self,
        main_window: object,
    ) -> TaskHandle[SessionSaveResult]:
        """Begin detached persistence for one GUI reload source shell."""

        controller = self._controller_for_main_window(main_window)
        return controller.begin_session_finalization(
            SessionFinalizationReason.GUI_RELOAD
        )

    def _controller_for_shell(
        self,
        shell: object,
    ) -> SessionFinalizationControllerProtocol:
        """Resolve the finalization controller owned by one shell main window."""

        main_window = self._main_window_for_shell(shell)
        if main_window is None:
            raise RuntimeError("active shell has no session finalization main window")
        return self._controller_for_main_window(main_window)

    @staticmethod
    def _controller_for_main_window(
        main_window: object,
    ) -> SessionFinalizationControllerProtocol:
        """Validate and return one main window's finalization controller."""

        controller = getattr(main_window, "session_autosave_controller", None)
        prepare = getattr(controller, "prepare_session_finalization", None)
        begin = getattr(controller, "begin_session_finalization", None)
        if not callable(prepare) or not callable(begin):
            raise RuntimeError("session finalization controller is unavailable")
        return cast(SessionFinalizationControllerProtocol, controller)


__all__ = ["ShellSessionFinalizationAdapter"]
