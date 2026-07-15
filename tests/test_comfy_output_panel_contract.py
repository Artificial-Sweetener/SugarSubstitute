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

"""Contract tests for the shell-owned Comfy output stream and panel."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSplitter, QWidget
from qfluentwidgets import BodyLabel  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_transcript import (
    TerminalOutputTranscript,
)
from substitute.presentation.shell.comfy_output_panel import ComfyOutputPanel


def _app() -> QApplication:
    """Return the shared QApplication used by widget contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, *, cycles: int = 5) -> None:
    """Flush a few Qt event turns so deferred layout work can settle."""

    for _ in range(cycles):
        app.processEvents()


def test_output_stream_normalizes_and_bounds_history() -> None:
    """The shell output stream should drop blank lines and retain bounded history."""

    stream = TerminalOutputStream(max_lines=3)

    stream.append_lines(("first\n", "", "  ", "second", "third"))
    stream.append_line("fourth\r\n")

    assert stream.snapshot() == ("second", "third", "fourth")


def test_output_stream_replaces_active_line_for_carriage_return_updates() -> None:
    """The shell output stream should redraw the active line for progress records."""

    stream = TerminalOutputStream(max_lines=3)

    stream.append_line("  0%|          | 0/28 [00:00<?, ?it/s]\r")
    stream.append_line(" 50%|#####     | 14/28 [00:02<00:02,  5.08it/s]\r")
    stream.append_line("100%|##########| 28/28 [00:05<00:00,  5.47it/s]\n")

    assert stream.snapshot() == ("100%|##########| 28/28 [00:05<00:00,  5.47it/s]",)


def test_output_panel_replays_history_wraps_lines_and_hides_cleanly() -> None:
    """The shell output panel should replay bounded history without extra blank rows."""

    app = _app()
    stream = TerminalOutputStream(max_lines=3)
    stream.append_lines(("first\n", "", "second", "third", "fourth"))
    panel = ComfyOutputPanel(panel_height=190)

    panel.set_stream(stream)
    assert panel.is_panel_visible() is False
    assert panel.height() == 0
    header = panel.findChild(QWidget, "ComfyOutputHeader")
    title = panel.findChild(BodyLabel, "ComfyOutputTitle")
    assert header is not None
    assert title is not None
    assert title.text() == "Comfy Console"
    assert "background: transparent;" in panel.styleSheet()
    assert (
        panel.log_view.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert panel.log_view.lineWrapMode() == panel.log_view.LineWrapMode.WidgetWidth
    assert panel.log_view.toPlainText().splitlines() == ["second", "third", "fourth"]

    panel.set_panel_visible(True)
    assert panel.is_panel_visible() is True
    assert panel.height() == 190

    stream.append_line("fifth")
    app.processEvents()

    assert panel.log_view.toPlainText().splitlines() == ["third", "fourth", "fifth"]

    panel.set_panel_visible(False)
    assert panel.is_panel_visible() is False
    assert panel.height() == 0


def test_terminal_output_transcript_finalizes_carriage_return_line_on_crlf() -> None:
    """Terminal transcript should finalize the active redraw line on ``\\r\\n``."""

    transcript = TerminalOutputTranscript(max_lines=5)

    assert transcript.apply_record("step 1\r") is not None
    assert transcript.apply_record("step 2\r") is not None
    assert transcript.apply_record("done\r\n") is not None

    assert transcript.snapshot() == ("done",)


def test_output_panel_preserves_interleaved_progress_and_fetch_lines() -> None:
    """The shell panel should keep stable fetch logs distinct from progress redraws."""

    app = _app()
    stream = TerminalOutputStream(max_lines=10)
    panel = ComfyOutputPanel(panel_height=190)
    panel.resize(420, 190)
    panel.set_stream(stream)
    panel.set_panel_visible(True)
    panel.show()
    _process_events(app)

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

    assert panel.log_view.toPlainText().splitlines() == [
        "FETCH ComfyRegistry Data: 25/134",
        "FETCH ComfyRegistry Data: 30/134",
        "100%|| 28/28 [00:04<00:00,  6.50it/s]",
    ]
    scrollbar = panel.log_view.verticalScrollBar()
    assert scrollbar.value() == scrollbar.maximum()

    panel.close()


def test_output_panel_supports_vertical_splitter_resizing() -> None:
    """The shell output panel should resize vertically inside its host splitter."""

    app = _app()
    splitter = QSplitter(Qt.Orientation.Vertical)
    top = QWidget()
    panel = ComfyOutputPanel(panel_height=190)
    splitter.addWidget(top)
    splitter.addWidget(panel)
    splitter.resize(480, 420)
    panel.set_panel_visible(True)
    splitter.show()
    _process_events(app)

    initial_height = panel.height()
    splitter.setSizes([180, 240])
    _process_events(app)
    expanded_height = panel.height()
    splitter.setSizes([260, 140])
    _process_events(app)

    assert expanded_height > initial_height
    assert panel.height() < expanded_height

    splitter.close()
