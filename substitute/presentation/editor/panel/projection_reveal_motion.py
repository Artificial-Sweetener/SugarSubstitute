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

"""Surround visible projection publication with optional structural motion."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .rendering.render_reconciler import ProjectedCubeBuildProtocol


class ProjectionRevealMotionPort(Protocol):
    """Describe motion around visible projection publication."""

    def prepare_projection_reveal(self) -> int | None:
        """Capture visible cubes before publication."""

    def present_projection_reveal(self, generation: int | None) -> bool:
        """Present newly published cubes above committed pixels."""


class ProjectionRevealReconcilerPort(Protocol):
    """Describe the functional publication owned by render reconciliation."""

    def reveal_projected_cube_builds(
        self,
        projected_builds: Sequence[ProjectedCubeBuildProtocol],
        *,
        workflow_id: str,
    ) -> None:
        """Publish completed cube builds to the committed editor layout."""


class AnimatedProjectionReveal:
    """Decorate functional projection publication with non-blocking motion."""

    def __init__(
        self,
        *,
        reconciler: ProjectionRevealReconcilerPort,
        motion: ProjectionRevealMotionPort,
    ) -> None:
        """Store narrow functional and cosmetic collaborators."""

        self._reconciler = reconciler
        self._motion = motion

    def reveal(
        self,
        projected_builds: Sequence[ProjectedCubeBuildProtocol],
        workflow_id: str,
    ) -> None:
        """Commit projected builds between motion preparation and presentation."""

        generation = self._motion.prepare_projection_reveal()
        self._reconciler.reveal_projected_cube_builds(
            projected_builds,
            workflow_id=workflow_id,
        )
        self._motion.present_projection_reveal(generation)


__all__ = [
    "AnimatedProjectionReveal",
    "ProjectionRevealMotionPort",
    "ProjectionRevealReconcilerPort",
]
