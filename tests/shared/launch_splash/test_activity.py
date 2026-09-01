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

"""Prove the shared splash activity timing and animation policy."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.launch_splash import (
    SplashActivity,
    SplashActivityStage,
    render_splash_activity,
    splash_activity_stage,
)

_ACTIVITY = SplashActivity(
    initial_text="Updating SugarCubes",
    long_wait_text="Updating SugarCubes is taking longer than usual",
    extended_wait_text="Still updating SugarCubes—network may be slow",
)


@pytest.mark.parametrize(
    ("elapsed_seconds", "expected_stage", "expected_text"),
    (
        (0.0, SplashActivityStage.INITIAL, "Updating SugarCubes."),
        (1.0, SplashActivityStage.INITIAL, "Updating SugarCubes.."),
        (2.0, SplashActivityStage.INITIAL, "Updating SugarCubes..."),
        (
            120.0,
            SplashActivityStage.LONG_WAIT,
            "Updating SugarCubes is taking longer than usual.",
        ),
        (
            121.0,
            SplashActivityStage.LONG_WAIT,
            "Updating SugarCubes is taking longer than usual..",
        ),
        (
            122.0,
            SplashActivityStage.LONG_WAIT,
            "Updating SugarCubes is taking longer than usual...",
        ),
        (
            300.0,
            SplashActivityStage.EXTENDED_WAIT,
            "Still updating SugarCubes—network may be slow.",
        ),
        (
            301.0,
            SplashActivityStage.EXTENDED_WAIT,
            "Still updating SugarCubes—network may be slow..",
        ),
        (
            302.0,
            SplashActivityStage.EXTENDED_WAIT,
            "Still updating SugarCubes—network may be slow...",
        ),
    ),
)
def test_splash_activity_cycles_dots_through_every_wait_stage(
    elapsed_seconds: float,
    expected_stage: SplashActivityStage,
    expected_text: str,
) -> None:
    """Keep visible motion before and after both long-wait transitions."""

    assert splash_activity_stage(elapsed_seconds) is expected_stage
    assert render_splash_activity(_ACTIVITY, elapsed_seconds) == expected_text


def test_splash_activity_clamps_negative_elapsed_time() -> None:
    """A clock adjustment should retain the first visible activity frame."""

    assert render_splash_activity(_ACTIVITY, -10.0) == "Updating SugarCubes."
