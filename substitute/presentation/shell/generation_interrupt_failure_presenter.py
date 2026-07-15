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

"""Present generation interrupt failures to shell diagnostics."""

from __future__ import annotations

from substitute.application.ports import InterruptResult
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.generation_interrupt_failure_presenter")


class GenerationInterruptFailurePresenter:
    """Report failed interrupt requests to the shell console and logs."""

    def __init__(self, output_stream: object) -> None:
        """Store the shell output stream used for operator-visible diagnostics."""

        self._output_stream = output_stream

    def log_interrupt_failure(self, interrupt_result: InterruptResult) -> None:
        """Log interrupt failure context from workspace generation controls."""

        append_line = getattr(self._output_stream, "append_line", None)
        if callable(append_line):
            append_line(
                "Interrupt request failed."
                f" status={interrupt_result.status}"
                f" status_code={interrupt_result.status_code}"
                f" error={interrupt_result.error or 'none'}"
            )
        log_warning(
            _LOGGER,
            "Generation interrupt request failed",
            status=interrupt_result.status,
            status_code=interrupt_result.status_code,
            error=interrupt_result.error,
        )


__all__ = ["GenerationInterruptFailurePresenter"]
