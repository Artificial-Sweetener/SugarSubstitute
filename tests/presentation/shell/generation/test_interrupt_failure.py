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

"""Tests for generation interrupt failure presentation."""

from __future__ import annotations

import logging

import pytest

from substitute.application.ports import InterruptResult
from substitute.presentation.shell.generation_interrupt_failure_presenter import (
    GenerationInterruptFailurePresenter,
)


class _OutputStream:
    """Record shell console output lines."""

    def __init__(self) -> None:
        """Create empty output records."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one appended console line."""

        self.lines.append(line)


def test_log_interrupt_failure_writes_console_line_and_structured_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed interrupt requests should be visible in console and logs."""

    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.shell.generation_interrupt_failure_presenter",
    )
    output_stream = _OutputStream()

    GenerationInterruptFailurePresenter(output_stream).log_interrupt_failure(
        InterruptResult(status="failed", status_code=500, error="boom")
    )

    assert output_stream.lines == [
        "Interrupt request failed. status=failed status_code=500 error=boom"
    ]
    assert "Generation interrupt request failed" in caplog.text
    assert "status=failed" in caplog.text
    assert "status_code=500" in caplog.text
    assert "error=boom" in caplog.text
