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

"""Verify typed setup progress rejects invented measurements."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.localization import app_text

from substitute.application.onboarding.setup_progress import (
    SetupProgressEvent,
    SetupProgressUnit,
    SetupTaskId,
    SetupTaskState,
)


def test_indeterminate_progress_cannot_claim_units() -> None:
    """Prevent phase-only work from presenting fabricated numeric precision."""

    with pytest.raises(ValueError, match="cannot declare units"):
        SetupProgressEvent(
            1,
            SetupTaskId.RUNTIME,
            SetupTaskState.RUNNING,
            app_text("Preparing runtime."),
            completed_units=1,
            total_units=2,
        )


def test_measured_progress_requires_monotonic_bounded_units() -> None:
    """Require exact transfer owners to provide coherent completed/total values."""

    event = SetupProgressEvent(
        2,
        SetupTaskId.MODEL_DOWNLOAD,
        SetupTaskState.RUNNING,
        app_text("Downloading model."),
        unit=SetupProgressUnit.BYTES,
        completed_units=50,
        total_units=100,
    )

    assert event.completed_units == 50
    assert event.monotonic_timestamp > 0
