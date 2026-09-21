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

"""Retire known diagnostics without changing an already classified run outcome."""

from __future__ import annotations

import errno
import logging
from pathlib import Path

from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext
from sugarsubstitute_shared.crash_reporting.run_context import (
    RUNTIME_CONTEXT_FILENAME,
    STARTUP_OUTPUT_FILENAME,
)

_LOGGER = logging.getLogger(__name__)


class CompletedRunArtifacts:
    """Own best-effort disposal of temporary files from an expected completion."""

    def __init__(self, context: CrashRunContext) -> None:
        """Limit cleanup to the exact diagnostic namespace of one completed run."""
        self._context = context

    def discard(self, *, minidump: Path | None) -> None:
        """Keep unavailable evidence and unrelated files without obstructing shutdown."""
        context = self._context
        if minidump is not None:
            self._unlink(minidump)
            attachment_directory = (
                context.crashpad_database / "attachments" / minidump.stem
            )
            self._unlink(attachment_directory / "python-fault.log")
            self._remove_empty_directory(attachment_directory)
        for path in (context.exit_intent_path, context.exit_receipt_path):
            self._unlink(path)
        self._remove_empty_directory(context.exit_intent_path.parent)
        incident_directory = context.incident_root / context.run_id
        for filename in (
            "python-fault.log",
            RUNTIME_CONTEXT_FILENAME,
            STARTUP_OUTPUT_FILENAME,
        ):
            self._unlink(incident_directory / filename)
        self._remove_empty_directory(incident_directory)

    def _unlink(self, path: Path) -> None:
        """Record retained evidence when the filesystem cannot dispose of it now."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _LOGGER.warning(
                "Completed-run diagnostic retained because cleanup was unavailable",
                extra={"run_id": self._context.run_id, "artifact": str(path)},
                exc_info=True,
            )

    def _remove_empty_directory(self, path: Path) -> None:
        """Remove empty scaffolding while preserving any remaining evidence."""
        try:
            path.rmdir()
        except FileNotFoundError:
            return
        except OSError as error:
            if error.errno in (errno.ENOTEMPTY, errno.EEXIST):
                _LOGGER.debug(
                    "Completed-run directory retained with remaining evidence",
                    extra={"run_id": self._context.run_id, "directory": str(path)},
                )
                return
            _LOGGER.warning(
                "Completed-run diagnostic directory retained because cleanup was unavailable",
                extra={"run_id": self._context.run_id, "directory": str(path)},
                exc_info=True,
            )
