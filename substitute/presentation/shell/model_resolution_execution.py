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

"""Define shared runtime routes for workflow model resolution and download."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.execution import TaskSubmitter


class ExecutionCallbackDispatcher(Protocol):
    """Dispatch progress callbacks through the owning Qt boundary."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Publish one callback to its owner thread."""


@dataclass(frozen=True, slots=True)
class ModelResolutionRoute:
    """Carry an execution route for pre-materialization model resolution."""

    submitter: TaskSubmitter
    close: Callable[[], None]


class ModelResolutionRouteFactory(Protocol):
    """Create a model-resolution route for one workflow request."""

    def __call__(
        self,
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> ModelResolutionRoute:
        """Return a route owned by the specified workflow request."""


@dataclass(frozen=True, slots=True)
class ModelDownloadRoute:
    """Carry execution and progress routes for verified model downloads."""

    submitter: TaskSubmitter
    progress_dispatcher: ExecutionCallbackDispatcher
    close: Callable[[], None]


class ModelDownloadRouteFactory(Protocol):
    """Create a verified-download route for one workflow request."""

    def __call__(
        self,
        *,
        request_id: int,
        target_workflow_id: str,
    ) -> ModelDownloadRoute:
        """Return a route owned by the specified workflow request."""


__all__ = [
    "ExecutionCallbackDispatcher",
    "ModelDownloadRoute",
    "ModelDownloadRouteFactory",
    "ModelResolutionRoute",
    "ModelResolutionRouteFactory",
]
