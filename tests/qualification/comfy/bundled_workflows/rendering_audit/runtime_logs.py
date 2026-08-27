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

"""Capture production warnings emitted during one bundled-workflow audit."""

from __future__ import annotations

import logging
import traceback

from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    RuntimeLogObservation,
)


class WorkflowRuntimeLogCapture(logging.Handler):
    """Capture warning-or-higher runtime logs for the active workflow."""

    def __init__(self) -> None:
        """Initialize a warning-level handler with an empty record buffer."""

        super().__init__(level=logging.WARNING)
        self._observations: list[RuntimeLogObservation] = []

    def reset(self) -> None:
        """Discard captured records from the previously completed workflow."""

        self._observations.clear()

    def observations(self) -> tuple[RuntimeLogObservation, ...]:
        """Return captured records for the current workflow."""

        return tuple(self._observations)

    def emit(self, record: logging.LogRecord) -> None:
        """Persist one log record without interfering with normal handlers."""

        try:
            trace = (
                "".join(traceback.format_exception(*record.exc_info))
                if record.exc_info is not None
                else ""
            )
            self._observations.append(
                RuntimeLogObservation(
                    level=record.levelname,
                    logger=record.name,
                    message=record.getMessage(),
                    traceback=trace,
                )
            )
        except Exception:
            self.handleError(record)
