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

"""Tests for prompt projection caret navigation and visibility behavior."""

from __future__ import annotations

import os
import random
from time import perf_counter
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionLineSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    delay_projection_update_scheduler as _delay_projection_update_scheduler,
    flush_semantic_refresh as _flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _projection_lines(
    surface: PromptProjectionSurface,
) -> tuple[PromptProjectionLineSnapshot, ...]:
    """Return the live projection visual-line snapshots for focused geometry tests."""

    return cast(
        tuple[PromptProjectionLineSnapshot, ...],
        cast(Any, surface)._layout._snapshot.lines,
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

        return float(cast(Any, self._surface)._layout.document_margin) + max(
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
        caret_hit = cast(Any, self._surface)._layout.caret_hit_test(
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
        layout_rect = cast(Any, self._surface)._layout.cursor_rect(
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


def _wait_for_surface_caret_state(
    box: PromptEditor,
    *,
    expected: bool,
    timeout_ms: int = 150,
) -> None:
    """Wait until Qt delivers a caret blink timer transition."""

    app = ensure_qapp()
    deadline = perf_counter() + (timeout_ms / 1000.0)
    while perf_counter() < deadline:
        process_events(app)
        if _surface_should_paint_caret(box) is expected:
            return
        QTest.qWait(5)
    process_events(app)
    assert _surface_should_paint_caret(box) is expected


def _restart_surface_caret_blink_cycle(box: PromptEditor) -> None:
    """Restart the custom caret blink timer for deterministic timer assertions."""

    surface_for(box)._restart_caret_blink_cycle()  # noqa: SLF001
    process_events(ensure_qapp())


def test_projection_surface_incremental_blank_line_click_uses_content_start(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking an incrementally-created blank line should land at content start."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
    )
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(24.0)
    process_events(app)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha\n")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    assert box.toPlainText() == "alpha\n\nbeta"
    assert rebuild_count == 0
    blank_line = _projection_lines(surface)[1]
    content_left = surface._layout.document_margin + 24.0  # noqa: SLF001
    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(2, int(blank_line.top + (blank_line.height / 2.0))),
    )
    process_events(app)

    caret_rect = box.cursorRect()
    assert surface.cursor_position == len("alpha\n")
    assert caret_rect.x() == pytest.approx(content_left, abs=1.0)
    assert caret_rect.y() == pytest.approx(blank_line.top, abs=1.0)


def test_projection_surface_vertical_navigation_reaches_incremental_blank_line(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Up and Down should traverse an incrementally-created blank visual line."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta",
        width=360,
    )
    surface = surface_for(box)
    surface.set_source_line_content_left_inset(24.0)
    process_events(app)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len("alpha\n")
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    first_line, blank_line, third_line = _projection_lines(surface)[:3]
    surface.set_cursor_positions(cursor_position=0, anchor_position=0)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert surface.cursor_position == blank_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(blank_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert surface.cursor_position == third_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(third_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    assert surface.cursor_position == blank_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(blank_line.top, abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    assert surface.cursor_position == first_line.source_content_start
    assert box.cursorRect().y() == pytest.approx(first_line.top, abs=1.0)
    assert rebuild_count == 0


def test_projection_surface_caret_placement_harness_keeps_blank_lines_out_of_margin(
    widgets: list[QWidget],
) -> None:
    """Caret placement should stay at content-left across blank-line edits."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\nbeta\ngamma",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface

    harness.set_cursor(len("alpha\n"))
    harness.key(Qt.Key.Key_Return)
    assert box.toPlainText() == "alpha\n\nbeta\ngamma"

    harness.click_visual_line_start(1)
    assert surface.cursor_position == len("alpha\n")
    harness.assert_caret_at_line_start(1, "blank-line click")

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == len("alpha\n\n")
    harness.assert_caret_at_line_start(2, "down from blank line")

    harness.key(Qt.Key.Key_Up)
    assert surface.cursor_position == len("alpha\n")
    harness.assert_caret_at_line_start(1, "up to blank line")

    harness.set_cursor(len("alpha\n\n"))
    harness.key(Qt.Key.Key_Backspace)
    assert box.toPlainText() == "alpha\nbeta\ngamma"
    harness.assert_caret_at_line_start(1, "backspace removed blank line")

    harness.key(Qt.Key.Key_Backspace)
    assert box.toPlainText() == "alphabeta\ngamma"
    harness.assert_caret_valid("backspace removed hard line break")


def test_projection_surface_caret_placement_harness_splits_empty_line_at_content_start(
    widgets: list[QWidget],
) -> None:
    """Enter before an empty-line newline should keep both blank carets aligned."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha\n\nbeta",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)

    harness.set_cursor(len("alpha\n"))
    harness.key(Qt.Key.Key_Return)

    assert box.toPlainText() == "alpha\n\n\nbeta"
    harness.assert_caret_at_line_start(2, "empty-line split inserted blank line")
    for line_index in (1, 2):
        line = _projection_lines(harness.surface)[line_index]
        assert line.caret_stops
        assert line.caret_stops[0].rect.left() == pytest.approx(
            harness.content_left,
            abs=1.0,
        )


def test_projection_surface_caret_placement_harness_backspace_after_erasing_second_line(
    widgets: list[QWidget],
) -> None:
    """Backspace after erasing second-line text should keep blank-line navigation valid."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n{erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    harness.set_cursor(len(box.toPlainText()))

    for _character in erased_text:
        harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(1, "after erasing second-line text")

    harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == ""
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "after deleting leading line break")

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "down after deleting leading line break")


def test_projection_surface_caret_placement_harness_backspace_after_incremental_second_line(
    widgets: list[QWidget],
) -> None:
    """Backspace after incrementally-created second-line text should not strand caret."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text="",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface

    harness.key(Qt.Key.Key_Return)
    harness.type_text(erased_text)

    assert box.toPlainText() == f"\n{erased_text}"
    harness.assert_caret_valid("after creating second-line text")

    for _character in erased_text:
        harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(1, "after erasing incremental second-line text")

    harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == ""
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "after deleting incremental line break")

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(0, "down after deleting incremental line break")


def test_projection_surface_caret_placement_harness_backspace_after_selection_erases_second_line(
    widgets: list[QWidget],
) -> None:
    """Selection-erasing second-line text should leave newline Backspace navigable."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n{erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    surface.set_cursor_positions(
        cursor_position=len(box.toPlainText()),
        anchor_position=1,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    harness.assert_caret_valid("after selection erases second-line text")

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(1, "after selection-erasing second-line text")

    QTest.keyClick(box, Qt.Key.Key_Backspace)
    harness.assert_caret_valid("after Backspace deletes selection-erased line break")

    assert box.toPlainText() == ""
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(
        0,
        "after deleting selection-erased line break",
    )

    QTest.keyClick(box, Qt.Key.Key_Down)
    assert surface.cursor_position == 0
    harness.assert_caret_at_line_start(
        0,
        "down after deleting selection-erased line break",
    )


def test_projection_surface_caret_placement_harness_backspace_after_erasing_indented_second_line(
    widgets: list[QWidget],
) -> None:
    """Backspace after erasing an indented second line should stay on that line."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n {erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    harness.set_cursor(len(box.toPlainText()))

    for _character in erased_text:
        harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n "
    assert surface.cursor_position == 2
    caret_after_word_delete = harness.assert_caret_valid(
        "after erasing indented second-line text",
    )
    second_line = _projection_lines(surface)[1]
    assert caret_after_word_delete.top() == pytest.approx(second_line.top, abs=1.0)
    assert caret_after_word_delete.left() > harness.content_left

    harness.key(Qt.Key.Key_Backspace)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "after deleting second-line indentation",
    )

    harness.key(Qt.Key.Key_Down)
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "down after deleting second-line indentation",
    )


def test_projection_surface_caret_placement_harness_backspace_burst_after_indented_second_line(
    widgets: list[QWidget],
) -> None:
    """Rapid erase then Backspace should not leave caret above the remaining blank line."""

    app = ensure_qapp()
    erased_text = "fajsklfajfkla"
    box = show_prompt_editor(
        widgets,
        text=f"\n {erased_text}",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    surface.set_cursor_positions(
        cursor_position=len(box.toPlainText()),
        anchor_position=len(box.toPlainText()),
    )
    process_events(app)

    for _character in erased_text:
        QTest.keyClick(box, Qt.Key.Key_Backspace)
    QTest.keyClick(box, Qt.Key.Key_Backspace)
    process_events(app)

    assert box.toPlainText() == "\n"
    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "after rapid deleting second-line indentation",
    )

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert surface.cursor_position == 1
    harness.assert_caret_at_line_start(
        1,
        "down after rapid deleting second-line indentation",
    )


def test_projection_surface_caret_placement_harness_down_from_first_blank_to_indented_blank(
    widgets: list[QWidget],
) -> None:
    """Down from the first blank line should reach a second whitespace-only line."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="\n ",
        width=360,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    harness.set_cursor(0)

    harness.key(Qt.Key.Key_Down)

    assert surface.cursor_position in {1, 2}
    second_line = _projection_lines(surface)[1]
    caret_rect = harness.assert_caret_valid(
        "down from first blank to indented blank",
    )
    assert caret_rect.top() == pytest.approx(second_line.top, abs=1.0)


def test_projection_surface_caret_placement_harness_preserves_soft_wrap_edges(
    widgets: list[QWidget],
) -> None:
    """Right-arrow movement should cross a soft-wrap edge before advancing text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz",
        width=142,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )
    assert wrap_position > 0

    harness.set_cursor(wrap_position - 1)
    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position
    harness.assert_caret_at_line_start(right_line_index, "right across soft-wrap edge")

    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position + 1
    caret_rect = harness.assert_caret_valid("right after soft-wrap edge")
    right_line = _projection_lines(surface)[right_line_index]
    assert caret_rect.top() == pytest.approx(right_line.top, abs=1.0)
    assert caret_rect.left() > harness.content_left
    assert left_line_index + 1 == right_line_index


def test_projection_surface_caret_placement_harness_backspace_at_soft_wrap_start(
    widgets: list[QWidget],
) -> None:
    """Backspace at a wrapped row start should leave one unambiguous caret position."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="abcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyz",
        width=142,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    surface = harness.surface
    left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )

    harness.set_cursor(wrap_position - 1)
    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position
    harness.assert_caret_at_line_start(
        right_line_index,
        "initial visual start of wrapped row",
    )

    harness.key(Qt.Key.Key_Backspace)

    assert surface.cursor_position == wrap_position - 1
    caret_rect = harness.assert_caret_has_no_stale_visual_override(
        "after Backspace at soft-wrap row start",
    )
    lines = _projection_lines(surface)
    caret_line_index = harness._line_index_for_rect(caret_rect)
    assert caret_line_index is not None
    assert caret_line_index in {left_line_index, right_line_index}

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    right_rect = harness.assert_caret_valid("right after soft-wrap Backspace")
    right_line_after_index = harness._line_index_for_rect(right_rect)
    assert surface.cursor_position == wrap_position
    assert right_line_after_index is not None
    assert lines


def test_projection_surface_caret_placement_harness_right_arrow_visits_soft_wrap_start(
    widgets: list[QWidget],
) -> None:
    """Right arrow should visit a wrapped row start before the next character."""

    box = show_prompt_editor(
        widgets,
        text=(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon"
        ),
        width=150,
    )
    harness = _CaretPlacementHarness(box, app=ensure_qapp(), inset=32.0)
    surface = harness.surface
    _left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )

    harness.set_cursor(wrap_position - 1)
    harness.key(Qt.Key.Key_Right)
    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Right)

    assert surface.cursor_position == wrap_position
    harness.assert_caret_at_line_start(
        right_line_index,
        "right arrow should visit wrapped row start",
    )


def test_projection_surface_caret_placement_harness_repeated_soft_wrap_start_backspace(
    widgets: list[QWidget],
) -> None:
    """Repeated Backspace at wrapped row starts should not retain stale affinity."""

    box = show_prompt_editor(
        widgets,
        text=(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon"
        ),
        width=150,
    )
    harness = _CaretPlacementHarness(box, app=ensure_qapp(), inset=32.0)
    surface = harness.surface

    for iteration in range(12):
        _left_line_index, right_line_index, wrap_position = (
            harness.soft_wrap_transition_pair()
        )
        harness.set_visual_line_start_from_layout_hit(right_line_index)
        assert surface.cursor_position == wrap_position
        harness.assert_caret_at_line_start(
            right_line_index,
            f"iteration {iteration} wrapped row start",
        )

        harness.key(Qt.Key.Key_Backspace)

        assert surface.cursor_position == wrap_position - 1
        harness.assert_caret_has_no_stale_visual_override(
            f"iteration {iteration} after soft-wrap start Backspace",
        )


def test_projection_surface_caret_placement_harness_left_after_soft_wrap_start_backspace(
    widgets: list[QWidget],
) -> None:
    """Left after a soft-wrap-start Backspace should leave the wrap boundary."""

    box = show_prompt_editor(
        widgets,
        text=(
            "alphabetagamma delta epsilon zeta eta theta iota kappa lambda "
            "mu nu xi omicron pi rho sigma tau upsilon"
        ),
        width=110,
    )
    harness = _CaretPlacementHarness(box, app=ensure_qapp(), inset=32.0)
    surface = harness.surface
    _left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )
    harness.set_visual_line_start_from_layout_hit(right_line_index)

    assert surface.cursor_position == wrap_position

    harness.key(Qt.Key.Key_Backspace)
    after_backspace_position = surface.cursor_position

    harness.key(Qt.Key.Key_Left)

    assert surface.cursor_position == after_backspace_position - 1
    harness.assert_caret_has_no_stale_visual_override(
        "left after soft-wrap-start Backspace",
    )


def test_projection_surface_caret_placement_harness_survives_mixed_edit_navigation(
    widgets: list[QWidget],
) -> None:
    """Caret placement should survive interleaved edits, clicks, and navigation."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=(
            "alpha beta gamma delta epsilon\n"
            "zeta eta theta iota kappa lambda\n"
            "mu nu xi omicron pi rho sigma"
        ),
        width=180,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)

    harness.set_cursor(len("alpha beta gamma"))
    harness.key(Qt.Key.Key_Return)
    harness.type_text("x")
    harness.key(Qt.Key.Key_Left)
    harness.key(Qt.Key.Key_Right)
    harness.key(Qt.Key.Key_Backspace)
    harness.key(Qt.Key.Key_Backspace)

    first_newline = box.toPlainText().index("\n")
    harness.set_cursor(first_newline + 1)
    harness.click_visual_line_start(1)
    harness.key(Qt.Key.Key_Down)
    harness.key(Qt.Key.Key_Up)

    left_line_index, right_line_index, wrap_position = (
        harness.soft_wrap_transition_pair()
    )
    harness.set_cursor(max(0, wrap_position - 1))
    harness.key(Qt.Key.Key_Right)
    harness.key(Qt.Key.Key_Right)
    harness.assert_caret_at_line_start(
        right_line_index,
        "mixed sequence soft-wrap transition",
    )
    assert left_line_index + 1 == right_line_index


@pytest.mark.parametrize("seed", [7, 19, 41])
def test_projection_surface_caret_placement_harness_random_edit_navigation_stress(
    widgets: list[QWidget],
    seed: int,
) -> None:
    """Random edit/navigation stress should never place caret in the left margin."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=("alpha beta gamma\ndelta epsilon zeta eta theta\niota kappa lambda mu"),
        width=170,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    rng = random.Random(seed)
    operations: list[str] = []

    for step_index in range(120):
        operations.append(
            harness.random_stress_step(rng=rng, step_index=step_index),
        )

    assert operations


@pytest.mark.parametrize("seed", [11, 23, 37])
def test_projection_surface_caret_placement_harness_random_edit_down_navigation_stress(
    widgets: list[QWidget],
    seed: int,
) -> None:
    """Random edits should not strand Down navigation above lower visual lines."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=("alpha beta gamma\nfajsklfajfkla\n "),
        width=170,
    )
    harness = _CaretPlacementHarness(box, app=app, inset=32.0)
    rng = random.Random(seed)

    for step_index in range(80):
        harness.random_stress_step(rng=rng, step_index=step_index)
        if step_index % 5 == 0:
            harness.assert_down_moves_when_lower_visual_line_exists(
                f"random_down_stress({seed}, {step_index})",
            )


def test_projection_surface_click_empty_space_keeps_short_line_affinity(
    widgets: list[QWidget],
) -> None:
    """Clicking past short line text should place the caret at that line's end."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="short row\na very long row with a lot of text on it",
        width=360,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    click_point = QPoint(
        surface.viewport().width() - 12,
        int(first_line.top + (first_line.height / 2.0)),
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    caret_rect = box.cursorRect()
    expected_rect = first_line.caret_stops[-1].rect
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)
    assert caret_rect.y() < second_line.top


def test_projection_surface_click_wrapped_trailing_edge_keeps_visual_row(
    widgets: list[QWidget],
) -> None:
    """Clicking a wrapped row's right edge should not jump to next-row leading x."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    click_point = QPoint(
        surface.viewport().width() - 8,
        int(first_line.top + (first_line.height / 2.0)),
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    caret_rect = box.cursorRect()
    expected_rect = first_line.caret_stops[-1].rect
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)
    assert caret_rect.y() < second_line.top


def test_projection_surface_click_wrapped_leading_edge_uses_clicked_row(
    widgets: list[QWidget],
) -> None:
    """Clicking the next wrapped row's left edge should keep that row affinity."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    _, second_line = _projection_lines(surface)[:2]
    expected_rect = second_line.caret_stops[0].rect
    click_point = QPoint(
        int(expected_rect.x() + 1.0),
        int(second_line.top + (second_line.height / 2.0)),
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    caret_rect = box.cursorRect()
    assert surface.cursor_position == second_line.source_content_start
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)


def test_projection_surface_inside_text_click_preserves_boundary_precision(
    widgets: list[QWidget],
) -> None:
    """Clicking inside text should still use the nearest glyph boundary."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=240,
    )
    surface = surface_for(box)
    expected_position = 3
    expected_rect = surface._layout.cursor_rect(  # noqa: SLF001
        surface.projection_document().caret_map.state_for_source_position(
            expected_position
        ),
        scroll_offset=0.0,
    )

    QTest.mouseClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=expected_rect.center().toPoint(),
    )
    process_events(app)

    caret_rect = box.cursorRect()
    assert surface.cursor_position == expected_position
    assert caret_rect.x() == pytest.approx(expected_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(expected_rect.y(), abs=1.0)


def test_projection_surface_right_arrow_steps_through_wrapped_row_boundary(
    widgets: list[QWidget],
) -> None:
    """Right arrow should visit both visual stops at a soft-wrap boundary."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    start_position = first_line.source_content_end - 1
    surface.set_cursor_positions(
        cursor_position=start_position,
        anchor_position=start_position,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    first_edge_rect = first_line.caret_stops[-1].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(first_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(first_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    second_edge_rect = second_line.caret_stops[0].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == second_line.source_content_start
    assert caret_rect.x() == pytest.approx(second_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(second_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert surface.cursor_position == second_line.source_content_start + 1


def test_projection_surface_left_arrow_steps_through_wrapped_row_boundary(
    widgets: list[QWidget],
) -> None:
    """Left arrow should visit both visual stops at a soft-wrap boundary."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        width=180,
    )
    surface = surface_for(box)
    first_line, second_line = _projection_lines(surface)[:2]
    start_position = second_line.source_content_start + 1
    surface.set_cursor_positions(
        cursor_position=start_position,
        anchor_position=start_position,
    )
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    second_edge_rect = second_line.caret_stops[0].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == second_line.source_content_start
    assert caret_rect.x() == pytest.approx(second_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(second_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    first_edge_rect = first_line.caret_stops[-1].rect
    caret_rect = box.cursorRect()
    assert surface.cursor_position == first_line.source_content_end
    assert caret_rect.x() == pytest.approx(first_edge_rect.x(), abs=1.0)
    assert caret_rect.y() == pytest.approx(first_edge_rect.y(), abs=1.0)

    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    assert surface.cursor_position == first_line.source_content_end - 1


def test_projection_surface_arrow_navigation_flushes_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact keyboard navigation should flush pending projection work first."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    _delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    _flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    QTest.keyClick(box, Qt.Key.Key_Left)

    assert surface.has_pending_projection_update() is False
    assert rebuild_count == 0


def test_projection_surface_vertical_navigation_preserves_pending_stale_safe_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vertical arrows should not synchronously flush stale-safe typing projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), \nbeta",
        width=240,
    )
    surface = surface_for(box)
    _delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    _flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    flush_calls: list[str] = []

    def record_flush(*, reason: str) -> None:
        """Record an unexpected synchronous projection flush."""

        flush_calls.append(reason)

    monkeypatch.setattr(surface, "_flush_pending_projection_update", record_flush)

    QTest.keyClick(box, Qt.Key.Key_Up)

    assert flush_calls == []
    assert surface.has_pending_projection_update() is True


def test_projection_surface_focused_caret_starts_visible(
    widgets: list[QWidget],
) -> None:
    """Focusing the prompt editor should show the custom caret immediately."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    _restart_surface_caret_blink_cycle(box)

    _wait_for_surface_caret_state(box, expected=True)


def test_projection_surface_owns_actual_focus_for_prompt_editor_facade(
    widgets: list[QWidget],
) -> None:
    """Prompt editor focus should resolve to the projection surface, not QTextEdit."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    surface = surface_for(box)
    process_events(app)

    assert box.hasFocus() is True
    assert surface.hasFocus() is True
    assert app.focusWidget() is surface


def test_projection_surface_caret_blinks_after_half_cycle(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The custom caret should toggle visibility using the surface flash-time seam."""

    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: 40,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    _restart_surface_caret_blink_cycle(box)

    _wait_for_surface_caret_state(box, expected=True)

    _wait_for_surface_caret_state(box, expected=False)
    _wait_for_surface_caret_state(box, expected=True)


def test_projection_surface_caret_move_resets_blink_to_visible(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moving the caret should make the custom caret visible immediately again."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: 40,
    )
    box = show_prompt_editor(
        widgets,
        text="ab",
        width=220,
    )
    surface_for(box).set_cursor_positions(
        cursor_position=0,
        anchor_position=0,
    )
    process_events(app)

    _wait_for_surface_caret_state(box, expected=False)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert _surface_should_paint_caret(box) is True


def test_projection_surface_selection_hides_caret(
    widgets: list[QWidget],
) -> None:
    """A non-empty selection should suppress custom caret painting."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=220,
    )
    surface = surface_for(box)

    surface.set_cursor_positions(
        cursor_position=5,
        anchor_position=0,
    )
    process_events(app)

    assert _surface_should_paint_caret(box) is False


def test_projection_surface_collapsing_selection_restores_caret(
    widgets: list[QWidget],
) -> None:
    """Collapsing an existing selection should restore custom caret painting."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=220,
    )
    surface = surface_for(box)

    surface.set_cursor_positions(
        cursor_position=5,
        anchor_position=0,
    )
    process_events(app)
    assert _surface_should_paint_caret(box) is False

    surface.set_cursor_positions(
        cursor_position=5,
        anchor_position=5,
    )
    process_events(app)

    assert _surface_should_paint_caret(box) is True


def test_projection_surface_text_edit_resets_blink_to_visible(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing should make the custom caret visible immediately again."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: 40,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )

    _wait_for_surface_caret_state(box, expected=False)

    QTest.keyClicks(box, "a")
    process_events(app)

    _wait_for_surface_caret_state(box, expected=True)


def test_projection_surface_focus_loss_hides_caret(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Losing focus should stop painting the custom caret immediately."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: 40,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    other = QWidget()
    other.resize(120, 80)
    other.show()
    other.activateWindow()
    other.raise_()
    other.setFocus()
    widgets.append(other)
    process_events(app)

    assert _surface_should_paint_caret(box) is False


def test_projection_surface_non_blinking_setting_keeps_caret_visible(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disabled system blink setting should keep the custom caret continuously visible."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: 0,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    surface = surface_for(box)

    QTest.qWait(80)
    process_events(app)

    assert _surface_should_paint_caret(box) is True
    assert surface._caret_visual_controller.blink_timer.isActive() is False  # noqa: SLF001
