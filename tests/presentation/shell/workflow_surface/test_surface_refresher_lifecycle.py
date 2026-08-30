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

"""Workflow surface refresher cache and stale-callback contracts."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
    active_workflow_surface_refresher_for,
)


def test_active_workflow_surface_refresher_for_reuses_composed_refresher() -> None:
    """Surface refresher composition should attach one owner to the shell."""

    view = SimpleNamespace()

    first = active_workflow_surface_refresher_for(view)
    second = active_workflow_surface_refresher_for(view)

    assert first is second
    assert view.active_workflow_surface_refresher is first


def test_detached_shell_ignores_stale_surface_refresh_callbacks() -> None:
    """Async cube callbacks should not refresh a shell detached for GUI reload."""

    shell = SimpleNamespace(
        _detached_for_gui_reload=True,
        get_active_workflow=lambda: (_ for _ in ()).throw(
            AssertionError("stale shell should not inspect workflow state")
        ),
    )

    ActiveWorkflowSurfaceRefresher(shell).refresh_active_workflow_surface()
