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

"""Contract tests for shell session autosave lifecycle policy."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

from substitute.presentation.shell.session_autosave_controller import (
    SessionAutosaveController,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)


def test_force_save_is_muted_during_restore_lifecycle() -> None:
    """Forced session saves should not persist placeholder restore state."""

    calls: list[str] = []

    def force_save(_port: object) -> bool:
        """Record an unexpected forced save."""

        calls.append("force_save")
        return True

    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _shell_restore_lifecycle="prehydrating",
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": object()},
        ),
        session_autosave_service=SimpleNamespace(force_save=force_save),
    )
    controller = SessionAutosaveController(shell)

    result = controller.force_save_session_snapshot()

    assert result is False
    assert calls == []


def test_request_autosave_skips_until_initial_workspace_hydrates() -> None:
    """Autosave requests before hydration should not call persistence."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _initial_workspace_hydrated=False,
        _shell_restore_lifecycle="running",
        session_autosave_service=SimpleNamespace(
            request_save=lambda _port: calls.append("request")
        ),
    )
    controller = SessionAutosaveController(shell)

    controller.request_session_autosave()

    assert calls == []


def test_request_autosave_is_muted_during_restore_lifecycle() -> None:
    """Autosave requests during restore should not persist placeholder layout state."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _initial_workspace_hydrated=True,
        _shell_restore_lifecycle="restoring",
        session_autosave_service=SimpleNamespace(
            request_save=lambda _port: calls.append("request")
        ),
    )
    controller = SessionAutosaveController(shell)

    controller.request_session_autosave()

    assert calls == []


def test_request_autosave_marks_first_unmuted_once_and_enqueues() -> None:
    """The first unmuted autosave should mark startup once and request persistence."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _initial_workspace_hydrated=True,
        _shell_restore_lifecycle="running",
        _startup_autosave_unmuted_marked=False,
        session_autosave_service=SimpleNamespace(
            request_save=lambda _port: calls.append("request")
        ),
    )
    controller = SessionAutosaveController(shell)

    controller.request_session_autosave()
    controller.request_session_autosave()

    assert shell._startup_autosave_unmuted_marked is True
    assert calls == ["request", "request"]


def test_categorized_autosave_routes_through_existing_coordinator() -> None:
    """Categorized autosave should use the composed debounce coordinator."""

    categories: list[SessionAutosaveRequestCategory] = []
    shell = SimpleNamespace(
        _session_autosave_coordinator=SimpleNamespace(request=categories.append),
        _initial_workspace_hydrated=True,
        _shell_restore_lifecycle="running",
    )
    controller = SessionAutosaveController(shell)

    controller.request_categorized_session_autosave(
        SessionAutosaveRequestCategory.CANVAS_SELECTION
    )

    assert categories == [SessionAutosaveRequestCategory.CANVAS_SELECTION]


def test_canvas_layout_autosave_uses_resize_category() -> None:
    """Floating canvas layout changes should use the debounced resize lane."""

    callbacks: list[Callable[[], None]] = []
    categories: list[SessionAutosaveRequestCategory] = []
    shell = SimpleNamespace(
        canvas_tabs=SimpleNamespace(
            layout_state_changed=SimpleNamespace(connect=callbacks.append),
        ),
        _session_autosave_coordinator=SimpleNamespace(request=categories.append),
    )
    controller = SessionAutosaveController(shell)

    controller.connect_canvas_layout_autosave()
    callback = callbacks[0]
    assert callable(callback)
    callback()

    assert categories == [SessionAutosaveRequestCategory.LAYOUT_RESIZE]
