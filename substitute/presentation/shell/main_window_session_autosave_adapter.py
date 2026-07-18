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

"""Adapt MainWindow autosave requests to the workflow session port."""

from __future__ import annotations


from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)
from substitute.shared.logging.logger import (
    get_logger,
)

_LOGGER = get_logger("presentation.shell.main_window_session_autosave_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowSessionAutosaveAdapter:
    """Expose session autosave coordinator through a narrow port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind an autosave API."""

        self._shell = shell

    def request(self, category: SessionAutosaveRequestCategory) -> None:
        """Request debounced autosave for an interaction category."""

        controller = getattr(self._shell, "session_autosave_controller", None)
        request = getattr(controller, "request_categorized_session_autosave", None)
        if callable(request):
            request(category)
            return
        request_session_autosave = getattr(
            self._shell, "request_session_autosave", None
        )
        if callable(request_session_autosave):
            request_session_autosave()

    def flush(self, category: SessionAutosaveRequestCategory) -> None:
        """Flush one autosave category immediately when supported."""

        coordinator = getattr(self._shell, "_session_autosave_coordinator", None)
        flush = getattr(coordinator, "flush", None)
        if callable(flush):
            flush(category)
            return
        request_session_autosave = getattr(
            self._shell, "request_session_autosave", None
        )
        if callable(request_session_autosave):
            request_session_autosave()


__all__ = ["MainWindowSessionAutosaveAdapter"]
