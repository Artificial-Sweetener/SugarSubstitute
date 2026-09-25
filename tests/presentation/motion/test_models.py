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

from substitute.presentation.motion import (
    FLUENT_ENTRANCE_EASING_CURVE,
    FLUENT_EXIT_EASING_CURVE,
    FLUENT_FAST_DURATION_MS,
    FLUENT_FASTER_DURATION_MS,
    FLUENT_NORMAL_DURATION_MS,
    FLUENT_POINT_TO_POINT_EASING_CURVE,
)
from substitute.presentation.motion.models import (
    MotionPlan,
    MotionSpec,
    MotionTarget,
    interpolate_target,
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
            start_rect=QRectF(),
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


def test_interpolate_target_blends_geometry_and_opacity() -> None:
    """Structural targets should follow one continuous before/after path."""

    ensure_qapplication()
    target = MotionTarget(
        identity="cube:A",
        start_rect=QRectF(10.0, 20.0, 100.0, 40.0),
        final_rect=QRectF(30.0, 60.0, 140.0, 60.0),
        snapshot=QPixmap(),
        start_opacity=0.25,
        final_opacity=1.0,
    )

    frame = interpolate_target(target, progress=0.5)

    assert frame.rect == QRectF(20.0, 40.0, 120.0, 50.0)
    assert frame.opacity == pytest.approx(0.625)


def test_structural_motion_uses_windows_fluent_timing_tokens() -> None:
    """Shared tokens should encode Microsoft's fast, normal, and easing guidance."""

    assert FLUENT_FASTER_DURATION_MS == 83
    assert FLUENT_FAST_DURATION_MS == 167
    assert FLUENT_NORMAL_DURATION_MS == 250
    assert FLUENT_ENTRANCE_EASING_CURVE.valueForProgress(0.5) > 0.8
    assert FLUENT_EXIT_EASING_CURVE.valueForProgress(0.5) < 0.2
    midpoint = FLUENT_POINT_TO_POINT_EASING_CURVE.valueForProgress(0.5)
    assert 0.9 < midpoint < 0.95


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
