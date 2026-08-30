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

"""Contract tests for workflow surface refresh scheduling."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.workflow_surface_refresh_scheduler import (
    WorkflowSurfaceRefreshScheduler,
)


def test_scheduler_refreshes_latest_workflow_only() -> None:
    """Rapid workflow refresh requests should coalesce to the latest workflow."""

    _app()
    active_workflow_id = "wf-b"
    calls: list[tuple[str, bool]] = []

    scheduler = WorkflowSurfaceRefreshScheduler(
        active_workflow_id=lambda: active_workflow_id,
        refresh_surface=lambda workflow_id, force_refresh, _on_complete: calls.append(
            (workflow_id, force_refresh)
        ),
    )

    scheduler.request("wf-a", force_refresh=False, reason="workflow_tab")
    scheduler.request("wf-b", force_refresh=True, reason="workflow_tab")
    scheduler.flush()

    assert calls == [("wf-b", True)]


def test_scheduler_skips_stale_workflow_refresh() -> None:
    """A pending refresh should not run after another workflow becomes active."""

    _app()
    active_workflow_id = "wf-b"
    calls: list[str] = []

    scheduler = WorkflowSurfaceRefreshScheduler(
        active_workflow_id=lambda: active_workflow_id,
        refresh_surface=lambda workflow_id, _force_refresh, _on_complete: calls.append(
            workflow_id
        ),
    )

    scheduler.request("wf-a", force_refresh=False, reason="workflow_tab")
    scheduler.flush()

    assert calls == []


def test_scheduler_forwards_completion_callback_for_current_refresh() -> None:
    """Current refreshes should preserve completion callback ownership."""

    _app()
    completions: list[str] = []

    def refresh_surface(
        _workflow_id: str,
        _force_refresh: bool,
        on_complete: object,
    ) -> None:
        """Run the provided completion callback."""

        if callable(on_complete):
            on_complete()

    scheduler = WorkflowSurfaceRefreshScheduler(
        active_workflow_id=lambda: "wf-a",
        refresh_surface=refresh_surface,
    )

    scheduler.request(
        "wf-a",
        force_refresh=False,
        reason="workspace_projection",
        on_complete=lambda: completions.append("done"),
    )
    scheduler.flush()

    assert completions == ["done"]


def _app() -> QApplication:
    """Return a QApplication for QTimer-backed scheduler tests."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
