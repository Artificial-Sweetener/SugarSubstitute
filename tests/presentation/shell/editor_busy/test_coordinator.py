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

"""Contract tests for workflow-scoped editor busy coordination."""

from __future__ import annotations

from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyCoordinator,
    EditorBusyToken,
)


class _Overlay:
    """Capture overlay projection calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def show_loading(self, message: str = "Loading") -> None:
        """Record a show request."""

        self.calls.append(("show", message))

    def hide_loading(self) -> None:
        """Record a hide request."""

        self.calls.append(("hide", None))

    def show_download_progress(
        self,
        *,
        title: str,
        message: str,
        detail: str,
        progress_per_mille: int | None,
        cancel_enabled: bool = True,
    ) -> None:
        """Record a download-progress request."""

        _ = detail, progress_per_mille, cancel_enabled
        self.calls.append(("download", f"{title}: {message}"))


def test_busy_coordinator_keeps_overlay_until_all_active_tokens_end() -> None:
    """Multiple operations in one workflow should keep the overlay visible."""

    active_workflow_id = "wf-a"
    overlay = _Overlay()
    coordinator = EditorBusyCoordinator(
        active_workflow_id=lambda: active_workflow_id,
        is_editor_surface_active=lambda: True,
        overlay=overlay,
    )

    first = coordinator.begin("wf-a", message="Loading")
    second = coordinator.begin("wf-a", message="Loading")
    coordinator.end(first)
    coordinator.end(second)

    assert overlay.calls == [
        ("show", "Loading"),
        ("show", "Loading"),
        ("show", "Loading"),
        ("hide", None),
    ]


def test_busy_coordinator_projects_only_active_workflow_state() -> None:
    """Workflow switching should show busy state only for the active workflow."""

    active_workflow_id = "wf-a"
    overlay = _Overlay()
    coordinator = EditorBusyCoordinator(
        active_workflow_id=lambda: active_workflow_id,
        is_editor_surface_active=lambda: True,
        overlay=overlay,
    )

    coordinator.begin("wf-b", message="Loading")
    active_workflow_id = "wf-b"
    coordinator.refresh_active_surface()

    assert overlay.calls == [("hide", None), ("show", "Loading")]


def test_busy_coordinator_ignores_unknown_tokens() -> None:
    """Ending an unknown token should not disturb current active busy state."""

    overlay = _Overlay()
    coordinator = EditorBusyCoordinator(
        active_workflow_id=lambda: "wf-a",
        is_editor_surface_active=lambda: True,
        overlay=overlay,
    )

    coordinator.begin("wf-a", message="Loading")
    coordinator.end(EditorBusyToken(workflow_id="wf-a", operation_id="missing"))

    assert overlay.calls == [("show", "Loading")]
    assert coordinator.has_pending_workflow("wf-a") is True


def test_busy_coordinator_hides_pending_work_outside_editor_route() -> None:
    """Settings should suppress editor presentation without discarding pending work."""

    editor_surface_active = True
    overlay = _Overlay()
    coordinator = EditorBusyCoordinator(
        active_workflow_id=lambda: "wf-a",
        is_editor_surface_active=lambda: editor_surface_active,
        overlay=overlay,
    )

    coordinator.begin("wf-a", message="Loading")
    editor_surface_active = False
    coordinator.refresh_active_surface()

    assert overlay.calls == [("show", "Loading"), ("hide", None)]
    assert coordinator.has_pending_workflow("wf-a") is True


def test_busy_coordinator_shutdown_clears_state_and_overlay() -> None:
    """Shell disposal should synchronously release application-wide busy presentation."""

    overlay = _Overlay()
    coordinator = EditorBusyCoordinator(
        active_workflow_id=lambda: "wf-a",
        is_editor_surface_active=lambda: True,
        overlay=overlay,
    )

    coordinator.begin("wf-a", message="Loading")
    coordinator.shutdown()
    coordinator.shutdown()

    assert overlay.calls == [("show", "Loading"), ("hide", None)]
    assert coordinator.has_pending_workflow("wf-a") is False
