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

"""Tests for shared post-addition cube surface projection."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.shell.cube_surface_projection_coordinator import (
    CubeSurfaceProjectionCoordinator,
)


class _SurfaceActions:
    """Capture incremental refresh and activation requests."""

    def __init__(self, refreshed: bool) -> None:
        """Store the incremental result returned to the coordinator."""

        self.refreshed = refreshed
        self.calls: list[tuple[str, object]] = []

    def refresh_loaded_cube_surface_async(
        self,
        workflow_id: str,
        cube_alias: str,
        on_complete: Callable[[bool], None],
        *,
        wait_for_complete: bool = False,
    ) -> None:
        """Return the configured incremental result immediately."""

        self.calls.append(("refresh", (workflow_id, cube_alias, wait_for_complete)))
        on_complete(self.refreshed)

    def activate_loaded_cube(self, workflow_id: str, cube_alias: str) -> None:
        """Capture final cube activation."""

        self.calls.append(("activate", (workflow_id, cube_alias)))


class _Refresher:
    """Capture structural fallback refreshes."""

    def __init__(self) -> None:
        """Initialize fallback call capture."""

        self.calls: list[bool] = []

    def refresh_active_workflow_surface(
        self,
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Capture fallback state and complete immediately."""

        self.calls.append(force_refresh)
        if on_complete is not None:
            on_complete()


def test_projection_materializes_and_activates_after_incremental_insert() -> None:
    """Successful incremental insertion should avoid structural fallback."""

    surfaces = _SurfaceActions(refreshed=True)
    refresher = _Refresher()
    materialized: list[tuple[str, str]] = []
    completed: list[bool] = []
    coordinator = CubeSurfaceProjectionCoordinator(
        surface_actions=surfaces,
        active_surface_refresher=refresher,
        materialize_input_canvas=lambda workflow_id, alias: materialized.append(
            (workflow_id, alias)
        ),
    )

    coordinator.project_added_cube(
        "wf-a",
        "Cube 2",
        on_complete=lambda: completed.append(True),
    )

    assert surfaces.calls == [
        ("refresh", ("wf-a", "Cube 2", True)),
        ("activate", ("wf-a", "Cube 2")),
    ]
    assert refresher.calls == []
    assert materialized == [("wf-a", "Cube 2")]
    assert completed == [True]


def test_projection_uses_structural_fallback_before_materialization() -> None:
    """Unavailable incremental insertion should recover through full refresh."""

    surfaces = _SurfaceActions(refreshed=False)
    refresher = _Refresher()
    materialized: list[tuple[str, str]] = []
    coordinator = CubeSurfaceProjectionCoordinator(
        surface_actions=surfaces,
        active_surface_refresher=refresher,
        materialize_input_canvas=lambda workflow_id, alias: materialized.append(
            (workflow_id, alias)
        ),
    )

    coordinator.project_added_cube("wf-a", "Cube 2")

    assert refresher.calls == [True]
    assert materialized == [("wf-a", "Cube 2")]
    assert surfaces.calls[-1] == ("activate", ("wf-a", "Cube 2"))
