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

"""Tests for truthful setup activity with a concise optional console."""

from __future__ import annotations

from substitute.presentation.onboarding.setup_activity_output import (
    SetupActivityOutput,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)


def test_setup_output_pulses_every_record_but_coalesces_busy_progress() -> None:
    """Preserve raw activity fidelity while showing about one line per ten percent."""

    stream = TerminalOutputStream()
    activity: list[None] = []
    diagnostics: list[str] = []
    presenter = SetupActivityOutput(
        stream=stream,
        activity_observer=lambda: activity.append(None),
        diagnostic_sink=diagnostics.append,
    )
    messages = [
        f"Copying managed Python packages: {percentage}/100 ({percentage}%), "
        "about 1s remaining."
        for percentage in range(101)
    ]

    for message in messages:
        presenter.accept(message)

    assert len(activity) == 101
    assert diagnostics == messages
    assert len(stream.snapshot()) == 11
    assert "(0%)" in stream.snapshot()[0]
    assert "(100%)" in stream.snapshot()[-1]


def test_setup_output_suppresses_dependency_noise_without_hiding_milestones() -> None:
    """Keep dependency summaries and raw diagnostics without pip satisfaction spam."""

    stream = TerminalOutputStream()
    activity: list[None] = []
    diagnostics: list[str] = []
    presenter = SetupActivityOutput(
        stream=stream,
        activity_observer=lambda: activity.append(None),
        diagnostic_sink=diagnostics.append,
    )

    presenter.accept("Installing SugarCubes Python dependencies.")
    presenter.accept("Requirement already satisfied: aiohttp (3.14.3)")
    presenter.accept("SugarCubes 0.14.9 is ready.")

    assert len(activity) == 3
    assert len(diagnostics) == 3
    assert stream.snapshot() == (
        "Installing SugarCubes Python dependencies.",
        "SugarCubes 0.14.9 is ready.",
    )
