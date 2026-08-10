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

"""Own generation-scoped automatic and manual Output navigation intent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from substitute.domain.workflow import OutputFocusMode, WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.workflows.output_navigation_session_service")


@dataclass(frozen=True, slots=True)
class OutputNavigationSessionState:
    """Describe navigation intent for one accepted generation session."""

    session_id: str
    focus_mode: OutputFocusMode
    content_presented: bool


class OutputNavigationSessionService:
    """Coordinate Output navigation mode across generation-session boundaries."""

    def __init__(self) -> None:
        """Initialize workflow-scoped live session state."""

        self._states: dict[str, OutputNavigationSessionState] = {}

    def begin_session(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        session_id: str,
    ) -> OutputNavigationSessionState | None:
        """Record automatic intent for a new session without rerouting old content."""

        if workflow_id not in workflows or not session_id:
            return None
        current = self._states.get(workflow_id)
        if current is not None and current.session_id == session_id:
            return current
        state = OutputNavigationSessionState(
            session_id=session_id,
            focus_mode=OutputFocusMode.AUTOMATIC,
            content_presented=False,
        )
        self._states[workflow_id] = state
        log_debug(
            _LOGGER,
            "Output navigation session began",
            workflow_id=workflow_id,
            output_session_id=session_id,
        )
        return state

    def present_session_content(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        session_id: str,
    ) -> OutputNavigationSessionState | None:
        """Activate session navigation mode when its first content is presentable."""

        workflow = workflows.get(workflow_id)
        if workflow is None or not session_id:
            return None
        current = self._states.get(workflow_id)
        if current is None or current.session_id != session_id:
            current = OutputNavigationSessionState(
                session_id=session_id,
                focus_mode=OutputFocusMode.AUTOMATIC,
                content_presented=False,
            )
        state = replace(current, content_presented=True)
        self._states[workflow_id] = state
        workflow.output_focus_mode = state.focus_mode
        log_debug(
            _LOGGER,
            "Output navigation session content presented",
            workflow_id=workflow_id,
            output_session_id=session_id,
            focus_mode=state.focus_mode.value,
        )
        return state

    def mark_user_navigation(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> OutputNavigationSessionState | None:
        """Make user-selected navigation sticky for the current session."""

        workflow.output_focus_mode = OutputFocusMode.MANUAL
        current = self._states.get(workflow_id)
        if current is None:
            return None
        state = replace(current, focus_mode=OutputFocusMode.MANUAL)
        self._states[workflow_id] = state
        log_debug(
            _LOGGER,
            "Output navigation session became manual",
            workflow_id=workflow_id,
            output_session_id=state.session_id,
        )
        return state

    def reset_workflow(self, workflow_id: str, workflow: WorkflowState) -> None:
        """Discard live session intent and restore default automatic navigation."""

        self._states.pop(workflow_id, None)
        workflow.output_focus_mode = OutputFocusMode.AUTOMATIC

    def discard_workflow(self, workflow_id: str) -> None:
        """Discard navigation session state for a closed workflow."""

        self._states.pop(workflow_id, None)

    def state_for(self, workflow_id: str) -> OutputNavigationSessionState | None:
        """Return live navigation session state for one workflow."""

        return self._states.get(workflow_id)


__all__ = ["OutputNavigationSessionService", "OutputNavigationSessionState"]
