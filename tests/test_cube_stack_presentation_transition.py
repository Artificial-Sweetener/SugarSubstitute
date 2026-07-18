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

"""Verify the typed retargetable cube-stack presentation animator."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPresentationFrame,
    CubeStackPresentationMode,
)
from substitute.presentation.shell.cube_stack_presentation_transition import (
    CubeStackPresentationTransition,
)


def _ensure_application() -> QApplication:
    """Return the process Qt application required by property animation."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def test_immediate_transition_applies_exact_target_and_completion_identity() -> None:
    """Non-animated projection should still use the production completion contract."""

    _ensure_application()
    current = CubeStackPresentationFrame(240, 212, 0.0, 0.0, 0.0)
    applied: list[CubeStackPresentationFrame] = []
    completed: list[tuple[object, int]] = []

    def apply(frame: CubeStackPresentationFrame) -> None:
        """Record and expose the current frame."""

        nonlocal current
        current = frame
        applied.append(frame)

    transition = CubeStackPresentationTransition(
        read_frame=lambda: current,
        apply_frame=apply,
    )
    transition.transitionFinished.connect(
        lambda mode, generation: completed.append((mode, generation))
    )
    target = CubeStackPresentationFrame(0, 44, 1.0, 1.0, 1.0)

    generation = transition.transition_to(
        CubeStackPresentationMode.UNAVAILABLE,
        target,
        animated=False,
    )

    assert current == target
    assert applied[-1] == target
    assert completed == [(CubeStackPresentationMode.UNAVAILABLE, generation)]
    assert not transition.is_animating


def test_retarget_starts_from_live_intermediate_frame_without_delta_drift() -> None:
    """A reversal should use the rendered frame rather than either stale endpoint."""

    _ensure_application()
    expanded = CubeStackPresentationFrame(240, 212, 0.0, 0.0, 0.0)
    hidden = CubeStackPresentationFrame(0, 44, 1.0, 1.0, 1.0)
    current = expanded
    applied: list[CubeStackPresentationFrame] = []

    def apply(frame: CubeStackPresentationFrame) -> None:
        """Record and expose the current frame."""

        nonlocal current
        current = frame
        applied.append(frame)

    transition = CubeStackPresentationTransition(
        read_frame=lambda: current,
        apply_frame=apply,
        duration_resolver=lambda _duration: 60_000,
    )

    first_generation = transition.transition_to(
        CubeStackPresentationMode.UNAVAILABLE,
        hidden,
    )
    transition.setProgress(0.5)
    midpoint = current
    second_generation = transition.transition_to(
        CubeStackPresentationMode.EXPANDED,
        expanded,
    )
    transition.setProgress(0.5)

    assert midpoint == CubeStackPresentationFrame(120, 128, 0.5, 0.5, 0.5)
    assert applied[-1] == CubeStackPresentationFrame(180, 170, 0.25, 0.25, 0.25)
    assert second_generation > first_generation
    assert transition.active_generation == second_generation
    transition.stop()
