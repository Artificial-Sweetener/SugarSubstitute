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

"""Tests for workspace cube action execution ownership."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

from tests.execution_testing import QueuedTaskSubmitter
from substitute.application.ports import CubeCatalogSnapshot
from substitute.presentation.shell.workspace_cube_picker_actions import (
    CatalogRefreshRoute,
    WorkspaceCubePickerActionView,
    WorkspaceCubePickerActions,
)


def test_catalog_refresh_uses_injected_route_and_cancels_on_shutdown() -> None:
    """Background catalog refresh should use an injected scoped execution route."""

    submitter = QueuedTaskSubmitter()
    close_calls: list[str] = []
    view = cast(
        WorkspaceCubePickerActionView,
        SimpleNamespace(
            cube_load_service=SimpleNamespace(
                refresh_picker_catalog=lambda: CubeCatalogSnapshot(
                    entries=[],
                    state="fresh",
                )
            )
        ),
    )
    actions = WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        catalog_refresh_route_factory=lambda trace_id: CatalogRefreshRoute(
            submitter=submitter,
            close=lambda: close_calls.append(trace_id),
        ),
    )
    schedule_refresh = cast(
        Callable[[str], None],
        getattr(actions, "_schedule_catalog_refresh"),
    )

    schedule_refresh("trace-a")
    assert len(submitter.handles) == 1
    assert submitter.cancellations[0].is_cancelled is False
    assert submitter.handles[0].identity.domain == "cube_load"

    actions.shutdown()

    assert submitter.cancellations[0].is_cancelled is True
    assert submitter.cancellations[0].reason == (
        "workspace_cube_picker_actions_shutdown"
    )
    assert submitter.handles[0].cancel_reason == (
        "workspace_cube_picker_actions_shutdown"
    )
    assert close_calls == ["trace-a"]
