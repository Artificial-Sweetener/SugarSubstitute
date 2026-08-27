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

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication, QSplitter, QWidget
from qfluentwidgets import BodyLabel  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from substitute.presentation.shell.comfy_output_panel import ComfyOutputPanel
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.fixture(scope="module", autouse=True)
def comfy_output_qt_application() -> Iterator[QApplication]:
    """Keep one process-local Qt application alive for panel tests."""

    application = ensure_qt_application()
    yield application


@pytest.fixture
def owned_qt_objects() -> Iterator[list[QObject]]:
    """Destroy every native Qt owner created by the current test."""

    objects: list[QObject] = []
    yield objects
    for candidate in reversed(objects):
        destroy_qt_object(candidate)


def test_output_panel_replays_history_wraps_lines_and_hides_cleanly(
    owned_qt_objects: list[QObject],
) -> None:
    """The shell output panel should replay bounded history without extra blank rows."""

    stream = TerminalOutputStream(max_lines=3)
    stream.append_lines(("first\n", "", "second", "third", "fourth"))
    panel = ComfyOutputPanel(panel_height=190)
    owned_qt_objects.append(panel)

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

    assert panel.log_view.toPlainText().splitlines() == ["third", "fourth", "fifth"]

    panel.set_panel_visible(False)
    assert panel.is_panel_visible() is False
    assert panel.height() == 0


def test_output_panel_preserves_interleaved_progress_and_fetch_lines(
    owned_qt_objects: list[QObject],
) -> None:
    """The shell panel should keep stable fetch logs distinct from progress redraws."""

    stream = TerminalOutputStream(max_lines=10)
    panel = ComfyOutputPanel(panel_height=190)
    owned_qt_objects.append(panel)
    panel.resize(420, 190)
    panel.set_stream(stream)
    panel.set_panel_visible(True)
    panel.show()
    panel.ensurePolished()

    stream.append_lines(
        (
            "  0%|          | 0/28 [00:00<?, ?it/s]\r",
            "FETCH ComfyRegistry Data: 25/134\n",
            " 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r",
            "FETCH ComfyRegistry Data: 30/134\n",
            "100%|| 28/28 [00:04<00:00,  6.50it/s]\n",
        )
    )
    assert panel.log_view.toPlainText().splitlines() == [
        "FETCH ComfyRegistry Data: 25/134",
        "FETCH ComfyRegistry Data: 30/134",
        "100%|| 28/28 [00:04<00:00,  6.50it/s]",
    ]
    scrollbar = panel.log_view.verticalScrollBar()
    wait_for_qt_condition(lambda: scrollbar.value() == scrollbar.maximum())
    assert scrollbar.value() == scrollbar.maximum()


def test_output_panel_supports_vertical_splitter_resizing(
    owned_qt_objects: list[QObject],
) -> None:
    """The shell output panel should resize vertically inside its host splitter."""

    splitter = QSplitter(Qt.Orientation.Vertical)
    owned_qt_objects.append(splitter)
    top = QWidget()
    panel = ComfyOutputPanel(panel_height=190)
    splitter.addWidget(top)
    splitter.addWidget(panel)
    splitter.resize(480, 420)
    panel.set_panel_visible(True)
    splitter.show()
    splitter.ensurePolished()
    wait_for_qt_condition(lambda: panel.isVisible() and panel.height() > 0)

    initial_height = panel.height()
    splitter.setSizes([180, 240])
    wait_for_qt_condition(lambda: panel.height() > initial_height)
    expanded_height = panel.height()
    splitter.setSizes([260, 140])
    wait_for_qt_condition(lambda: panel.height() < expanded_height)

    assert expanded_height > initial_height
    assert panel.height() < expanded_height
