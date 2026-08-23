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

"""Provide shared geometry proof for caret-navigation tests."""

from __future__ import annotations

import random
from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionLineSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    surface_for,
)


def _projection_lines(
    surface: PromptProjectionSurface,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return the live projection visual-line snapshots for focused geometry tests."""

    return cast(
        tuple[PromptProjectionLineSnapshot, ...],
        cast(Any, surface)._layout.frame.output.snapshot.lines,
    )


class _CaretPlacementHarness:
    """Drive one live prompt editor and assert caret geometry after every step."""

    def __init__(
        self,
        box: PromptEditor,
        *,
        app: QApplication,
        inset: float,
    ) -> None:
        """Capture the widget, surface, and expected content-left coordinate."""

        self._box = box
        self._app = app
        self._surface = surface_for(box)
        self._inset = inset
        self._surface.set_source_line_content_left_inset(inset)
        process_events(app)

    @property
    def content_left(self) -> float:
        """Return the document-local x coordinate where editable content starts."""

        return float(
            cast(Any, self._surface)._layout.frame.output.configuration.document_margin
        ) + max(
            0.0,
            self._inset,
        )

    @property
    def surface(self) -> PromptProjectionSurface:
        """Return the projection surface driven by this harness."""

        return self._surface

    def set_cursor(self, position: int) -> None:
        """Move the logical caret to one raw source position."""

        self._surface.set_cursor_positions(
            cursor_position=position,
            anchor_position=position,
        )
        self.assert_caret_valid(f"set_cursor({position})")

    def key(self, key: Qt.Key) -> None:
        """Send one key press and assert the resulting caret geometry."""

        QTest.keyClick(self._box, key)
        self.assert_caret_valid(f"key({key})")

    def type_text(self, text: str) -> None:
        """Type plain text and assert the resulting caret geometry."""

        QTest.keyClicks(self._box, text)
        self.assert_caret_valid(f"type_text({text!r})")

    def random_stress_step(self, *, rng: random.Random, step_index: int) -> str:
        """Apply one deterministic random edit/navigation operation."""

        text = self._box.toPlainText()
        actions = [
            "type_char",
            "type_word",
            "enter",
            "backspace",
            "up",
            "down",
            "left",
            "right",
            "jump_position",
        ]
        if "\n" in text:
            actions.extend(["after_newline_backspace", "before_newline_enter"])
        action = rng.choice(actions)
        if action == "type_char":
            value = rng.choice("abcdefghijklmnopqrstuvwxyz ")
            QTest.keyClicks(self._box, value)
        elif action == "type_word":
            length = rng.randint(2, 7)
            value = "".join(
                rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(length)
            )
            QTest.keyClicks(self._box, value)
        elif action == "enter":
            QTest.keyClick(self._box, Qt.Key.Key_Return)
        elif action == "backspace":
            QTest.keyClick(self._box, Qt.Key.Key_Backspace)
        elif action == "up":
            QTest.keyClick(self._box, Qt.Key.Key_Up)
        elif action == "down":
            QTest.keyClick(self._box, Qt.Key.Key_Down)
        elif action == "left":
            QTest.keyClick(self._box, Qt.Key.Key_Left)
        elif action == "right":
            QTest.keyClick(self._box, Qt.Key.Key_Right)
        elif action == "jump_position":
            position = rng.randint(0, len(text))
            self._surface.set_cursor_positions(
                cursor_position=position,
                anchor_position=position,
            )
        elif action == "after_newline_backspace":
            newline_positions = [
                index + 1 for index, character in enumerate(text) if character == "\n"
            ]
            position = rng.choice(newline_positions)
            self._surface.set_cursor_positions(
                cursor_position=position,
                anchor_position=position,
            )
            QTest.keyClick(self._box, Qt.Key.Key_Backspace)
        elif action == "before_newline_enter":
            newline_positions = [
                index for index, character in enumerate(text) if character == "\n"
            ]
            position = rng.choice(newline_positions)
            self._surface.set_cursor_positions(
                cursor_position=position,
                anchor_position=position,
            )
            QTest.keyClick(self._box, Qt.Key.Key_Return)
        else:
            raise AssertionError(f"unknown random stress action: {action}")
        self.assert_caret_valid(f"random_stress_step({step_index}, {action})")
        return action

    def click_visual_line_start(self, line_index: int) -> None:
        """Click inside the left gutter of one visual line and assert content snapping."""

        line = _projection_lines(self._surface)[line_index]
        QTest.mouseClick(
            self._box.viewport(),
            Qt.MouseButton.LeftButton,
            pos=QPoint(
                max(0, int(self.content_left - 12.0)),
                int(line.top + (line.height / 2.0)),
            ),
        )
        self.assert_caret_valid(f"click_visual_line_start({line_index})")

    def set_visual_line_start_from_layout_hit(self, line_index: int) -> None:
        """Place the caret using the production layout hit-test for one visual line."""

        line = _projection_lines(self._surface)[line_index]
        caret_hit = cast(
            Any, self._surface
        )._layout.frame.geometry.hit_testing.caret_hit_test(
            QPointF(
                max(0.0, self.content_left - 12.0),
                line.top + (line.height / 2.0),
            ),
            scroll_offset=0.0,
        )
        cast(Any, self._surface)._set_cursor_from_projection_hit(
            caret_hit.state,
            keep_anchor=False,
            caret_rect_override=caret_hit.document_rect,
        )
        self.assert_caret_valid(f"set_visual_line_start_from_layout_hit({line_index})")

    def assert_caret_valid(self, label: str) -> QRectF:
        """Fail when live caret geometry lands before editable content."""

        process_events(self._app)
        caret_rect = cast(Any, self._surface)._current_caret_document_rect()
        assert caret_rect.left() >= self.content_left - 1.0, self._describe_failure(
            label,
            caret_rect,
        )
        self.assert_line_caret_stops_valid(label)
        return QRectF(caret_rect)

    def assert_caret_at_line_start(self, line_index: int, label: str) -> QRectF:
        """Assert that the live caret sits at the editable start of one visual line."""

        caret_rect = self.assert_caret_valid(label)
        line = _projection_lines(self._surface)[line_index]
        assert caret_rect.left() == pytest.approx(self.content_left, abs=1.0), (
            self._describe_failure(label, caret_rect)
        )
        assert caret_rect.top() == pytest.approx(line.top, abs=1.0), (
            self._describe_failure(label, caret_rect)
        )
        return caret_rect

    def assert_line_caret_stops_valid(self, label: str) -> None:
        """Fail when any line-local caret stop is positioned inside the left gutter."""

        for line_index, line in enumerate(_projection_lines(self._surface)):
            for stop_index, caret_stop in enumerate(line.caret_stops):
                assert caret_stop.rect.left() >= self.content_left - 1.0, (
                    f"{label}: line caret stop is inside the left margin; "
                    f"line_index={line_index} stop_index={stop_index} "
                    f"projection_position={caret_stop.projection_position} "
                    f"stop_left={caret_stop.rect.left():.2f} "
                    f"content_left={self.content_left:.2f} "
                    f"source_range=({line.source_start}, {line.source_end}) "
                    f"content_range=({line.source_content_start}, "
                    f"{line.source_content_end}) text={self._box.toPlainText()!r}"
                )

    def assert_down_moves_when_lower_visual_line_exists(self, label: str) -> None:
        """Fail when Down cannot leave a non-final visual line."""

        before_rect = self.assert_caret_valid(f"{label}: before Down")
        before_line_index = self._line_index_for_rect(before_rect)
        lines = _projection_lines(self._surface)
        if before_line_index is None or before_line_index >= len(lines) - 1:
            return

        QTest.keyClick(self._box, Qt.Key.Key_Down)
        after_rect = self.assert_caret_valid(f"{label}: after Down")
        after_line_index = self._line_index_for_rect(after_rect)

        assert after_line_index is not None, self._describe_failure(label, after_rect)
        assert after_line_index > before_line_index, (
            f"{label}: Down did not move to a lower visual line; "
            f"before_line_index={before_line_index} "
            f"after_line_index={after_line_index} "
            f"cursor_position={self._surface.cursor_position} "
            f"text={self._box.toPlainText()!r}"
        )

    def assert_caret_has_no_stale_visual_override(self, label: str) -> QRectF:
        """Fail when the live caret rect disagrees with the logical layout rect."""

        caret_rect = self.assert_caret_valid(label)
        layout_rect = cast(Any, self._surface)._layout.frame.geometry.caret.cursor_rect(
            cast(Any, self._surface)._cursor_state,
            scroll_offset=0.0,
        )
        assert cast(Any, self._surface)._caret_rect_override is None, (
            f"{label}: stale caret rect override remains; "
            f"cursor_position={self._surface.cursor_position} "
            f"text={self._box.toPlainText()!r}"
        )
        assert caret_rect.left() == pytest.approx(layout_rect.left(), abs=1.0), (
            self._describe_failure(label, caret_rect)
        )
        assert caret_rect.top() == pytest.approx(layout_rect.top(), abs=1.0), (
            self._describe_failure(label, caret_rect)
        )
        return caret_rect

    def soft_wrap_transition_pair(self) -> tuple[int, int, int]:
        """Return adjacent visual lines that share a soft-wrap caret position."""

        lines = _projection_lines(self._surface)
        for line_index, (left_line, right_line) in enumerate(zip(lines, lines[1:])):
            if not left_line.caret_stops or not right_line.caret_stops:
                continue
            left_position = left_line.caret_stops[-1].projection_position
            right_position = right_line.caret_stops[0].projection_position
            if left_position == right_position:
                return (line_index, line_index + 1, left_position)
        raise AssertionError(
            "test setup did not produce an adjacent soft-wrap caret transition"
        )

    def _line_index_for_rect(self, caret_rect: QRectF) -> int | None:
        """Return the visual line owning one caret rectangle."""

        caret_center_y = caret_rect.center().y()
        for line_index, line in enumerate(_projection_lines(self._surface)):
            if (line.top - 1.0) <= caret_center_y <= (line.top + line.height + 1.0):
                return line_index
        return None

    def _describe_failure(self, label: str, caret_rect: QRectF) -> str:
        """Return detailed caret and line geometry for one failed harness step."""

        line_details = "; ".join(
            (
                f"{index}:top={line.top:.2f},height={line.height:.2f},"
                f"source=({line.source_start},{line.source_end}),"
                f"content=({line.source_content_start},{line.source_content_end}),"
                f"stops={[(stop.projection_position, round(stop.rect.left(), 2)) for stop in line.caret_stops[:4]]}"
            )
            for index, line in enumerate(_projection_lines(self._surface))
        )
        return (
            f"{label}: caret is inside the left margin; "
            f"cursor_position={self._surface.cursor_position} "
            f"caret=({caret_rect.left():.2f}, {caret_rect.top():.2f}, "
            f"{caret_rect.width():.2f}, {caret_rect.height():.2f}) "
            f"content_left={self.content_left:.2f} "
            f"text={self._box.toPlainText()!r} lines=[{line_details}]"
        )


def _surface_should_paint_caret(box: PromptEditor) -> bool:
    """Return whether the live projection surface currently wants to paint the caret."""

    return surface_for(box)._should_paint_caret()  # noqa: SLF001


def _restart_surface_caret_blink_cycle(box: PromptEditor) -> None:
    """Restart the custom caret blink timer for deterministic timer assertions."""

    surface_for(box)._restart_caret_blink_cycle()  # noqa: SLF001
    process_events(ensure_qapp())
