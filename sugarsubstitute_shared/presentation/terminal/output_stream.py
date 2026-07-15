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

"""Buffer terminal output records and notify Qt presentation subscribers."""

from __future__ import annotations

from collections.abc import Iterable
from threading import Lock

from PySide6.QtCore import QObject, Signal

from sugarsubstitute_shared.presentation.terminal.output_transcript import (
    TerminalOutputMutation,
    TerminalOutputTranscript,
)
from sugarsubstitute_shared.presentation.terminal.ansi import TerminalStyledLine


class TerminalOutputStream(QObject):
    """Store bounded terminal output history and broadcast transcript changes."""

    changed = Signal()
    mutation_applied = Signal(object)
    cleared = Signal()

    def __init__(self, *, max_lines: int = 2000) -> None:
        """Initialize the stream with one bounded terminal transcript."""

        super().__init__()
        self._transcript = TerminalOutputTranscript(max_lines=max_lines)
        self._lock = Lock()

    def append_line(self, line: str) -> None:
        """Append one terminal record and emit one incremental mutation when changed."""

        with self._lock:
            mutation = self._transcript.apply_record(line)
        if mutation is None:
            return
        self._emit_mutation(mutation)

    def append_lines(self, lines: Iterable[str]) -> None:
        """Append many terminal records and emit one mutation per visible change."""

        with self._lock:
            mutations = self._transcript.apply_records(lines)
        for mutation in mutations:
            self._emit_mutation(mutation)

    def clear(self) -> None:
        """Drop all buffered terminal history and notify subscribers."""

        with self._lock:
            self._transcript.clear()
        self.cleared.emit()

    def snapshot(self) -> tuple[str, ...]:
        """Return the current buffered transcript in display order."""

        with self._lock:
            return self._transcript.snapshot()

    def styled_snapshot(self) -> tuple[TerminalStyledLine, ...]:
        """Return the current buffered transcript with terminal styling spans."""

        with self._lock:
            return self._transcript.styled_snapshot()

    @property
    def max_lines(self) -> int:
        """Return the configured retained-history bound."""

        max_lines = self._transcript.max_lines
        assert max_lines is not None
        return max_lines

    @staticmethod
    def normalize_record(record: str) -> str | None:
        """Normalize one terminal record for direct display or return ``None``."""

        return TerminalOutputTranscript.normalize_record(record)

    def _emit_mutation(self, mutation: TerminalOutputMutation) -> None:
        """Broadcast one visible transcript mutation to subscribers."""

        self.mutation_applied.emit(mutation)
        self.changed.emit()


__all__ = ["TerminalOutputStream"]
