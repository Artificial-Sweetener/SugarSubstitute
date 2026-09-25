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

"""Test deterministic shared motion plan calculations."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap

from substitute.presentation.motion.models import (
    MotionPlan,
    MotionSpec,
    MotionTarget,
    motion_duration_ms,
    target_progress,
)
from tools.editor_projection_rig.qt_harness import ensure_qapplication


def test_target_progress_respects_stagger_and_clamps() -> None:
    """Target progress should remain bounded around its shared delay."""

    spec = MotionSpec(duration_ms=100, stagger_ms=20)

    assert target_progress(elapsed_ms=19, target_order=1, spec=spec) == 0.0
    assert target_progress(elapsed_ms=70, target_order=1, spec=spec) == 0.5
    assert target_progress(elapsed_ms=200, target_order=1, spec=spec) == 1.0


def test_motion_duration_includes_only_last_target_stagger() -> None:
    """One timeline should cover duration plus the latest target delay."""

    ensure_qapplication()
    spec = MotionSpec(duration_ms=180, stagger_ms=15)
    targets = tuple(
        MotionTarget(
            identity=str(index),
            final_rect=QRectF(),
            snapshot=QPixmap(),
            order=index,
        )
        for index in range(3)
    )
    plan = MotionPlan(
        generation=1,
        reason="insert",
        background=QPixmap(),
        viewport_rect=QRectF(),
        targets=targets,
        spec=spec,
    )

    assert motion_duration_ms(plan) == 210


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"duration_ms": -1}, "duration"),
        ({"stagger_ms": -1}, "stagger"),
        ({"start_opacity": 1.1}, "opacity"),
    ],
)
def test_motion_spec_rejects_invalid_values(
    kwargs: dict[str, object],
    message: str,
) -> None:
    """Invalid motion values should fail at the immutable policy boundary."""

    with pytest.raises(ValueError, match=message):
        MotionSpec(**kwargs)  # type: ignore[arg-type]
