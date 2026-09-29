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

"""Test motion decoration around visible editor projection publication."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.presentation.editor.panel.projection_reveal_motion import (
    AnimatedProjectionReveal,
)
from substitute.presentation.editor.panel.rendering.render_reconciler import (
    ProjectedCubeBuildProtocol,
)


class _Reconciler:
    """Record the functional projection commit."""

    def __init__(self, events: list[object]) -> None:
        """Store the shared event ledger."""

        self._events = events

    def reveal_projected_cube_builds(
        self,
        projected_builds: Sequence[ProjectedCubeBuildProtocol],
        *,
        workflow_id: str,
    ) -> None:
        """Record publication between visual preparation and presentation."""

        self._events.append(("commit", len(projected_builds), workflow_id))


class _Motion:
    """Record the cosmetic transition boundaries."""

    def __init__(self, events: list[object]) -> None:
        """Store the shared event ledger."""

        self._events = events

    def prepare_projection_reveal(self) -> int:
        """Record pre-commit capture and return one generation."""

        self._events.append("prepare")
        return 9

    def present_projection_reveal(self, generation: int | None) -> bool:
        """Record post-commit presentation of the prepared generation."""

        self._events.append(("present", generation))
        return True


def test_animated_projection_reveal_surrounds_functional_commit() -> None:
    """Visible builds should commit between motion preparation and presentation."""

    events: list[object] = []
    reveal = AnimatedProjectionReveal(
        reconciler=_Reconciler(events),
        motion=_Motion(events),
    )

    reveal.reveal((), "workflow")

    assert events == ["prepare", ("commit", 0, "workflow"), ("present", 9)]
