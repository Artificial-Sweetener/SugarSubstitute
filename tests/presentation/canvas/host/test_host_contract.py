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

"""Exercise selector, chrome, availability, and docking through the real host."""

from __future__ import annotations

from collections.abc import Callable
from PySide6.QtCore import QRect, QTimer, Signal, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import Pivot, SegmentedItem  # type: ignore[import-untyped]
import pytest
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.workspace_state import (
    CanvasLayoutSnapshot,
    FloatingCanvasWindowSnapshot,
)
from substitute.presentation.canvas.host.canvas_host import CanvasHost
from substitute.presentation.canvas.host.canvas_host_selector import CanvasHostSelector
from substitute.presentation.canvas.host.canvas_host_state import CanvasHostPage
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Canvas(QWidget):
    """Record host ports used by generic canvas lifecycle tests."""

    dockActionRequested = Signal()

    def __init__(self) -> None:
        """Create a canvas with observable host projections."""

        super().__init__()
        self.chrome_obstacles: list[tuple[QRect, ...]] = []
        self.detached_states: list[bool] = []
        self.availability: list[tuple[bool, object]] = []

    def set_host_chrome_obstacles(self, obstacles: tuple[QRect, ...]) -> None:
        """Record host chrome geometry presented to this canvas."""

        self.chrome_obstacles.append(obstacles)

    def set_canvas_detached(self, detached: bool) -> None:
        """Record attachment state for context-menu presentation."""

        self.detached_states.append(detached)

    def set_available(self, available: bool, reason: object) -> None:
        """Record passive availability presentation."""

        self.availability.append((available, reason))


class _DefersFirstFocusCanvas(_Canvas):
    """Reject one focus request to model a target not ready in the activating event."""

    def __init__(self) -> None:
        """Create a canvas that records and accepts later focus verification."""

        super().__init__()
        self.focus_requests = 0

    def setFocus(  # noqa: N802
        self,
        reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason,
    ) -> None:
        """Accept focus after the first request without introducing wall-clock timing."""

        self.focus_requests += 1
        if self.focus_requests > 1:
            super().setFocus(reason)


class _FloatingWindow(QWidget):
    """Provide deterministic floating-window behavior for host docking tests."""

    layoutStateChanged = Signal()

    def __init__(
        self,
        canvas_widget: QWidget,
        label: str,
        redock_callback: Callable[[QWidget, str], None],
        **_kwargs: object,
    ) -> None:
        """Store the production redock boundary without native window effects."""

        super().__init__()
        self.canvas_widget = canvas_widget
        self.label = label
        self.redock_callback = redock_callback
        self.restored_snapshots: list[FloatingCanvasWindowSnapshot] = []

    def close(self) -> bool:
        """Invoke the production redock callback deterministically."""

        self.redock_callback(self.canvas_widget, self.label)
        return True

    def floating_canvas_snapshot(self) -> FloatingCanvasWindowSnapshot:
        """Return the durable snapshot used by host persistence tests."""

        return FloatingCanvasWindowSnapshot(label=self.label)

    def apply_restored_floating_snapshot(
        self,
        snapshot: FloatingCanvasWindowSnapshot,
    ) -> None:
        """Accept restored state for the host persistence contract."""

        self.restored_snapshots.append(snapshot)


def _app() -> QApplication:
    """Return the application used by real host widget tests."""

    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _host() -> tuple[CanvasHost, _Canvas, _Canvas]:
    """Create a shown two-canvas host with observable page ports."""

    _app()
    input_canvas = _Canvas()
    output_canvas = _Canvas()
    host = CanvasHost(
        pages=(
            CanvasHostPage("Input", app_text("Input"), input_canvas),
            CanvasHostPage("Output", app_text("Output"), output_canvas),
        )
    )
    host.show()
    _app().processEvents()
    return host, input_canvas, output_canvas


def test_host_uses_segmented_anchor_and_no_pivot_control() -> None:
    """The canvas selector should use Output's anchor primitive without a Pivot."""

    host, _input_canvas, _output_canvas = _host()
    try:
        selector = host.selector
        assert isinstance(selector, CanvasHostSelector)
        assert isinstance(selector.button, SegmentedItem)
        assert selector.isVisible()
        assert selector.surface.styleSheet() == floating_canvas_surface_stylesheet(
            "QLabel#CanvasHostSelectorSurface"
        )
        assert host.findChildren(Pivot) == []
        assert not hasattr(host, "pivot")
    finally:
        host.close()


def test_selector_switches_the_authoritative_stack_selection() -> None:
    """Selector choices should drive stack visibility through host state."""

    host, _input_canvas, _output_canvas = _host()
    activated: list[str] = []
    host.canvas_activated.connect(activated.append)
    try:
        host.activate_canvas("Output", keyboard_focus=False)
        _app().processEvents()

        selector = host.selector
        assert isinstance(selector, CanvasHostSelector)
        assert selector.button.text() == "Output"
        assert host.is_canvas_visible("Output")
        assert not host.is_canvas_visible("Input")
        assert activated == ["Output"]
    finally:
        host.close()


def test_host_activation_can_transfer_keyboard_focus_to_selected_canvas() -> None:
    """Explicit editing activation must select and focus the requested canvas."""

    host, input_canvas, output_canvas = _host()
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocus()
        _app().processEvents()

        assert host.activate_canvas("Input", keyboard_focus=True)
        _app().processEvents()

        assert host.is_canvas_visible("Input")
        assert input_canvas.hasFocus()
    finally:
        host.close()


def test_host_activation_verifies_focus_after_current_event_dispatch() -> None:
    """Activation must recover when its first synchronous focus request is rejected."""

    _app()
    input_canvas = _DefersFirstFocusCanvas()
    output_canvas = _Canvas()
    host = CanvasHost(
        pages=(
            CanvasHostPage("Input", app_text("Input"), input_canvas),
            CanvasHostPage("Output", app_text("Output"), output_canvas),
        )
    )
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        host.show()
        wait_for_qt_condition(host.isVisible)
        assert input_canvas.focus_requests == 0

        assert host.activate_canvas("Input", keyboard_focus=True)
        assert input_canvas.focus_requests == 1
        wait_for_qt_condition(input_canvas.hasFocus)

        assert input_canvas.focus_requests >= 2
    finally:
        host.close()


def test_deferred_focus_does_not_override_a_newer_canvas_activation() -> None:
    """A queued pointer-event handoff must not focus a superseded route."""

    host, input_canvas, output_canvas = _host()
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocus()
        _app().processEvents()

        assert host.activate_canvas("Input", keyboard_focus=True)
        assert host.activate_canvas("Output", keyboard_focus=False)
        _app().processEvents()

        assert host.is_canvas_visible("Output")
        assert output_canvas.hasFocus()
    finally:
        host.close()


def test_activation_focus_settles_after_nested_same_event_projections() -> None:
    """Nested toolbar projections must not steal picker-requested canvas focus."""

    host, input_canvas, output_canvas = _host()
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocus()
        _app().processEvents()

        host.canvas_activated.connect(
            lambda _route_key: QTimer.singleShot(
                0,
                lambda: QTimer.singleShot(
                    0,
                    lambda: QTimer.singleShot(0, output_canvas.setFocus),
                ),
            )
        )

        assert host.activate_canvas("Input", keyboard_focus=True)
        wait_for_qt_condition(input_canvas.hasFocus)

        assert input_canvas.hasFocus()
    finally:
        host.close()


def test_activation_focus_recovers_after_projection_temporarily_clears_focus() -> None:
    """A transient focusless projection must preserve picker-requested focus."""

    host, input_canvas, output_canvas = _host()
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        output_canvas.setFocus()
        wait_for_qt_condition(output_canvas.hasFocus)

        assert host.activate_canvas("Input", keyboard_focus=True)
        wait_for_qt_condition(input_canvas.hasFocus)

        input_canvas.clearFocus()
        wait_for_qt_condition(input_canvas.hasFocus)
    finally:
        host.close()


def test_activation_focus_restores_before_projection_transfer_returns() -> None:
    """A same-window projection must not expose transient competing focus."""

    host, input_canvas, _output_canvas = _host()
    projection_focus = QWidget(host)
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        projection_focus.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        projection_focus.show()

        assert host.activate_canvas("Input", keyboard_focus=True)
        wait_for_qt_condition(input_canvas.hasFocus)

        projection_focus.setFocus()

        assert input_canvas.hasFocus()
    finally:
        host.close()


def test_activation_focus_handoff_yields_to_later_user_intent() -> None:
    """A later keyboard event must release picker-requested focus ownership."""

    host, input_canvas, _output_canvas = _host()
    other_focus = QWidget(host)
    try:
        input_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        other_focus.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        other_focus.show()

        assert host.activate_canvas("Input", keyboard_focus=True)
        _app().processEvents()
        assert input_canvas.hasFocus()

        QTest.keyClick(input_canvas, Qt.Key.Key_Tab)
        other_focus.setFocus()
        _app().processEvents()

        assert other_focus.hasFocus()
    finally:
        host.close()


def test_selector_opens_shared_anchored_picker() -> None:
    """Clicking the host anchor should use the shared canvas navigation popup."""

    host, _input_canvas, _output_canvas = _host()
    try:
        selector = host.selector
        assert isinstance(selector, CanvasHostSelector)

        selector.button.click()
        _app().processEvents()

        assert selector.picker_visible()
    finally:
        host.close()


def test_selector_geometry_is_one_obstacle_for_attached_canvas_chrome() -> None:
    """Attached canvas chrome should receive the selector's occupied rectangle."""

    host, input_canvas, output_canvas = _host()
    try:
        selector = host.selector
        assert isinstance(selector, CanvasHostSelector)
        expected_obstacles = (selector.geometry(),)
        assert input_canvas.chrome_obstacles[-1] == expected_obstacles
        assert output_canvas.chrome_obstacles[-1] == expected_obstacles
    finally:
        host.close()


def test_unavailable_canvas_hides_selector_and_uses_fallback() -> None:
    """Availability should update selector, stack, passive state, and fallback once."""

    host, input_canvas, output_canvas = _host()
    try:
        host.set_canvas_available("Input", False, reason="Unavailable")
        _app().processEvents()

        assert host.selector.isHidden()
        assert host.is_canvas_visible("Output")
        assert input_canvas.availability[-1] == (False, "Unavailable")
        assert input_canvas.chrome_obstacles[-1] == ()
        assert output_canvas.chrome_obstacles[-1] == ()
    finally:
        host.close()


def test_detach_and_redock_reuse_state_without_parallel_selector_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docking should collapse and restore selector chrome from the same entries."""

    docking_module = __import__(
        "substitute.presentation.canvas.host.canvas_docking_controller",
        fromlist=["FloatingCanvasWindow"],
    )
    monkeypatch.setattr(docking_module, "FloatingCanvasWindow", _FloatingWindow)
    host, input_canvas, _output_canvas = _host()
    try:
        host.detach_canvas("Input")
        _app().processEvents()

        assert host.selector.isHidden()
        assert input_canvas.detached_states[-1]
        assert input_canvas.chrome_obstacles[-1] == ()
        assert host.canvas_layout_snapshot() == CanvasLayoutSnapshot(
            floating_windows=(FloatingCanvasWindowSnapshot(label="Input"),)
        )

        input_canvas.dockActionRequested.emit()
        _app().processEvents()

        assert host.selector.isVisible()
        assert input_canvas.detached_states[-1] is False
        assert host.is_canvas_visible("Input")
    finally:
        host.close()


def test_layout_restore_uses_docking_owner_and_ignores_unknown_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durable floating state should restore through configured host entries only."""

    docking_module = __import__(
        "substitute.presentation.canvas.host.canvas_docking_controller",
        fromlist=["FloatingCanvasWindow"],
    )
    monkeypatch.setattr(docking_module, "FloatingCanvasWindow", _FloatingWindow)
    host, _input_canvas, _output_canvas = _host()
    output_snapshot = FloatingCanvasWindowSnapshot(label="Output")
    try:
        host.apply_restored_canvas_layout(
            CanvasLayoutSnapshot(
                floating_windows=(
                    output_snapshot,
                    FloatingCanvasWindowSnapshot(label="Unknown"),
                )
            )
        )
        _app().processEvents()

        assert host.canvas_layout_snapshot() == CanvasLayoutSnapshot(
            floating_windows=(output_snapshot,)
        )
        assert host.selector.isHidden()
        assert host.is_canvas_visible("Input")

        host.apply_restored_canvas_layout(CanvasLayoutSnapshot())
        _app().processEvents()

        assert host.canvas_layout_snapshot() == CanvasLayoutSnapshot()
        assert host.selector.isVisible()
        assert host.is_canvas_visible("Output")
    finally:
        host.close()


def test_failed_window_creation_restores_canvas_to_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A native window failure should leave selection and stack ownership intact."""

    docking_module = __import__(
        "substitute.presentation.canvas.host.canvas_docking_controller",
        fromlist=["FloatingCanvasWindow"],
    )

    def fail_window_creation(*_args: object, **_kwargs: object) -> None:
        """Raise the deterministic native-window failure used by this regression."""

        raise RuntimeError("window creation failed")

    monkeypatch.setattr(docking_module, "FloatingCanvasWindow", fail_window_creation)
    host, _input_canvas, _output_canvas = _host()
    try:
        with pytest.raises(RuntimeError, match="window creation failed"):
            host.detach_canvas("Input")
        _app().processEvents()

        assert host.selector.isVisible()
        assert host.is_canvas_visible("Input")
        assert host.canvas_layout_snapshot() == CanvasLayoutSnapshot()
    finally:
        host.close()
