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

"""Contract tests for the shared terminal output view widget."""

from __future__ import annotations

import os
from typing import cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_style import (
    build_terminal_output_stylesheet,
)
from sugarsubstitute_shared.presentation.terminal.output_view import TerminalOutputView

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "terminal output Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )

_MAX_BOTTOM_CHROME_GAP_PX = 6


def _app() -> QApplication:
    """Return the shared QApplication used by terminal view tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, *, cycles: int = 5) -> None:
    """Flush a few Qt event turns so deferred layout and timers can settle."""

    for _ in range(cycles):
        app.processEvents()


def _dispose_view(app: QApplication, view: TerminalOutputView) -> None:
    """Close and delete one terminal view deterministically for Qt worker stability."""

    view.close()
    view.deleteLater()
    _process_events(app)


def _wrapped_terminal_line(index: int) -> str:
    """Build one long terminal record that reliably wraps in narrow views."""

    return f"{index:02d}: wrapped output " + ("0123456789 " * 20)


def _end_of_document_bottom_gap(view: TerminalOutputView) -> int:
    """Measure the rendered gap between the final caret row and viewport bottom."""

    cursor = view.log_view.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor_rect = view.log_view.cursorRect(cursor)
    viewport_rect = view.log_view.viewport().rect()
    return int(viewport_rect.bottom() - cursor_rect.bottom())


def _document_fragments(view: TerminalOutputView) -> list[tuple[str, str | None, bool]]:
    """Return visible document fragments as text, foreground color, and bold state."""

    fragments: list[tuple[str, str | None, bool]] = []
    block = view.log_view.document().firstBlock()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.text():
                text_format = fragment.charFormat()
                foreground = text_format.foreground()
                color = foreground.color().name() if foreground.style() else None
                fragments.append(
                    (
                        fragment.text(),
                        color,
                        text_format.font().bold(),
                    )
                )
            iterator += 1
        block = block.next()
    return fragments


def test_terminal_output_view_is_one_surface_without_header_chrome() -> None:
    """The shared terminal view should render as one terminal surface only."""

    app = _app()
    view = TerminalOutputView()
    header = view.findChild(QWidget, "TerminalOutputHeader")

    assert view.findChild(type(view.log_view)) is view.log_view
    assert header is None

    _dispose_view(app, view)


def test_terminal_output_view_replays_stream_history_and_redraws_in_place() -> None:
    """Binding a stream should replay history and honor in-place redraw records."""

    app = _app()
    stream = TerminalOutputStream(max_lines=4)
    stream.append_line("booting\n")
    stream.append_line("0%\r")
    stream.append_line("100%\n")
    view = TerminalOutputView()

    view.set_stream(stream)
    app.processEvents()

    assert view.log_view.toPlainText().splitlines() == ["booting", "100%"]

    _dispose_view(app, view)


def test_terminal_output_view_renders_ansi_sgr_spans_from_stream_history() -> None:
    """Binding stream history should render ANSI SGR without showing escape bytes."""

    app = _app()
    stream = TerminalOutputStream(max_lines=4)
    stream.append_line("\x1b[32m[INFO]\x1b[0m Using pytorch attention\n")
    view = TerminalOutputView()

    view.set_stream(stream)
    app.processEvents()

    assert view.log_view.toPlainText() == "[INFO] Using pytorch attention"
    fragments = _document_fragments(view)
    assert fragments[0] == ("[INFO]", "#33d17a", False)
    assert fragments[1][0] == " Using pytorch attention"
    assert fragments[1][1] != "#33d17a"

    _dispose_view(app, view)


def test_terminal_output_view_copy_and_clear_actions_operate_on_bound_stream() -> None:
    """Copy and clear actions should reflect the rendered terminal transcript."""

    app = _app()
    stream = TerminalOutputStream(max_lines=4)
    view = TerminalOutputView()
    view.set_stream(stream)
    view.append_line("first\n")
    view.append_line("second\n")
    app.processEvents()

    view.copy_all_output()
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text().splitlines() == ["first", "second"]

    view.clear_output()
    app.processEvents()

    assert stream.snapshot() == ()
    assert view.log_view.toPlainText() == ""

    _dispose_view(app, view)


def test_terminal_output_view_applies_shared_terminal_style() -> None:
    """The shared terminal view should own the terminal surface stylesheet."""

    app = _app()
    view = TerminalOutputView()

    assert "QFrame#TerminalOutputView" in view.styleSheet()
    assert "{{" not in view.styleSheet()
    assert view.styleSheet() == build_terminal_output_stylesheet()
    assert "PlainTextEdit#TerminalOutputLog" in view.log_view.styleSheet()
    assert view.log_view.viewport().objectName() == "TerminalOutputViewport"
    assert "background-color: transparent;" in view.log_view.styleSheet()
    assert view.log_view.cursorWidth() == 0

    _dispose_view(app, view)


def test_terminal_output_view_uses_fixed_pitch_terminal_font() -> None:
    """The shared terminal view should use a terminal-friendly fixed-width font."""

    app = _app()
    view = TerminalOutputView()
    font = view.log_view.font()

    assert font.fixedPitch() is True
    assert font.styleHint() is QFont.StyleHint.TypeWriter
    assert font.pointSize() == 9

    _dispose_view(app, view)


def test_terminal_output_view_disables_qfluent_smooth_scrolling() -> None:
    """The shared terminal view should disable QFluent wheel smoothing."""

    app = _app()
    view = TerminalOutputView()
    scroll_delegate = view.log_view.scrollDelegate

    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0

    _dispose_view(app, view)


def test_terminal_output_view_stays_inside_layout_contents() -> None:
    """The terminal surface should not overflow a parent card's content rect."""

    app = _app()
    parent = QWidget()
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(0)
    view = TerminalOutputView(
        parent,
        min_height=220,
        max_height=220,
    )
    layout.addWidget(view)
    parent.resize(560, 300)
    parent.show()
    _process_events(app)

    view_bottom_right = view.geometry().bottomRight()
    parent_contents = parent.contentsRect().adjusted(22, 20, -22, -20)
    assert parent_contents.contains(view.geometry().topLeft())
    assert parent_contents.contains(view_bottom_right)

    view_contents = view.contentsRect()
    log_bottom_right = view.log_view.geometry().bottomRight()
    assert view_contents.contains(view.log_view.geometry().topLeft())
    assert view_contents.contains(log_bottom_right)
    assert (
        view.log_view.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )

    parent.close()
    parent.deleteLater()
    _process_events(app)


def test_terminal_output_view_stays_pinned_to_bottom_for_wrapped_stream_output() -> (
    None
):
    """Shared output should follow the newest wrapped lines without a false blank row."""

    app = _app()
    stream = TerminalOutputStream(max_lines=200)
    view = TerminalOutputView(
        min_height=120,
        max_height=120,
    )
    view.resize(260, 120)
    view.set_stream(stream)
    view.show()
    _process_events(app)

    for index in range(25):
        stream.append_line(_wrapped_terminal_line(index) + "\n")
    _process_events(app)

    scrollbar = view.log_view.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()
    assert view.log_view.toPlainText().splitlines()[-1] == _wrapped_terminal_line(24)
    assert view.log_view.toPlainText().endswith("\n") is False
    assert _end_of_document_bottom_gap(view) <= _MAX_BOTTOM_CHROME_GAP_PX

    _dispose_view(app, view)


def test_terminal_output_view_stays_pinned_to_bottom_when_history_replays_on_show() -> (
    None
):
    """Shared output should replay wrapped history without a false blank row."""

    app = _app()
    stream = TerminalOutputStream(max_lines=200)
    view = TerminalOutputView(
        min_height=120,
        max_height=120,
    )
    view.resize(260, 120)
    view.set_stream(stream)

    for index in range(25):
        stream.append_line(_wrapped_terminal_line(index) + "\n")

    view.show()
    _process_events(app)

    scrollbar = view.log_view.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()
    assert view.log_view.toPlainText().splitlines()[-1] == _wrapped_terminal_line(24)
    assert view.log_view.toPlainText().endswith("\n") is False
    assert _end_of_document_bottom_gap(view) <= _MAX_BOTTOM_CHROME_GAP_PX

    _dispose_view(app, view)


def test_terminal_output_view_updates_interleaved_progress_without_full_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Steady-state mixed progress updates should avoid full document replacement."""

    app = _app()
    stream = TerminalOutputStream(max_lines=10)
    view = TerminalOutputView(
        min_height=120,
        max_height=120,
    )
    view.resize(320, 120)
    view.set_stream(stream)
    view.show()
    _process_events(app)

    set_plain_text_calls: list[str] = []
    original_set_plain_text = view.log_view.setPlainText

    def _recording_set_plain_text(text: str) -> None:
        set_plain_text_calls.append(text)
        original_set_plain_text(text)

    monkeypatch.setattr(view.log_view, "setPlainText", _recording_set_plain_text)

    stream.append_lines(
        (
            "  0%|          | 0/28 [00:00<?, ?it/s]\r",
            "FETCH ComfyRegistry Data: 25/134\n",
            " 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r",
            "FETCH ComfyRegistry Data: 30/134\n",
            "100%|| 28/28 [00:04<00:00,  6.50it/s]\n",
        )
    )
    _process_events(app)

    assert set_plain_text_calls == []
    assert view.log_view.toPlainText().splitlines() == [
        "FETCH ComfyRegistry Data: 25/134",
        "FETCH ComfyRegistry Data: 30/134",
        "100%|| 28/28 [00:04<00:00,  6.50it/s]",
    ]
    scrollbar = view.log_view.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()

    _dispose_view(app, view)


def test_terminal_output_view_direct_append_uses_shared_progress_semantics() -> None:
    """Direct append mode should share the same redraw semantics as bound streams."""

    app = _app()
    view = TerminalOutputView()

    view.append_line("0%\r")
    view.append_line("FETCH ComfyRegistry Data: 25/134\n")
    view.append_line("100%\n")
    app.processEvents()

    assert view.log_view.toPlainText().splitlines() == [
        "FETCH ComfyRegistry Data: 25/134",
        "100%",
    ]

    _dispose_view(app, view)
