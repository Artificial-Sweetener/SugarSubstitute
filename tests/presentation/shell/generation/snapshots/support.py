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

"""Shared helpers for WorkspaceController generation tests."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.generation import SeedRandomizationResult, SeedValueChange


class SeedRandomizationRecorder:
    """Record model-owned seed randomization in controller tests."""

    def __init__(
        self,
        order: list[str],
        *,
        mutate: object | None = None,
        value: object | None = None,
    ) -> None:
        """Store call ordering and optional workflow mutation."""

        self._order = order
        self._mutate = mutate
        self._value = value

    def randomize_workflow_seeds(self, **_kwargs: object) -> SeedRandomizationResult:
        """Record one model randomization call and mutate test workflow state."""

        self._order.append("randomize")
        if self._mutate is not None:
            setattr(self._mutate, "seed", self._value)
        return SeedRandomizationResult(
            (SeedValueChange(value=1, previous_value=0, override_key="seed"),)
        )


def replace_seed_randomizer(
    controller: object,
    recorder: SeedRandomizationRecorder,
) -> None:
    """Install a recording seed randomizer on a controller collaborator bundle."""

    controller._collaborators = replace(  # type: ignore[attr-defined]
        controller._collaborators,  # type: ignore[attr-defined]
        generation_seed_randomizer=lambda *, request, behavior_snapshot: (
            recorder.randomize_workflow_seeds(
                request=request,
                behavior_snapshot=behavior_snapshot,
            )
        ),
    )
