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

"""Compute source-backed clipboard edit intents for prompt editing."""

from __future__ import annotations

from dataclasses import dataclass

from .selection_state import PromptSelection


@dataclass(frozen=True, slots=True)
class PromptClipboardCopyResult:
    """Describe source text copied from the current selection."""

    text: str


@dataclass(frozen=True, slots=True)
class PromptClipboardCutResult:
    """Describe source text cut from the current selection."""

    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PromptClipboardPasteResult:
    """Describe the source range replaced by pasted text."""

    start: int
    end: int
    text: str


class PromptClipboardController:
    """Prepare source-backed copy, cut, and paste operations."""

    def copy(
        self,
        *,
        source_text: str,
        selection: PromptSelection,
    ) -> PromptClipboardCopyResult:
        """Return the raw source text covered by the current selection."""

        return PromptClipboardCopyResult(text=selection.selected_text(source_text))

    def cut(
        self,
        *,
        source_text: str,
        selection: PromptSelection,
    ) -> PromptClipboardCutResult | None:
        """Return the selected source range to cut, if one exists."""

        clamped_selection = selection.clamped(len(source_text))
        if clamped_selection.is_empty:
            return None
        return PromptClipboardCutResult(
            text=clamped_selection.selected_text(source_text),
            start=clamped_selection.start,
            end=clamped_selection.end,
        )

    def paste(
        self,
        *,
        pasted_text: str,
        source_text: str,
        selection: PromptSelection,
    ) -> PromptClipboardPasteResult:
        """Return the source range that should receive pasted text."""

        clamped_selection = selection.clamped(len(source_text))
        return PromptClipboardPasteResult(
            start=clamped_selection.start,
            end=clamped_selection.end,
            text=pasted_text,
        )


__all__ = [
    "PromptClipboardController",
    "PromptClipboardCopyResult",
    "PromptClipboardCutResult",
    "PromptClipboardPasteResult",
]
