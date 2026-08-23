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

"""Verify queue panel and dropdown composition through real Qt surfaces."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QLayout, QWidget

from qfluentwidgets.components.material import AcrylicFlyout  # type: ignore[import-untyped]

from substitute.presentation.generation.queue_dropdown import (
    GenerationQueueDropdown,
    GenerationQueueDropdownView,
)
from substitute.presentation.generation.queue_panel import GenerationQueuePanel
from tests.presentation.generation.queue.support import (
    RecordingQueueService,
    queue_job,
)
from tests.support.qt.lifecycle import destroy_qt_object


class _FlyoutBoundary(QObject):
    """Represent the external QFluent flyout host while retaining the real view."""

    closed = Signal()

    def __init__(self, view: GenerationQueueDropdownView) -> None:
        """Own the mounted queue view and visible state."""

        super().__init__()
        self.view = view
        self._visible = True

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether this flyout boundary is open."""

        return self._visible

    def close(self) -> None:
        """Close the boundary and publish the production close event."""

        self._visible = False
        self.closed.emit()


def _assert_direct_widget(layout: QLayout, index: int, widget: QWidget) -> None:
    """Assert one direct layout slot owns the expected widget."""

    item = layout.itemAt(index)
    assert item is not None and item.widget() is widget


def _assert_qfluent_smoothing_disabled(scroll_area: object) -> None:
    """Assert the queue surface uses deterministic native scroll delivery."""

    delegate = cast(Any, scroll_area).scrollDelagate
    assert delegate.useAni is False
    assert delegate.vScrollBar.duration == 0
    assert delegate.hScrollBar.duration == 0


def test_queue_panel_routes_shared_row_intents_and_disposes_observer() -> None:
    """Panel row commands must cross the queue-service boundary exactly once."""

    service = RecordingQueueService((queue_job("a", status="pending"),))
    opened: list[str] = []
    panel = GenerationQueuePanel(
        cast(Any, service),
        open_snapshot_requested=opened.append,
    )
    try:
        panel._rows_view.cancelRequested.emit("a")
        panel._rows_view.removeRequested.emit("a")
        panel._rows_view.moveRequested.emit("a", 0)
        panel._rows_view.openSnapshotRequested.emit("a")
        assert service.cancelled == ["a"]
        assert service.removed == ["a"]
        assert service.moved == [("a", 0)]
        assert opened == ["a"]
        _assert_qfluent_smoothing_disabled(panel._scroll_area)
        panel.dispose()
        assert service.observers == []
    finally:
        destroy_qt_object(panel)


def test_queue_panel_header_owns_title_count_hide_action_and_layout() -> None:
    """Header composition must expose pending count and the shell hide intent."""

    service = RecordingQueueService(
        (
            queue_job("pending", status="pending"),
            queue_job("running", status="running"),
            queue_job("completed", status="completed"),
            queue_job("cancelled", status="cancelled"),
        )
    )
    panel = GenerationQueuePanel(cast(Any, service))
    hide_spy = QSignalSpy(panel.hideRequested)
    try:
        layout = panel.layout()
        header_layout = panel._header.layout()
        assert layout is not None and header_layout is not None
        _assert_direct_widget(layout, 0, panel._header)
        _assert_direct_widget(header_layout, 0, panel._title_label)
        _assert_direct_widget(header_layout, 2, panel._hide_panel_button)
        assert panel._title_label.text() == "Generation Queue :: 1 Pending Jobs"
        assert panel._hide_panel_button.objectName() == "GenerationQueuePanelHideButton"
        assert panel._hide_panel_button.toolTip() == "Hide full queue panel"
        assert not panel._hide_panel_button.icon().isNull()
        assert not panel._hide_panel_button.iconSize().isEmpty()
        QTest.mouseClick(panel._hide_panel_button, Qt.MouseButton.LeftButton)
        assert hide_spy.count() == 1
    finally:
        panel.dispose()
        destroy_qt_object(panel)


def test_queue_panel_empty_state_uses_content_below_header() -> None:
    """Empty copy must occupy the stretch region without displacing the header."""

    service = RecordingQueueService()
    panel = GenerationQueuePanel(cast(Any, service))
    try:
        layout = panel.layout()
        empty_layout = panel._empty_state.layout()
        assert layout is not None and empty_layout is not None
        _assert_direct_widget(layout, 0, panel._header)
        _assert_direct_widget(layout, 1, panel._empty_state)
        _assert_direct_widget(empty_layout, 1, panel._empty_label)
        assert not panel._empty_state.isHidden()
        assert panel._scroll_area.isHidden()
        assert panel._empty_label.minimumHeight() == 88
    finally:
        panel.dispose()
        destroy_qt_object(panel)


def test_queue_dropdown_view_uses_same_empty_content_region() -> None:
    """Flyout empty state must match the panel's below-header composition."""

    view = GenerationQueueDropdownView()
    try:
        layout = view.layout()
        empty_layout = view._empty_state.layout()
        assert layout is not None and empty_layout is not None
        title = layout.itemAt(0).widget()
        assert title is not None and title.objectName() == "GenerationQueueTitle"
        _assert_direct_widget(layout, 1, view._empty_state)
        _assert_direct_widget(empty_layout, 1, view._empty_label)
        assert not view._empty_state.isHidden()
        assert view._scroll_area.isHidden()
        assert view._empty_label.minimumHeight() == 88
        _assert_qfluent_smoothing_disabled(view._scroll_area)
    finally:
        destroy_qt_object(view)


def test_queue_dropdown_toggles_and_routes_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropdown lifecycle must route commands and detach its observer on disposal."""

    service = RecordingQueueService((queue_job("a", status="pending"),))
    parent = QWidget()
    target = QWidget(parent)
    created: list[_FlyoutBoundary] = []

    def make_flyout(view: object, *_args: object) -> _FlyoutBoundary:
        """Mount the production view behind the external flyout boundary."""

        assert isinstance(view, GenerationQueueDropdownView)
        boundary = _FlyoutBoundary(view)
        created.append(boundary)
        return boundary

    monkeypatch.setattr(AcrylicFlyout, "make", make_flyout)
    dropdown = GenerationQueueDropdown(cast(Any, service), parent=parent)
    try:
        dropdown.toggle_for(target)
        assert dropdown.is_visible()
        view = created[-1].view
        view.cancelRequested.emit("a")
        view.removeRequested.emit("a")
        view.moveRequested.emit("a", 0)
        dropdown.toggle_for(target)
        assert service.cancelled == ["a"]
        assert service.removed == ["a"]
        assert service.moved == [("a", 0)]
        assert not dropdown.is_visible()
        dropdown.dispose()
        assert service.observers == []
    finally:
        destroy_qt_object(parent)
