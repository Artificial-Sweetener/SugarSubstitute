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

"""Build hostile prompt-editor scenarios with exact source checkpoints."""

from __future__ import annotations

from .models import (
    PromptAbuseAction,
    PromptAbuseActionKind,
    PromptAbuseEditorKind,
    PromptAbuseScenario,
)


class PromptAbuseScenarioBuilder:
    """Build exact source checkpoints for one hostile interaction sequence."""

    def __init__(self, text: str, *, cursor_position: int) -> None:
        """Initialize mutable construction state for one immutable scenario."""

        self.text = text
        self.cursor_position = cursor_position
        self.selection_start = cursor_position
        self.selection_end = cursor_position
        self.actions: list[PromptAbuseAction] = []

    def type_text(self, text: str) -> None:
        """Append typed text while recording its exact resulting source."""

        self._replace_selection(text)
        self.actions.append(
            PromptAbuseAction(
                "type",
                value=text,
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=self.cursor_position,
            )
        )

    def paste(self, text: str) -> None:
        """Append a clipboard paste while recording its exact resulting source."""

        self._replace_selection(text)
        self.actions.append(
            PromptAbuseAction(
                "paste",
                value=text,
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=self.cursor_position,
            )
        )

    def move_cursor(self, position: int) -> None:
        """Move the source caret to one exact boundary."""

        self.cursor_position = position
        self.selection_start = position
        self.selection_end = position
        self.actions.append(
            PromptAbuseAction(
                "move_cursor",
                position=position,
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=self.cursor_position,
            )
        )

    def select(self, start: int, end: int) -> None:
        """Select one exact source range for the next destructive action."""

        self.selection_start = min(start, end)
        self.selection_end = max(start, end)
        self.cursor_position = end
        self.actions.append(
            PromptAbuseAction(
                "select",
                position=start,
                selection_end=end,
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=start,
            )
        )

    def key(self, key: str, *, expected_source: str | None = None) -> None:
        """Append one editing key and update supported deterministic source state."""

        if key == "backspace":
            if self.selection_start != self.selection_end:
                self._replace_selection("")
            elif self.cursor_position > 0:
                start = self.cursor_position - 1
                self.text = self.text[:start] + self.text[self.cursor_position :]
                self.cursor_position = start
                self.selection_start = start
                self.selection_end = start
        elif key == "delete":
            if self.selection_start != self.selection_end:
                self._replace_selection("")
            elif self.cursor_position < len(self.text):
                self.text = (
                    self.text[: self.cursor_position]
                    + self.text[self.cursor_position + 1 :]
                )
        elif key == "enter":
            self._replace_selection("\n")
        elif key == "left":
            self.cursor_position = max(0, self.cursor_position - 1)
            self.selection_start = self.cursor_position
            self.selection_end = self.cursor_position
        elif key == "right":
            self.cursor_position = min(len(self.text), self.cursor_position + 1)
            self.selection_start = self.cursor_position
            self.selection_end = self.cursor_position
        elif expected_source is not None:
            self.text = expected_source
            self.cursor_position = min(self.cursor_position, len(self.text))
            self.selection_start = self.cursor_position
            self.selection_end = self.cursor_position
        self.actions.append(
            PromptAbuseAction(
                "key",
                value=key,
                expected_source=self.text,
                expected_cursor_position=(
                    None if key in {"undo", "redo"} else self.cursor_position
                ),
                expected_anchor_position=(
                    None if key in {"undo", "redo"} else self.cursor_position
                ),
            )
        )

    def resize(self, width: int, height: int) -> None:
        """Append a hostile viewport resize without changing source state."""

        self.actions.append(
            PromptAbuseAction(
                "resize",
                viewport_size=(width, height),
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=self.cursor_position,
            )
        )

    def drain_events(self) -> None:
        """Expose queued-work races at an explicit event-loop boundary."""

        self.actions.append(
            PromptAbuseAction(
                "drain_events",
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=self.cursor_position,
            )
        )

    def passive_action(
        self,
        kind: PromptAbuseActionKind,
        *,
        value: str = "",
    ) -> None:
        """Append one source-neutral lifecycle or viewport interaction."""

        self.actions.append(
            PromptAbuseAction(
                kind=kind,
                value=value,
                expected_source=self.text,
                expected_cursor_position=self.cursor_position,
                expected_anchor_position=self.cursor_position,
            )
        )

    def build(
        self,
        name: str,
        initial_text: str,
        *,
        initial_cursor_position: int,
        viewport_size: tuple[int, int] = (720, 240),
        editor_kind: PromptAbuseEditorKind = "prompt",
        seed: int | None = None,
    ) -> PromptAbuseScenario:
        """Return the immutable scenario produced by this builder."""

        return PromptAbuseScenario(
            name=name,
            initial_text=initial_text,
            actions=tuple(self.actions),
            expected_text=self.text,
            cursor_position=initial_cursor_position,
            viewport_size=viewport_size,
            editor_kind=editor_kind,
            seed=seed,
        )

    def _replace_selection(self, replacement: str) -> None:
        """Replace current selection and collapse the caret after new text."""

        start = self.selection_start
        end = self.selection_end
        self.text = self.text[:start] + replacement + self.text[end:]
        self.cursor_position = start + len(replacement)
        self.selection_start = self.cursor_position
        self.selection_end = self.cursor_position


__all__ = ["PromptAbuseScenarioBuilder"]
