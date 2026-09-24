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

"""Compose the Output action facade shared by real-shell test harnesses."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.shell.workspace_canvas_actions import (
    WorkspaceCanvasActions,
)
from substitute.presentation.shell.workspace_output_external_actions import (
    WorkspaceOutputExternalActions,
)
from substitute.presentation.shell.workspace_output_navigation_actions import (
    WorkspaceOutputNavigationActions,
    WorkspaceOutputNavigationView,
)
from substitute.presentation.shell.workspace_output_preparation_actions import (
    OutputPreparationErrorPresenterProtocol,
    WorkspaceOutputPreparationActions,
)


@dataclass(frozen=True, slots=True)
class WorkspaceOutputActionHarness:
    """Expose pre-workspace Output action adapters for one test shell."""

    canvas_actions: WorkspaceCanvasActions
    preparation_actions: WorkspaceOutputPreparationActions
    external_actions: WorkspaceOutputExternalActions


@dataclass(frozen=True, slots=True)
class WorkspaceOutputControllerHarness:
    """Expose navigation actions and their production-shaped facade."""

    navigation_actions: WorkspaceOutputNavigationActions
    controller: SimpleNamespace


def compose_workspace_output_actions(
    view: object,
    *,
    error_presenter: OutputPreparationErrorPresenterProtocol,
) -> WorkspaceOutputActionHarness:
    """Build the Output adapters required before workspace composition."""

    action_view = cast(Any, view)
    return WorkspaceOutputActionHarness(
        canvas_actions=WorkspaceCanvasActions(action_view),
        preparation_actions=WorkspaceOutputPreparationActions(
            action_view,
            error_presenter=error_presenter,
        ),
        external_actions=WorkspaceOutputExternalActions(action_view),
    )


def compose_workspace_output_controller(
    view: object,
    *,
    actions: WorkspaceOutputActionHarness,
) -> WorkspaceOutputControllerHarness:
    """Build one coherent Output action facade for a mounted test shell."""

    navigation_actions = WorkspaceOutputNavigationActions(
        cast(WorkspaceOutputNavigationView, view)
    )
    return WorkspaceOutputControllerHarness(
        navigation_actions=navigation_actions,
        controller=SimpleNamespace(
            output_navigation_actions=navigation_actions,
            output_external_actions=actions.external_actions,
            output_preparation_actions=actions.preparation_actions,
        ),
    )


__all__ = [
    "WorkspaceOutputActionHarness",
    "WorkspaceOutputControllerHarness",
    "compose_workspace_output_actions",
    "compose_workspace_output_controller",
]
