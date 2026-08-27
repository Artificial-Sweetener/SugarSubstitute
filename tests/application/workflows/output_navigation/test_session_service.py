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

"""Contract tests for generation-scoped Output navigation ownership."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.domain.workflow import OutputFocusMode, WorkflowState


def test_new_session_defers_automatic_projection_until_content_is_presentable() -> None:
    """Keep the prior visible route stable while recording automatic intent."""

    workflow = WorkflowState(
        output_focus_mode=OutputFocusMode.MANUAL,
        active_output_uuid=uuid4(),
        active_output_source_key="wf:inspected",
        active_output_set_index=0,
    )
    service = OutputNavigationSessionService()

    started = service.begin_session({"wf": workflow}, "wf", "session-2")

    assert started is not None
    assert started.session_id == "session-2"
    assert started.focus_mode is OutputFocusMode.AUTOMATIC
    assert started.content_presented is False
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_source_key == "wf:inspected"
    assert workflow.active_output_set_index == 0

    presented = service.present_session_content(
        {"wf": workflow},
        "wf",
        "session-2",
    )

    assert presented is not None
    assert presented.content_presented is True
    assert workflow.output_focus_mode.value == OutputFocusMode.AUTOMATIC.value


def test_same_session_start_does_not_reset_manual_navigation() -> None:
    """Treat later scene jobs sharing one session id as the same navigation session."""

    workflow = WorkflowState()
    service = OutputNavigationSessionService()
    service.begin_session({"wf": workflow}, "wf", "scene-run")
    service.present_session_content({"wf": workflow}, "wf", "scene-run")
    service.mark_user_navigation("wf", workflow)

    repeated = service.begin_session({"wf": workflow}, "wf", "scene-run")

    assert repeated is not None
    assert repeated.focus_mode is OutputFocusMode.MANUAL
    assert repeated.content_presented is True
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL


def test_next_session_resets_manual_navigation_when_first_content_is_presented() -> (
    None
):
    """Reset manual intent exactly once when the next session becomes presentable."""

    workflow = WorkflowState()
    service = OutputNavigationSessionService()
    service.begin_session({"wf": workflow}, "wf", "session-1")
    service.present_session_content({"wf": workflow}, "wf", "session-1")
    service.mark_user_navigation("wf", workflow)

    service.begin_session({"wf": workflow}, "wf", "session-2")
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    service.present_session_content({"wf": workflow}, "wf", "session-2")

    assert workflow.output_focus_mode.value == OutputFocusMode.AUTOMATIC.value


def test_user_navigation_before_first_content_does_not_override_session_reset() -> None:
    """Treat pre-result navigation as inspection of the prior session's content."""

    workflow = WorkflowState(output_focus_mode=OutputFocusMode.MANUAL)
    service = OutputNavigationSessionService()
    service.begin_session({"wf": workflow}, "wf", "session-2")

    pending = service.mark_user_navigation("wf", workflow)

    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert pending is not None
    assert pending.focus_mode is OutputFocusMode.AUTOMATIC
    assert pending.content_presented is False

    presented = service.present_session_content({"wf": workflow}, "wf", "session-2")

    assert workflow.output_focus_mode.value == OutputFocusMode.AUTOMATIC.value
    assert presented is not None
    assert presented.focus_mode is OutputFocusMode.AUTOMATIC
    assert presented.content_presented is True


def test_unannounced_presentable_session_is_adopted_automatically() -> None:
    """Recover automatic session state when host feedback omitted run-start ingress."""

    workflow = WorkflowState(output_focus_mode=OutputFocusMode.MANUAL)
    service = OutputNavigationSessionService()

    state = service.present_session_content(
        {"wf": workflow},
        "wf",
        "generation-run",
    )

    assert state is not None
    assert state.session_id == "generation-run"
    assert state.focus_mode is OutputFocusMode.AUTOMATIC
    assert state.content_presented is True
    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC
