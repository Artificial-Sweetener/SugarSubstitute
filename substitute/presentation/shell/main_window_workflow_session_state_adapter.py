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

"""Adapt MainWindow session state to its workflow surface port."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast


from substitute.shared.logging.logger import (
    get_logger,
)

_LOGGER = get_logger("presentation.shell.main_window_workflow_session_state_adapter")
_RECONCILER_LOGGER = get_logger("presentation.shell.workflow_surface_reconciler")


class MainWindowWorkflowSessionStateAdapter:
    """Expose workflow session state through a read-only port."""

    def __init__(self, shell: object) -> None:
        """Store the shell object behind a session state API."""

        self._shell = shell

    @property
    def active_workflow_id(self) -> str:
        """Return the workflow session's active workflow id."""

        session = getattr(self._shell, "workflow_session_service", None)
        return str(getattr(session, "active_workflow_id", ""))

    @property
    def workflows(self) -> Mapping[str, object]:
        """Return workflow state by id."""

        session = getattr(self._shell, "workflow_session_service", None)
        return cast(Mapping[str, object], getattr(session, "workflows", {}))
