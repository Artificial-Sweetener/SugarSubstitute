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

"""Verify Output transfer feedback distinguishes cancellation from failure."""

from __future__ import annotations

from pytest import MonkeyPatch

from substitute.presentation.canvas.output.output_transfer_drag_provider import (
    OUTPUT_DRAG_GESTURE_ENDED_MESSAGE,
)
from substitute.presentation.canvas.output.output_transfer_failure_presenter import (
    OutputTransferFailurePresenter,
)


def test_ended_drag_gesture_does_not_show_failure_feedback(
    monkeypatch: MonkeyPatch,
) -> None:
    """Releasing before payload delivery is a quiet cancellation, not an error."""

    shown: list[object] = []
    monkeypatch.setattr(
        "substitute.presentation.canvas.output.output_transfer_failure_presenter.InfoBar.error",
        lambda **kwargs: shown.append(kwargs),
    )
    presenter = OutputTransferFailurePresenter(parent=object())  # type: ignore[arg-type]

    presenter.report_drag_failure(OUTPUT_DRAG_GESTURE_ENDED_MESSAGE)

    assert shown == []
