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

import logging
import os
from pathlib import Path
import shutil
import tempfile

from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext
from sugarsubstitute_shared.crash_reporting.run_context import (
    STARTUP_OUTPUT_FILENAME,
)

_LOGGER = logging.getLogger(__name__)


class CompletedRunArtifacts:
    """Own best-effort disposal of temporary files from an expected completion."""

    def __init__(self, context: CrashRunContext) -> None:
        """Limit cleanup to the exact diagnostic namespace of one completed run."""
        self._context = context

    def discard(self, *, minidump: Path | None, startup_log_path: Path) -> None:
        """Publish current startup output, then retire this exact run workspace."""
        context = self._context
        if minidump is not None:
            self._unlink(minidump)
            attachment_directory = (
                context.crashpad_database / "attachments" / minidump.stem
            )
            self._unlink(attachment_directory / "python-fault.log")
            self._remove_empty_directory(attachment_directory)
        run_directory = context.run_root / context.run_id
        startup_published = self._publish_startup_output(
            run_directory / STARTUP_OUTPUT_FILENAME,
            startup_log_path,
        )
        if not startup_published:
            return
        try:
            shutil.rmtree(run_directory)
        except FileNotFoundError:
            return
        except OSError:
            _LOGGER.warning(
                "Completed-run workspace retained because cleanup was unavailable",
                extra={"run_id": context.run_id, "directory": str(run_directory)},
                exc_info=True,
            )

    def _publish_startup_output(self, source: Path, destination: Path) -> bool:
        """Atomically replace the canonical log and report whether cleanup is safe."""

        try:
            with source.open("rb") as source_file:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=destination.parent,
                        prefix=f".{destination.name}.",
                        suffix=".tmp",
                        delete=False,
                    ) as temporary_file:
                        temporary_path = Path(temporary_file.name)
                        shutil.copyfileobj(source_file, temporary_file)
                        temporary_file.flush()
                        os.fsync(temporary_file.fileno())
                    os.replace(temporary_path, destination)
                finally:
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)
        except FileNotFoundError:
            return True
        except OSError:
            _LOGGER.warning(
                "Completed-run startup output could not be published",
                extra={"run_id": self._context.run_id, "artifact": str(source)},
                exc_info=True,
            )
            return False
        return True

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
        """Remove one now-empty Crashpad attachment directory when available."""

        try:
            path.rmdir()
        except FileNotFoundError:
            return
        except OSError:
            _LOGGER.debug(
                "Crashpad attachment directory retained with remaining evidence",
                extra={"run_id": self._context.run_id, "directory": str(path)},
            )
