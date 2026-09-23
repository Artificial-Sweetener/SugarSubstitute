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

"""Promote one temporary diagnostic run into durable incident evidence."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil

from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext
from sugarsubstitute_shared.crash_reporting.run_context import (
    RUNTIME_CONTEXT_FILENAME,
    STARTUP_OUTPUT_FILENAME,
)
from sugarsubstitute_shared.crash_reporting.store import CrashIncidentStore
from launcher.sugarsubstitute_launcher.crash_launcher_log import (
    LAUNCHER_LOG_TAIL_FILENAME,
)


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PromotedIncidentEvidence:
    """Describe copied attachments and the temporary sources used to classify them."""

    attachment_names: tuple[str, ...]
    fault_log: Path
    startup_output: Path
    retained_minidump: Path | None
    run_retention_complete: bool


class CrashIncidentEvidencePromoter:
    """Atomically copy one run's evidence and retire only fully promoted workspaces."""

    def __init__(self, context: CrashRunContext) -> None:
        """Bind promotion to one authenticated run and its incident store."""

        self._context = context
        self._run_directory = context.run_root / context.run_id
        self._store = CrashIncidentStore(context.incident_root)

    def promote(self, *, minidump: Path | None) -> PromotedIncidentEvidence:
        """Copy every available meaningful artifact into the incident namespace."""

        retained: list[str] = []
        run_retention_complete = True
        fault_log = self._run_directory / "python-fault.log"
        startup_output = self._run_directory / STARTUP_OUTPUT_FILENAME
        for filename in (
            "python-fault.log",
            STARTUP_OUTPUT_FILENAME,
            LAUNCHER_LOG_TAIL_FILENAME,
            RUNTIME_CONTEXT_FILENAME,
            "exit-intent.json",
            "exit-receipt.json",
        ):
            source = self._run_directory / filename
            if not source.is_file():
                continue
            if source.suffix in {".log", ".txt"} and not file_has_meaningful_content(
                source
            ):
                continue
            try:
                self._store.retain_attachment(
                    self._context.run_id,
                    source,
                    filename=filename,
                )
            except OSError:
                run_retention_complete = False
                _LOGGER.exception(
                    "Run diagnostic could not be retained with its incident.",
                    extra={
                        "run_id": self._context.run_id,
                        "artifact": str(source),
                    },
                )
                continue
            retained.append(filename)
        retained_minidump = self._retain_minidump(minidump)
        if retained_minidump is not None:
            retained.append(retained_minidump.name)
        return PromotedIncidentEvidence(
            attachment_names=tuple(dict.fromkeys(retained)),
            fault_log=fault_log,
            startup_output=startup_output,
            retained_minidump=retained_minidump,
            run_retention_complete=run_retention_complete,
        )

    def retire(self, evidence: PromotedIncidentEvidence) -> None:
        """Remove the run workspace only after every available run file was copied."""

        if not evidence.run_retention_complete:
            return
        try:
            shutil.rmtree(self._run_directory)
        except FileNotFoundError:
            return
        except OSError:
            _LOGGER.warning(
                "Crash run workspace remained after incident finalization.",
                extra={
                    "run_id": self._context.run_id,
                    "directory": str(self._run_directory),
                },
                exc_info=True,
            )

    def _retain_minidump(self, minidump: Path | None) -> Path | None:
        """Retain an available minidump without discarding other evidence."""

        if minidump is None:
            return None
        try:
            return self._store.retain_attachment(self._context.run_id, minidump)
        except OSError:
            _LOGGER.exception(
                "Crashpad minidump could not be retained with its incident.",
                extra={"run_id": self._context.run_id},
            )
            return None


def file_has_meaningful_content(path: Path) -> bool:
    """Return whether bounded head or tail evidence contains non-whitespace data."""

    try:
        with path.open("rb") as stream:
            head = stream.read(4096)
            if any(not chr(byte).isspace() for byte in head):
                return True
            stream.seek(0, 2)
            size = stream.tell()
            if size <= len(head):
                return False
            stream.seek(max(0, size - 4096))
            return any(not chr(byte).isspace() for byte in stream.read())
    except OSError:
        return False


__all__ = [
    "CrashIncidentEvidencePromoter",
    "PromotedIncidentEvidence",
    "file_has_meaningful_content",
]
