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

"""Model terminal-style output with explicit transient redraw-row ownership."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from sugarsubstitute_shared.presentation.terminal.ansi import (
    TerminalStyledLine,
    parse_ansi_sgr_record,
)


class TerminalOutputMutationKind(Enum):
    """Describe one incremental visible transcript update."""

    APPEND_LINE = "append_line"
    REPLACE_LAST_LINE = "replace_last_line"


@dataclass(frozen=True)
class TerminalOutputMutation:
    """Describe one incremental transcript change for renderer consumers.

    Attributes:
        kind: The type of visible mutation to apply.
        line: The rendered line associated with the mutation.
    """

    kind: TerminalOutputMutationKind
    line: str
    styled_line: TerminalStyledLine


class TerminalOutputTranscript:
    """Store bounded terminal output while honoring carriage-return redraws."""

    def __init__(self, *, max_lines: int | None) -> None:
        """Initialize the transcript with one optional visible-history bound."""

        if max_lines is not None and max_lines <= 0:
            raise ValueError("max_lines must be positive when provided.")
        self._max_lines = max_lines
        self._stable_lines: list[TerminalStyledLine] = []
        self._transient_line: TerminalStyledLine | None = None

    def apply_record(self, record: str) -> TerminalOutputMutation | None:
        """Apply one terminal record and return one visible mutation when changed."""

        normalized_record = self.normalize_record(record)
        if normalized_record is None:
            return None
        line = parse_ansi_sgr_record(normalized_record)
        if self._record_is_carriage_return_update(record):
            return self._apply_transient_record(line)
        return self._apply_committed_record(line)

    def apply_records(
        self, records: Iterable[str]
    ) -> tuple[TerminalOutputMutation, ...]:
        """Apply many terminal records in arrival order and return visible mutations."""

        mutations: list[TerminalOutputMutation] = []
        for record in records:
            mutation = self.apply_record(record)
            if mutation is not None:
                mutations.append(mutation)
        return tuple(mutations)

    def clear(self) -> None:
        """Drop all retained transcript lines."""

        self._stable_lines.clear()
        self._transient_line = None

    def snapshot(self) -> tuple[str, ...]:
        """Return the retained transcript lines in display order."""

        return tuple(line.plain_text for line in self.styled_snapshot())

    def styled_snapshot(self) -> tuple[TerminalStyledLine, ...]:
        """Return the retained transcript lines with terminal styling spans."""

        if self._transient_line is None:
            return tuple(self._stable_lines)
        return (*self._stable_lines, self._transient_line)

    @property
    def max_lines(self) -> int | None:
        """Return the bounded retained history size when one is configured."""

        return self._max_lines

    @staticmethod
    def normalize_record(record: str) -> str | None:
        """Normalize one terminal record for display or return ``None`` when empty."""

        normalized = record.rstrip("\r\n")
        if not normalized.strip():
            return None
        return normalized

    def _apply_transient_record(
        self,
        line: TerminalStyledLine,
    ) -> TerminalOutputMutation:
        """Render one carriage-return update as the current transient tail row."""

        if self._transient_line is None:
            self._trim_stable_overflow(extra_visible_lines=1)
            self._transient_line = line
            return TerminalOutputMutation(
                kind=TerminalOutputMutationKind.APPEND_LINE,
                line=line.plain_text,
                styled_line=line,
            )
        self._transient_line = line
        return TerminalOutputMutation(
            kind=TerminalOutputMutationKind.REPLACE_LAST_LINE,
            line=line.plain_text,
            styled_line=line,
        )

    def _apply_committed_record(
        self,
        line: TerminalStyledLine,
    ) -> TerminalOutputMutation:
        """Commit one stable visible row and retire any transient redraw row."""

        replacing_transient_line = self._transient_line is not None
        self._stable_lines.append(line)
        self._transient_line = None
        self._trim_stable_overflow(extra_visible_lines=0)
        mutation_kind = (
            TerminalOutputMutationKind.REPLACE_LAST_LINE
            if replacing_transient_line
            else TerminalOutputMutationKind.APPEND_LINE
        )
        return TerminalOutputMutation(
            kind=mutation_kind,
            line=line.plain_text,
            styled_line=line,
        )

    def _trim_stable_overflow(self, *, extra_visible_lines: int) -> None:
        """Trim retained stable history down to the configured visible bound."""

        if self._max_lines is None:
            return
        visible_limit = self._max_lines - extra_visible_lines
        overflow = len(self._stable_lines) - visible_limit
        if overflow > 0:
            del self._stable_lines[:overflow]

    @staticmethod
    def _record_is_carriage_return_update(record: str) -> bool:
        """Return whether the record redraws the active line in place."""

        return record.endswith("\r") and not record.endswith("\r\n")


__all__ = [
    "TerminalOutputMutation",
    "TerminalOutputMutationKind",
    "TerminalOutputTranscript",
]
