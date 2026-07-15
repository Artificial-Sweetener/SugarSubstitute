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

"""Characterization tests for canvas tab manager control flow."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.workspace_snapshot import (
    CanvasLayoutSnapshot,
    FloatingCanvasWindowSnapshot,
    WindowGeometrySnapshot,
)


class _DockSignal:
    """Small signal double for canvas dock-action manager tests."""

    def __init__(self) -> None:
        self._slots: list[Any] = []

    def connect(self, slot: Any) -> None:
        self._slots.append(slot)

    def disconnect(self, slot: Any) -> None:
        if slot not in self._slots:
            raise RuntimeError("slot is not connected")
        self._slots.remove(slot)

    def emit(self) -> None:
        for slot in list(self._slots):
            slot()


def _import_canvas_module():
    """Import canvas tab manager module."""
    return importlib.import_module(
        "substitute.presentation.canvas.host.canvas_tabs_view"
    )


def _import_output_chrome_module():
    """Import Output-owned floating chrome module."""
    return importlib.import_module(
        "substitute.presentation.canvas.output.output_floating_chrome"
    )


def _app() -> QApplication:
    """Return the QApplication required for real widget host tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_close_all_floating_windows_closes_every_window() -> None:
    """Window cleanup should close each floating window currently tracked."""
    mod = _import_canvas_module()
    closed: list[str] = []
    fake = SimpleNamespace(
        canvas_map={"Input": object(), "Output": object()},
        floating_windows={
            "Input": SimpleNamespace(close=lambda: closed.append("Input")),
            "Output": SimpleNamespace(close=lambda: closed.append("Output")),
        },
    )

    mod.CanvasTabManager._close_all_floating_windows(fake)

    assert sorted(closed) == ["Input", "Output"]


def test_floating_window_applies_shell_titlebar_button_theme(monkeypatch) -> None:
    """Floating canvas titlebar buttons should use the shell theme helper."""

    mod = _import_canvas_module()
    floating_mod = importlib.import_module(
        "substitute.presentation.canvas.host.floating_canvas_window"
    )
    titlebar = object()
    themed_titlebars: list[object] = []
    fake = SimpleNamespace(titleBar=titlebar)
    monkeypatch.setattr(
        floating_mod,
        "apply_shell_titlebar_button_theme",
        lambda themed: themed_titlebars.append(themed),
    )

    mod.FloatingCanvasWindow._apply_theme_styles(fake)

    assert themed_titlebars == [titlebar]


def test_floating_canvas_snapshot_captures_geometry_without_domain_state() -> None:
    """Floating windows should expose Qt-free layout state for persistence."""

    mod = _import_canvas_module()
    geometry = SimpleNamespace(
        x=lambda: 10,
        y=lambda: 20,
        width=lambda: 640,
        height=lambda: 480,
    )
    fake = SimpleNamespace(
        label="Output",
        geometry=lambda: geometry,
        isFullScreen=lambda: False,
        isMaximized=lambda: True,
    )

    snapshot = mod.FloatingCanvasWindow.floating_canvas_snapshot(fake)

    assert snapshot == FloatingCanvasWindowSnapshot(
        label="Output",
        geometry=WindowGeometrySnapshot(x=10, y=20, width=640, height=480),
        window_display_state="maximized",
        output_generation_controls_revealed=False,
    )


def test_input_floating_canvas_snapshot_never_marks_output_reveal() -> None:
    """Input floating snapshots should not persist output-only reveal state."""

    mod = _import_canvas_module()
    geometry = SimpleNamespace(
        x=lambda: 1,
        y=lambda: 2,
        width=lambda: 320,
        height=lambda: 240,
    )
    fake = SimpleNamespace(
        label="Input",
        geometry=lambda: geometry,
        isFullScreen=lambda: False,
        isMaximized=lambda: False,
    )

    snapshot = mod.FloatingCanvasWindow.floating_canvas_snapshot(fake)

    assert snapshot.output_generation_controls_revealed is False
    assert snapshot.window_display_state == "normal"


def test_floating_canvas_applies_restored_geometry_and_display_state() -> None:
    """Floating windows should restore geometry before display state."""

    mod = _import_canvas_module()
    calls: list[tuple[object, ...]] = []
    fake = SimpleNamespace(
        setGeometry=lambda *args: calls.append(("geometry", *args)),
        showFullScreen=lambda: calls.append(("fullscreen",)),
        showMaximized=lambda: calls.append(("maximized",)),
        showNormal=lambda: calls.append(("normal",)),
    )

    mod.FloatingCanvasWindow.apply_restored_floating_snapshot(
        fake,
        FloatingCanvasWindowSnapshot(
            label="Input",
            geometry=WindowGeometrySnapshot(x=10, y=20, width=640, height=480),
            window_display_state="fullscreen",
        ),
    )

    assert calls == [("geometry", 10, 20, 640, 480), ("fullscreen",)]


def test_floating_canvas_geometry_clamps_offscreen_rect(monkeypatch) -> None:
    """Offscreen floating canvas geometry should move onto an available screen."""

    geom_mod = importlib.import_module(
        "substitute.presentation.canvas.host.geometry_persistence"
    )

    class _Rect:
        def __init__(self, x: int, y: int, width: int, height: int) -> None:
            self._x = x
            self._y = y
            self._width = width
            self._height = height

        def x(self) -> int:
            return self._x

        def y(self) -> int:
            return self._y

        def width(self) -> int:
            return self._width

        def height(self) -> int:
            return self._height

    screen = SimpleNamespace(availableGeometry=lambda: _Rect(0, 0, 1920, 1080))
    monkeypatch.setattr(
        geom_mod,
        "QGuiApplication",
        SimpleNamespace(screens=lambda: [screen], primaryScreen=lambda: screen),
    )

    geometry = geom_mod.clamped_floating_geometry(
        WindowGeometrySnapshot(x=5000, y=4000, width=50, height=50)
    )

    assert geometry == WindowGeometrySnapshot(
        x=1600,
        y=840,
        width=320,
        height=240,
    )


def test_output_generation_controls_restore_uses_reveal_host() -> None:
    """Output floating windows should restore reveal state without animation."""

    chrome_mod = _import_output_chrome_module()
    calls: list[tuple[bool, bool]] = []
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    chrome.generation_reveal_host = SimpleNamespace(
        set_expanded=lambda revealed, *, animated: calls.append((revealed, animated))
    )

    chrome.set_controls_revealed(
        True,
        animated=False,
    )

    assert calls == [(True, False)]


def test_input_generation_controls_restore_noops() -> None:
    """Input floating windows should not restore output-only reveal state."""

    mod = _import_canvas_module()
    calls: list[bool] = []
    fake = SimpleNamespace(
        setGeometry=lambda *_args: None,
        showNormal=lambda: calls.append(True),
    )

    mod.FloatingCanvasWindow.apply_restored_floating_snapshot(
        fake,
        FloatingCanvasWindowSnapshot(
            label="Input",
            output_generation_controls_revealed=True,
        ),
    )

    assert calls == [True]


def test_on_pivot_changed_only_switches_for_known_tab() -> None:
    """Pivot route changes should switch stack index only for tracked keys."""
    mod = _import_canvas_module()
    stack_calls: list[int] = []
    fake = SimpleNamespace(
        tab_indices={"Input": 0, "Output": 1},
        stack=SimpleNamespace(setCurrentIndex=lambda idx: stack_calls.append(idx)),
    )

    mod.CanvasTabManager.on_pivot_changed(fake, "Output")
    mod.CanvasTabManager.on_pivot_changed(fake, "Unknown")

    assert stack_calls == [1]


def test_focus_attached_canvas_selects_known_docked_tab() -> None:
    """Attached canvas focus should route the pivot and stack for docked tabs."""

    mod = _import_canvas_module()
    pivot_calls: list[str] = []
    stack_calls: list[int] = []
    fake = SimpleNamespace(
        floating_windows={},
        tab_indices={"Input": 0, "Output": 1},
        pivot=SimpleNamespace(
            items={"Input": object(), "Output": object()},
            setCurrentItem=lambda label: pivot_calls.append(label),
        ),
        stack=SimpleNamespace(setCurrentIndex=lambda index: stack_calls.append(index)),
    )

    mod.CanvasTabManager.focus_attached_canvas(fake, "Input")
    mod.CanvasTabManager.focus_attached_canvas(fake, "Output")

    assert pivot_calls == ["Input", "Output"]
    assert stack_calls == [0, 1]


def test_focus_attached_canvas_ignores_detached_or_missing_tabs() -> None:
    """Attached canvas focus should not manipulate detached or unavailable tabs."""

    mod = _import_canvas_module()
    pivot_calls: list[str] = []
    stack_calls: list[int] = []
    fake = SimpleNamespace(
        floating_windows={"Input": object()},
        tab_indices={"Input": 0, "Output": 1},
        pivot=SimpleNamespace(
            items={"Output": object()},
            setCurrentItem=lambda label: pivot_calls.append(label),
        ),
        stack=SimpleNamespace(setCurrentIndex=lambda index: stack_calls.append(index)),
    )

    mod.CanvasTabManager.focus_attached_canvas(fake, "Input")
    mod.CanvasTabManager.focus_attached_canvas(fake, "Missing")

    assert pivot_calls == []
    assert stack_calls == []


def test_set_canvas_available_false_hides_docked_input_and_selects_output() -> None:
    """Unavailable docked Input should hide its selector and fall back to Output."""

    mod = _import_canvas_module()
    availability_calls: list[tuple[bool, str]] = []
    current_items: list[str] = []
    stack_indices: list[int] = []
    removed: list[str] = []
    visible_calls: list[bool] = []

    class _Pivot:
        items = {"Input": object(), "Output": object()}

        def currentRouteKey(self) -> str:
            return "Input"

        def setCurrentItem(self, label: str) -> None:
            current_items.append(label)

        def removeWidget(self, label: str) -> None:
            removed.append(label)
            self.items.pop(label, None)

        def setVisible(self, visible: bool) -> None:
            visible_calls.append(visible)

    fake = SimpleNamespace(
        canvas_map={
            "Input": SimpleNamespace(
                set_available=lambda available, reason: availability_calls.append(
                    (available, reason)
                )
            )
        },
        floating_windows={},
        tab_indices={"Input": 0, "Output": 1},
        pivot=_Pivot(),
        stack=SimpleNamespace(
            setCurrentIndex=lambda index: stack_indices.append(index)
        ),
    )
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )
    fake.focus_attached_canvas = lambda label: (
        mod.CanvasTabManager.focus_attached_canvas(
            fake,
            label,
        )
    )
    fake._canvas_availability = {}
    fake._fallback_labels = {"Input": "Output"}

    mod.CanvasTabManager.set_canvas_available(
        fake,
        "Input",
        False,
        reason="No input canvas nodes",
        fallback_label="Output",
    )

    assert availability_calls == [(False, "No input canvas nodes")]
    assert current_items == ["Output"]
    assert stack_indices == [1]
    assert removed == ["Input"]
    assert "Input" not in fake.pivot.items
    assert "Input" in fake.canvas_map
    assert fake.floating_windows == {}
    assert visible_calls == [False]


def test_set_canvas_available_false_keeps_detached_input_tracked() -> None:
    """Unavailable detached Input should show overlay without docked-tab mutation."""

    mod = _import_canvas_module()
    availability_calls: list[tuple[bool, str]] = []
    removed: list[str] = []
    fake = SimpleNamespace(
        canvas_map={
            "Input": SimpleNamespace(
                set_available=lambda available, reason: availability_calls.append(
                    (available, reason)
                )
            )
        },
        floating_windows={"Input": object()},
        tab_indices={"Output": 1},
        pivot=SimpleNamespace(
            items={"Output": object()},
            removeWidget=lambda label: removed.append(label),
        ),
    )
    fake._canvas_availability = {}
    fake._fallback_labels = {"Input": "Output"}

    mod.CanvasTabManager.set_canvas_available(
        fake,
        "Input",
        False,
        reason="No input canvas nodes",
        fallback_label="Output",
    )

    assert availability_calls == [(False, "No input canvas nodes")]
    assert removed == []
    assert "Input" in fake.floating_windows


def test_set_canvas_available_true_restores_input_before_output() -> None:
    """Available docked Input should restore its selector before Output."""

    mod = _import_canvas_module()
    availability_calls: list[tuple[bool, str]] = []
    inserted: list[tuple[int, str, object]] = []
    visible_calls: list[bool] = []

    class _Pivot:
        def __init__(self) -> None:
            self.items = {"Output": object()}

        def insertWidget(self, index: int, label: str, item: object) -> None:
            inserted.append((index, label, item))
            self.items = {"Input": item, "Output": self.items["Output"]}

        def setVisible(self, visible: bool) -> None:
            visible_calls.append(visible)

    fake = SimpleNamespace(
        canvas_map={
            "Input": SimpleNamespace(
                set_available=lambda available, reason: availability_calls.append(
                    (available, reason)
                )
            )
        },
        floating_windows={},
        tab_indices={"Input": 0, "Output": 1},
        pivot=_Pivot(),
    )
    fake._create_pivot_item = lambda label: f"item:{label}"
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )
    fake.insertion_index_for_label = lambda label: 0
    fake.rebuild_tab_indices = lambda: setattr(
        fake,
        "tab_indices",
        {label: index for index, label in enumerate(fake.pivot.items)},
    )
    fake._canvas_availability = {}
    fake._fallback_labels = {"Input": "Output"}

    mod.CanvasTabManager.set_canvas_available(
        fake,
        "Input",
        True,
        reason="No input canvas nodes",
        fallback_label="Output",
    )

    assert availability_calls == [(True, "No input canvas nodes")]
    assert inserted == [(0, "Input", "item:Input")]
    assert list(fake.pivot.items) == ["Input", "Output"]
    assert fake.tab_indices == {"Input": 0, "Output": 1}
    assert visible_calls == [True]


def test_undock_tab_returns_early_when_missing_or_already_floating() -> None:
    """undock_tab should no-op for unknown labels and already floating labels."""
    mod = _import_canvas_module()

    fake_missing = SimpleNamespace(canvas_map={}, floating_windows={})
    mod.CanvasTabManager.undock_tab(fake_missing, "Input")

    fake_floating = SimpleNamespace(
        canvas_map={"Input": object()},
        floating_windows={"Input": object()},
    )
    mod.CanvasTabManager.undock_tab(fake_floating, "Input")

    assert "Input" not in fake_missing.canvas_map
    assert "Input" in fake_floating.floating_windows


def test_all_tabs_empty_reflects_pivot_item_count() -> None:
    """Tab emptiness is based solely on pivot item map size."""
    mod = _import_canvas_module()
    fake = SimpleNamespace(pivot=SimpleNamespace(items={}))
    assert mod.CanvasTabManager.all_tabs_empty(fake) is True

    fake.pivot.items = {"Input": object()}
    assert mod.CanvasTabManager.all_tabs_empty(fake) is False


def test_update_tab_visibility_shows_pivot_only_for_multiple_docked_canvases() -> None:
    """Pivot selector should hide when fewer than two canvases are docked."""
    mod = _import_canvas_module()
    visible_calls: list[bool] = []
    fake = SimpleNamespace(
        pivot=SimpleNamespace(
            items={},
            setVisible=lambda visible: visible_calls.append(visible),
        )
    )

    mod.CanvasTabManager.update_tab_visibility(fake)
    fake.pivot.items["Input"] = object()
    mod.CanvasTabManager.update_tab_visibility(fake)
    fake.pivot.items["Output"] = object()
    mod.CanvasTabManager.update_tab_visibility(fake)

    assert visible_calls == [False, False, True]


def test_install_pivot_undock_handler_keeps_manager_receiver() -> None:
    """Pivot mouse override should call the manager-bound handler."""
    mod = _import_canvas_module()
    fake = SimpleNamespace(pivot=SimpleNamespace(mousePressEvent=None))
    fake._pivot_mouse_press_event = lambda event: f"handled:{event}"

    mod.CanvasTabManager._install_pivot_undock_handler(fake)

    assert fake.pivot.mousePressEvent("right-click") == "handled:right-click"


def test_pivot_right_click_undocks_target_tab(monkeypatch) -> None:
    """Pivot right-click should undock the tab under the cursor."""
    mod = _import_canvas_module()
    undocked: list[str] = []
    forwarded: list[object] = []

    class _Geometry:
        def contains(self, _pos: object) -> bool:
            return True

    class _PivotItem:
        def geometry(self) -> _Geometry:
            return _Geometry()

    class _Event:
        def button(self) -> int:
            return 2

        def pos(self) -> object:
            return object()

    monkeypatch.setattr(mod, "Qt", SimpleNamespace(RightButton=2))
    monkeypatch.setattr(
        mod,
        "Pivot",
        SimpleNamespace(
            mousePressEvent=lambda pivot, event: forwarded.append((pivot, event))
        ),
    )
    pivot = SimpleNamespace(items={"Input": _PivotItem()})
    fake = SimpleNamespace(
        pivot=pivot,
        undock_tab=lambda label: undocked.append(label),
    )
    event = _Event()

    mod.CanvasTabManager._pivot_mouse_press_event(fake, event)

    assert undocked == ["Input"]
    assert forwarded == [(pivot, event)]


def test_add_canvas_sets_and_connects_context_menu_dock_action(monkeypatch) -> None:
    """Added canvases should expose manager-owned dock action wiring."""

    mod = _import_canvas_module()

    class _Wrapper:
        pass

    class _VBox:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def setContentsMargins(self, *_args: object) -> None:
            return None

        def setSpacing(self, _spacing: int) -> None:
            return None

        def addWidget(self, _widget: object) -> None:
            return None

    class _Canvas:
        def __init__(self) -> None:
            self.dockActionRequested = _DockSignal()
            self.text_calls: list[str] = []

        def set_dock_action_text(self, text: str) -> None:
            self.text_calls.append(text)

    class _Pivot:
        def __init__(self) -> None:
            self.items: dict[str, object] = {}

        def insertWidget(self, _index: int, label: str, item: object) -> None:
            self.items[label] = item

        def setCurrentItem(self, _label: str) -> None:
            return None

        def setVisible(self, _visible: bool) -> None:
            return None

    class _Stack:
        def insertWidget(self, _index: int, _widget: object) -> None:
            return None

        def setCurrentIndex(self, _index: int) -> None:
            return None

    monkeypatch.setattr(mod, "QWidget", _Wrapper)
    monkeypatch.setattr(mod, "QVBoxLayout", _VBox)

    handled: list[str] = []
    canvas = _Canvas()
    fake = SimpleNamespace(
        pivot=_Pivot(),
        stack=_Stack(),
        canvas_map={},
        wrapper_map={},
        tab_indices={},
        _canvas_dock_action_callbacks={},
        handle_canvas_dock_action=lambda label: handled.append(label),
    )
    fake._create_pivot_item = lambda label: f"item:{label}"
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )

    mod.CanvasTabManager.add_canvas(fake, "Input", canvas)
    canvas.dockActionRequested.emit()

    assert canvas.text_calls == ["Undock canvas"]
    assert handled == ["Input"]


def test_handle_canvas_dock_action_undocks_attached_canvas() -> None:
    """Attached context-menu dock action should delegate to undock_tab."""

    mod = _import_canvas_module()
    undocked: list[str] = []
    fake = SimpleNamespace(
        floating_windows={},
        canvas_map={"Input": object()},
        undock_tab=lambda label: undocked.append(label),
    )

    mod.CanvasTabManager.handle_canvas_dock_action(fake, "Input")
    mod.CanvasTabManager.handle_canvas_dock_action(fake, "Missing")

    assert undocked == ["Input"]


def test_handle_canvas_dock_action_redocks_detached_canvas_by_closing_window() -> None:
    """Detached context-menu dock action should use the floating redock path."""

    mod = _import_canvas_module()
    closed: list[str] = []
    fake = SimpleNamespace(
        floating_windows={
            "Output": SimpleNamespace(close=lambda: closed.append("Output"))
        },
        canvas_map={"Output": object()},
    )

    mod.CanvasTabManager.handle_canvas_dock_action(fake, "Output")

    assert closed == ["Output"]


def test_handle_canvas_dock_action_does_not_mutate_image_ownership() -> None:
    """Phase 0 - floating/docked host transitions do not mutate image ownership."""

    mod = _import_canvas_module()
    ownership_calls: list[str] = []
    closed: list[str] = []

    class _CanvasSurface:
        def __init__(self) -> None:
            self.input_image_id = "input-a"
            self.active_mask_id = "mask-a"
            self.output_image_ids = ["output-a"]
            self.catalog_image_ids = {"input-a", "output-a", "foreign-warm"}

        def ownership_snapshot(self) -> tuple[object, ...]:
            return (
                self.input_image_id,
                self.active_mask_id,
                tuple(self.output_image_ids),
                frozenset(self.catalog_image_ids),
            )

        def set_active_input_image(self, *_args: object) -> None:
            ownership_calls.append("set_active_input_image")
            self.input_image_id = "mutated-input"

        def set_active_mask(self, *_args: object) -> None:
            ownership_calls.append("set_active_mask")
            self.active_mask_id = "mutated-mask"

        def register_output_image(self, *_args: object) -> None:
            ownership_calls.append("register_output_image")
            self.output_image_ids.append("mutated-output")

        def clear_output_for_workflow(self, *_args: object) -> None:
            ownership_calls.append("clear_output_for_workflow")
            self.output_image_ids.clear()

    undocked: list[str] = []
    input_surface = _CanvasSurface()
    output_surface = _CanvasSurface()
    fake = SimpleNamespace(
        floating_windows={
            "Output": SimpleNamespace(close=lambda: closed.append("Output"))
        },
        canvas_map={"Input": input_surface, "Output": output_surface},
        undock_tab=lambda label: undocked.append(label),
    )
    before_snapshots = {
        label: surface.ownership_snapshot()
        for label, surface in fake.canvas_map.items()
    }

    mod.CanvasTabManager.handle_canvas_dock_action(fake, "Input")
    mod.CanvasTabManager.handle_canvas_dock_action(fake, "Output")

    assert undocked == ["Input"]
    assert closed == ["Output"]
    assert ownership_calls == []
    assert {
        label: surface.ownership_snapshot()
        for label, surface in fake.canvas_map.items()
    } == before_snapshots


def test_undock_selected_tab_moves_selection_before_removing_pivot_item(
    monkeypatch,
) -> None:
    """Undocking the current pivot route should not invalidate QFluent state."""
    mod = _import_canvas_module()

    class _Widget:
        def setParent(self, _parent) -> None:
            return None

    class _VBox:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setContentsMargins(self, *_args) -> None:
            return None

        def setSpacing(self, _spacing: int) -> None:
            return None

        def addWidget(self, _widget) -> None:
            return None

    class _FloatingWindow:
        def __init__(
            self,
            canvas_widget,
            label,
            redock_callback,
            *,
            backdrop_mode=None,
            generation_titlebar_control_registry=None,
            generation_progress_strip_registry=None,
        ) -> None:
            self.canvas_widget = canvas_widget
            self.label = label
            self.redock_callback = redock_callback
            self.backdrop_mode = backdrop_mode
            self.generation_titlebar_control_registry = (
                generation_titlebar_control_registry
            )
            self.generation_progress_strip_registry = generation_progress_strip_registry
            created_windows[label] = self

        def setAttribute(self, *_args, **_kwargs) -> None:
            return None

        def setWindowFlag(self, *_args, **_kwargs) -> None:
            return None

        def setWindowModality(self, *_args, **_kwargs) -> None:
            return None

        def setWindowTitle(self, *_args, **_kwargs) -> None:
            return None

        def setWindowIcon(self, *_args, **_kwargs) -> None:
            return None

        def resize(self, *_args, **_kwargs) -> None:
            return None

        def show(self) -> None:
            return None

    created_windows: dict[str, _FloatingWindow] = {}
    monkeypatch.setattr(mod, "QWidget", _Widget)
    monkeypatch.setattr(mod, "QVBoxLayout", _VBox)
    monkeypatch.setattr(mod, "FloatingCanvasWindow", _FloatingWindow)
    monkeypatch.setattr(
        mod,
        "Qt",
        SimpleNamespace(WA_DeleteOnClose=1, Window=2, NonModal=3, Tool=4),
    )

    class _Pivot:
        def __init__(self) -> None:
            self.items = {"Input": object(), "Output": object()}
            self.current_route_key = "Input"
            self.calls: list[tuple[str, str]] = []

        def currentRouteKey(self) -> str | None:
            return self.current_route_key

        def setCurrentItem(self, label: str) -> None:
            self.calls.append(("set", label))
            self.current_route_key = label

        def removeWidget(self, label: str) -> None:
            self.calls.append(("remove", label))
            assert self.calls[0] == ("set", "Output")
            self.items.pop(label, None)

        def setVisible(self, _visible: bool) -> None:
            return None

    class _Stack:
        def __init__(self) -> None:
            self.current_indices: list[int] = []

        def removeWidget(self, _widget) -> None:
            return None

        def insertWidget(self, _index: int, _widget) -> None:
            return None

        def setCurrentIndex(self, index: int) -> None:
            self.current_indices.append(index)

    visibility_calls: list[bool] = []
    pivot = _Pivot()
    fake = SimpleNamespace(
        canvas_map={"Input": _Widget(), "Output": _Widget()},
        wrapper_map={"Input": object(), "Output": object()},
        tab_indices={"Input": 0, "Output": 1},
        floating_windows={},
        generation_titlebar_control_registry=None,
        pivot=pivot,
        stack=_Stack(),
        canvas_region=SimpleNamespace(isVisible=lambda: True),
        visibility_changed=SimpleNamespace(
            emit=lambda visible: visibility_calls.append(visible)
        ),
        window=lambda: SimpleNamespace(windowIcon=lambda: object()),
        _pivot_item_stylesheet=lambda: "",
    )
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )
    fake.all_tabs_empty = lambda: mod.CanvasTabManager.all_tabs_empty(fake)

    mod.CanvasTabManager.undock_tab(fake, "Input")

    assert pivot.calls[:2] == [("set", "Output"), ("remove", "Input")]
    assert "Input" in created_windows
    assert visibility_calls == []


def test_undocking_one_canvas_hides_single_remaining_selector(monkeypatch) -> None:
    """A single remaining docked canvas should not show the selector."""
    mod = _import_canvas_module()

    class _Widget:
        def setParent(self, _parent) -> None:
            return None

    class _VBox:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setContentsMargins(self, *_args) -> None:
            return None

        def setSpacing(self, _spacing: int) -> None:
            return None

        def addWidget(self, _widget) -> None:
            return None

    class _FloatingWindow:
        def __init__(
            self,
            canvas_widget,
            label,
            redock_callback,
            *,
            backdrop_mode=None,
            generation_titlebar_control_registry=None,
            generation_progress_strip_registry=None,
        ) -> None:
            self.canvas_widget = canvas_widget
            self.label = label
            self.redock_callback = redock_callback
            self.backdrop_mode = backdrop_mode
            self.generation_titlebar_control_registry = (
                generation_titlebar_control_registry
            )
            self.generation_progress_strip_registry = generation_progress_strip_registry

        def setAttribute(self, *_args, **_kwargs) -> None:
            return None

        def setWindowFlag(self, *_args, **_kwargs) -> None:
            return None

        def setWindowModality(self, *_args, **_kwargs) -> None:
            return None

        def setWindowTitle(self, *_args, **_kwargs) -> None:
            return None

        def setWindowIcon(self, *_args, **_kwargs) -> None:
            return None

        def resize(self, *_args, **_kwargs) -> None:
            return None

        def show(self) -> None:
            return None

    monkeypatch.setattr(mod, "QWidget", _Widget)
    monkeypatch.setattr(mod, "QVBoxLayout", _VBox)
    monkeypatch.setattr(mod, "FloatingCanvasWindow", _FloatingWindow)
    monkeypatch.setattr(
        mod,
        "Qt",
        SimpleNamespace(WA_DeleteOnClose=1, Window=2, NonModal=3, Tool=4),
    )

    class _Pivot:
        def __init__(self) -> None:
            self.items = {"Input": object(), "Output": object()}
            self.current_route_key = "Input"
            self.visible_calls: list[bool] = []

        def currentRouteKey(self) -> str | None:
            return self.current_route_key

        def setCurrentItem(self, label: str) -> None:
            self.current_route_key = label

        def removeWidget(self, label: str) -> None:
            self.items.pop(label, None)

        def setVisible(self, visible: bool) -> None:
            self.visible_calls.append(visible)

    class _Stack:
        def removeWidget(self, _widget) -> None:
            return None

        def insertWidget(self, _index: int, _widget) -> None:
            return None

        def setCurrentIndex(self, _index: int) -> None:
            return None

    visibility_calls: list[bool] = []
    pivot = _Pivot()
    fake = SimpleNamespace(
        canvas_map={"Input": _Widget(), "Output": _Widget()},
        wrapper_map={"Input": object(), "Output": object()},
        tab_indices={"Input": 0, "Output": 1},
        floating_windows={},
        generation_titlebar_control_registry=None,
        pivot=pivot,
        stack=_Stack(),
        canvas_region=SimpleNamespace(isVisible=lambda: True),
        visibility_changed=SimpleNamespace(
            emit=lambda visible: visibility_calls.append(visible)
        ),
        window=lambda: SimpleNamespace(windowIcon=lambda: object()),
        _pivot_item_stylesheet=lambda: "",
    )
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )
    fake.all_tabs_empty = lambda: mod.CanvasTabManager.all_tabs_empty(fake)

    mod.CanvasTabManager.undock_tab(fake, "Input")

    assert list(pivot.items) == ["Output"]
    assert pivot.visible_calls == [False]
    assert visibility_calls == []


def test_undocked_canvas_windows_are_taskbar_visible_top_level_windows(
    monkeypatch,
) -> None:
    """Undocked canvases should be normal taskbar-visible top-level windows."""
    mod = _import_canvas_module()
    fake_qt = SimpleNamespace(WA_DeleteOnClose=1, Window=2, NonModal=3, Tool=4)

    class _Widget:
        def setParent(self, _parent: object) -> None:
            return None

    class _FloatingWindow:
        def __init__(
            self,
            canvas_widget: object,
            label: str,
            redock_callback: object,
            *,
            backdrop_mode: object = None,
            generation_titlebar_control_registry: object = None,
            generation_progress_strip_registry: object = None,
        ) -> None:
            self.canvas_widget = canvas_widget
            self.label = label
            self.redock_callback = redock_callback
            self.backdrop_mode = backdrop_mode
            self.generation_titlebar_control_registry = (
                generation_titlebar_control_registry
            )
            self.generation_progress_strip_registry = generation_progress_strip_registry
            self.attribute_calls: list[object] = []
            self.flag_calls: list[tuple[object, bool]] = []
            self.modality_calls: list[object] = []
            self.title_calls: list[str] = []
            self.icon_calls: list[object] = []
            self.resize_calls: list[tuple[int, int]] = []
            self.show_calls = 0
            created_windows[label] = self

        def setAttribute(self, attribute: object) -> None:
            self.attribute_calls.append(attribute)

        def setWindowFlag(self, flag: object, enabled: bool = True) -> None:
            self.flag_calls.append((flag, enabled))

        def setWindowModality(self, modality: object) -> None:
            self.modality_calls.append(modality)

        def setWindowTitle(self, title: str) -> None:
            self.title_calls.append(title)

        def setWindowIcon(self, icon: object) -> None:
            self.icon_calls.append(icon)

        def resize(self, width: int, height: int) -> None:
            self.resize_calls.append((width, height))

        def show(self) -> None:
            self.show_calls += 1

    class _Pivot:
        def __init__(self, selected_label: str) -> None:
            self.items = {"Input": object(), "Output": object()}
            self.current_route_key = selected_label

        def currentRouteKey(self) -> str | None:
            return self.current_route_key

        def setCurrentItem(self, label: str) -> None:
            self.current_route_key = label

        def removeWidget(self, label: str) -> None:
            self.items.pop(label, None)

        def setVisible(self, _visible: bool) -> None:
            return None

    class _Stack:
        def removeWidget(self, _widget: object) -> None:
            return None

        def insertWidget(self, _index: int, _widget: object) -> None:
            return None

        def setCurrentIndex(self, _index: int) -> None:
            return None

    def exercise_undock(label: str) -> tuple[_FloatingWindow, object]:
        expected_icon = object()
        top_level_window = SimpleNamespace(
            _backdrop_mode="mica",
            windowIcon=lambda: expected_icon,
        )
        fake = SimpleNamespace(
            canvas_map={"Input": _Widget(), "Output": _Widget()},
            wrapper_map={"Input": object(), "Output": object()},
            tab_indices={"Input": 0, "Output": 1},
            floating_windows={},
            generation_titlebar_control_registry=registry,
            generation_progress_strip_registry=progress_registry,
            pivot=_Pivot(label),
            stack=_Stack(),
            canvas_region=SimpleNamespace(isVisible=lambda: True),
            visibility_changed=SimpleNamespace(emit=lambda _visible: None),
            window=lambda: top_level_window,
        )
        fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
            fake
        )
        fake.all_tabs_empty = lambda: mod.CanvasTabManager.all_tabs_empty(fake)

        mod.CanvasTabManager.undock_tab(fake, label)

        return created_windows[label], expected_icon

    created_windows: dict[str, _FloatingWindow] = {}
    registry = object()
    progress_registry = object()
    monkeypatch.setattr(mod, "QWidget", _Widget)
    monkeypatch.setattr(mod, "FloatingCanvasWindow", _FloatingWindow)
    monkeypatch.setattr(mod, "Qt", fake_qt)

    input_window, input_icon = exercise_undock("Input")
    output_window, output_icon = exercise_undock("Output")

    assert input_window.generation_titlebar_control_registry is None
    assert output_window.generation_titlebar_control_registry is None
    assert input_window.generation_progress_strip_registry is None
    assert output_window.generation_progress_strip_registry is None

    for window, expected_title, expected_icon in (
        (input_window, "Input Canvas", input_icon),
        (output_window, "Output Canvas", output_icon),
    ):
        assert window.attribute_calls == [fake_qt.WA_DeleteOnClose]
        assert (fake_qt.Window, True) in window.flag_calls
        assert (fake_qt.Tool, False) in window.flag_calls
        assert (fake_qt.Tool, True) not in window.flag_calls
        assert window.modality_calls == [fake_qt.NonModal]
        assert window.title_calls[-1] == expected_title
        assert window.icon_calls == [expected_icon]
        assert window.resize_calls == [(800, 600)]
        assert window.show_calls == 1


def test_close_event_marks_manager_closing_and_closes_floating_windows() -> None:
    """Closing manager should flag closing state and close tracked floating windows."""
    mod = _import_canvas_module()
    closed: list[str] = []
    accepted: list[bool] = []
    fake = SimpleNamespace(
        floating_windows={
            "Input": SimpleNamespace(close=lambda: closed.append("Input")),
            "Output": SimpleNamespace(close=lambda: closed.append("Output")),
        }
    )
    event = SimpleNamespace(accept=lambda: accepted.append(True))

    mod.CanvasTabManager.closeEvent(fake, event)

    assert fake.closing is True
    assert sorted(closed) == ["Input", "Output"]
    assert accepted == [True]


def test_floating_window_close_event_redocks_only_when_parent_is_open() -> None:
    """Floating close should call redock callback unless parent is already closing."""
    mod = _import_canvas_module()

    redock_calls: list[tuple[object, str]] = []
    accepted_a: list[bool] = []
    fake_open = SimpleNamespace(
        canvas_widget=object(),
        label="Input",
        redock_callback=lambda widget, label: redock_calls.append((widget, label)),
        parent=lambda: SimpleNamespace(closing=False),
    )
    event_a = SimpleNamespace(accept=lambda: accepted_a.append(True))
    mod.FloatingCanvasWindow.closeEvent(fake_open, event_a)

    accepted_b: list[bool] = []
    fake_closing = SimpleNamespace(
        canvas_widget=object(),
        label="Output",
        redock_callback=lambda *_a: redock_calls.append(("unexpected", "unexpected")),
        parent=lambda: SimpleNamespace(closing=True),
    )
    event_b = SimpleNamespace(accept=lambda: accepted_b.append(True))
    mod.FloatingCanvasWindow.closeEvent(fake_closing, event_b)

    assert len(redock_calls) == 1
    assert redock_calls[0][1] == "Input"
    assert accepted_a == [True]
    assert accepted_b == [True]


def test_floating_output_window_installs_generation_reveal_host(monkeypatch) -> None:
    """Only Output floating windows should add and register the reveal host."""

    chrome_mod = _import_output_chrome_module()
    registered: list[object] = []
    host_control = object()

    class _Host:
        def __init__(
            self,
            parent: object,
            *,
            acrylic_style_enabled: bool = False,
        ) -> None:
            self.parent = parent
            self.acrylic_style_enabled = acrylic_style_enabled
            self.control = host_control

    class _Layout:
        def __init__(self) -> None:
            self.inserted: list[tuple[int, object]] = []

        def indexOf(self, widget: object) -> int:
            return 2 if widget == "min" else -1

        def insertWidget(self, index: int, widget: object) -> None:
            self.inserted.append((index, widget))

        def addWidget(self, _widget: object) -> None:
            raise AssertionError("expected insertion before min button")

    layout = _Layout()
    titlebar = SimpleNamespace(layout=lambda: layout, minBtn="min")
    fake = SimpleNamespace(
        label="Output",
        titleBar=titlebar,
        backdrop_mode=chrome_mod.ShellBackdropMode.ACRYLIC,
    )
    registry = SimpleNamespace(register=lambda control: registered.append(control))
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=registry,
        progress_strip_registry=None,
    )
    monkeypatch.setattr(chrome_mod, "GenerationClusterRevealHost", _Host)

    chrome._install_generation_reveal_host(fake)

    assert registered == [host_control]
    assert chrome.generation_reveal_host.control is host_control
    assert chrome.generation_reveal_host.acrylic_style_enabled is True
    assert layout.inserted == [(2, chrome.generation_reveal_host)]


def test_floating_input_window_does_not_install_generation_reveal_host(
    monkeypatch,
) -> None:
    """Input floating windows should not receive output generation controls."""

    chrome_mod = _import_output_chrome_module()
    factory = chrome_mod.OutputFloatingChromeFactory(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    input_chrome = factory()

    assert input_chrome.generation_reveal_host is None


def test_floating_output_window_unregisters_generation_control_on_close() -> None:
    """Closing/redocking output should detach its registered reveal control."""

    chrome_mod = _import_output_chrome_module()
    control = object()
    unregistered: list[object] = []
    registry = SimpleNamespace(unregister=lambda value: unregistered.append(value))
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=registry,
        progress_strip_registry=None,
    )
    chrome.generation_reveal_host = SimpleNamespace(control=control)

    chrome._unregister_generation_reveal_host()

    assert unregistered == [control]
    assert chrome._titlebar_control_registry is None


def test_canvas_manager_set_registry_updates_existing_output_window() -> None:
    """Late registry attachment should reach an already-undocked Output Canvas."""

    registry = object()
    calls: list[object] = []
    chrome_mod = _import_output_chrome_module()
    factory = chrome_mod.OutputFloatingChromeFactory()
    chrome = factory()
    chrome.set_titlebar_control_registry = calls.append

    factory.set_titlebar_control_registry(registry)

    assert factory.titlebar_control_registry is registry
    assert calls == [registry]


def test_canvas_manager_set_progress_registry_updates_existing_output_window() -> None:
    """Late progress registry attachment should reach an undocked Output Canvas."""

    registry = object()
    calls: list[object] = []
    chrome_mod = _import_output_chrome_module()
    factory = chrome_mod.OutputFloatingChromeFactory()
    chrome = factory()
    chrome.set_progress_strip_registry = calls.append

    factory.set_progress_strip_registry(registry)

    assert factory.progress_strip_registry is registry
    assert calls == [registry]


def test_canvas_manager_set_progress_registry_ignores_input_window() -> None:
    """Input floating windows should not receive output progress-strip wiring."""

    chrome_mod = _import_output_chrome_module()
    registry = object()
    factory = chrome_mod.OutputFloatingChromeFactory()

    factory.set_progress_strip_registry(registry)

    assert factory.progress_strip_registry is registry


def test_canvas_host_does_not_expose_output_registry_setters() -> None:
    """Generic host should not own Output generation registry attachment."""

    mod = _import_canvas_module()

    assert not hasattr(mod.CanvasTabManager, "set_generation_titlebar_control_registry")
    assert not hasattr(mod.CanvasTabManager, "set_generation_progress_strip_registry")


def test_canvas_manager_snapshot_captures_floating_windows_in_stable_order() -> None:
    """Canvas manager snapshots should include known floating labels only."""

    mod = _import_canvas_module()
    fake = SimpleNamespace(
        canvas_map={"Input": object(), "Output": object()},
        floating_windows={
            "Output": SimpleNamespace(
                floating_canvas_snapshot=lambda: FloatingCanvasWindowSnapshot(
                    label="Output"
                )
            ),
            "Unknown": SimpleNamespace(
                floating_canvas_snapshot=lambda: FloatingCanvasWindowSnapshot(
                    label="Unknown"
                )
            ),
            "Input": SimpleNamespace(
                floating_canvas_snapshot=lambda: FloatingCanvasWindowSnapshot(
                    label="Input"
                )
            ),
        },
    )

    snapshot = mod.CanvasTabManager.canvas_layout_snapshot(fake)

    assert snapshot == CanvasLayoutSnapshot(
        floating_windows=(
            FloatingCanvasWindowSnapshot(label="Input"),
            FloatingCanvasWindowSnapshot(label="Output"),
        )
    )


def test_canvas_manager_snapshot_empty_when_no_windows_float() -> None:
    """Canvas layout snapshot should represent all canvases docked as empty."""

    mod = _import_canvas_module()
    fake = SimpleNamespace(
        canvas_map={"Input": object(), "Output": object()}, floating_windows={}
    )

    snapshot = mod.CanvasTabManager.canvas_layout_snapshot(fake)

    assert snapshot == CanvasLayoutSnapshot()


def test_canvas_manager_restore_undocks_and_applies_output_reveal() -> None:
    """Canvas layout restore should undock output and restore reveal state."""

    mod = _import_canvas_module()
    undocked: list[str] = []
    applied: list[object] = []
    reveal_calls: list[tuple[bool, bool]] = []
    output_window = SimpleNamespace(
        apply_restored_floating_snapshot=applied.append,
        set_output_generation_controls_revealed=lambda revealed, *, animated: (
            reveal_calls.append((revealed, animated))
        ),
    )
    fake = SimpleNamespace(
        canvas_map={"Input": object(), "Output": object()}, floating_windows={}
    )

    def undock(label: str) -> None:
        undocked.append(label)
        if label == "Output":
            fake.floating_windows[label] = output_window

    fake.undock_tab = undock

    output_snapshot = FloatingCanvasWindowSnapshot(
        label="Output",
        output_generation_controls_revealed=True,
    )
    mod.CanvasTabManager.apply_restored_canvas_layout(
        fake,
        CanvasLayoutSnapshot(floating_windows=(output_snapshot,)),
    )

    assert undocked == ["Output"]
    assert applied == [output_snapshot]
    assert reveal_calls == []


def test_canvas_manager_restore_empty_layout_redocks_existing_window() -> None:
    """Canvas layout restore should redock windows missing from the snapshot."""

    mod = _import_canvas_module()
    closed: list[str] = []
    fake = SimpleNamespace(
        canvas_map={"Input": object(), "Output": object()},
        floating_windows={
            "Input": SimpleNamespace(close=lambda: closed.append("Input")),
        },
        undock_tab=lambda _label: None,
    )

    mod.CanvasTabManager.apply_restored_canvas_layout(fake, CanvasLayoutSnapshot())

    assert closed == ["Input"]


def test_canvas_manager_restore_ignores_unknown_floating_labels() -> None:
    """Unknown floating canvas snapshot labels should not be restored."""

    mod = _import_canvas_module()
    undocked: list[str] = []
    fake = SimpleNamespace(
        canvas_map={"Input": object(), "Output": object()},
        floating_windows={},
        undock_tab=undocked.append,
    )

    mod.CanvasTabManager.apply_restored_canvas_layout(
        fake,
        CanvasLayoutSnapshot(
            floating_windows=(FloatingCanvasWindowSnapshot(label="Unknown"),)
        ),
    )

    assert undocked == []


def test_floating_output_window_installs_generation_progress_strip(
    monkeypatch,
) -> None:
    """Output floating windows should register a top overlay progress strip."""

    chrome_mod = _import_output_chrome_module()
    registered: list[tuple[object, object]] = []

    class _Strip:
        def __init__(self, parent: object) -> None:
            self.parent = parent
            self.hidden = False
            self.geometries: list[tuple[int, int, int, int]] = []
            self.raise_calls = 0

        def hide(self) -> None:
            self.hidden = True

        def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
            self.geometries.append((x, y, width, height))

        def raise_(self) -> None:
            self.raise_calls += 1

    registry = SimpleNamespace(
        register=lambda strip, *, visible_gate: registered.append((strip, visible_gate))
    )
    controls_anchor = SimpleNamespace(
        mapTo=lambda _window, _point: SimpleNamespace(x=lambda: 560)
    )
    fake = SimpleNamespace(
        label="Output",
        width=lambda: 800,
    )
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=registry,
    )
    chrome.generation_reveal_host = SimpleNamespace(
        is_expanded=lambda: True,
        mapTo=lambda _window, _point: SimpleNamespace(x=lambda: 560),
        control=SimpleNamespace(
            progress_strip_stop_target=lambda: controls_anchor,
        ),
    )
    monkeypatch.setattr(chrome_mod, "GenerationProgressStrip", _Strip)

    chrome._install_generation_progress_strip(fake)

    assert isinstance(chrome.generation_progress_strip, _Strip)
    assert chrome.generation_progress_strip.hidden is True
    assert chrome.generation_progress_strip.parent is fake
    assert chrome.generation_progress_strip.geometries == [(0, 0, 560, 6)]
    assert chrome.generation_progress_strip.raise_calls == 1
    assert registered[0][0] is chrome.generation_progress_strip
    assert registered[0][1]() is True


def test_floating_output_progress_strip_stops_before_titlebar_controls() -> None:
    """Progress strip should stop before controls that would otherwise be covered."""

    chrome_mod = _import_output_chrome_module()
    strip = SimpleNamespace(
        geometries=[],
        raise_calls=0,
        setGeometry=lambda x, y, width, height: strip.geometries.append(
            (x, y, width, height)
        ),
        raise_=lambda: setattr(strip, "raise_calls", strip.raise_calls + 1),
    )
    batch_accessory = SimpleNamespace(
        mapTo=lambda _window, _point: SimpleNamespace(x=lambda: 520)
    )
    control = SimpleNamespace(
        mapTo=lambda _window, _point: SimpleNamespace(x=lambda: 506),
        progress_strip_stop_target=lambda: batch_accessory,
    )
    host = SimpleNamespace(
        mapTo=lambda _window, _point: SimpleNamespace(x=lambda: 492),
        control=control,
    )
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    chrome.generation_progress_strip = strip
    chrome.generation_reveal_host = host
    fake = SimpleNamespace(width=lambda: 640)

    chrome._position_generation_progress_strip(fake)

    assert strip.geometries == [(0, 0, 520, 6)]
    assert strip.raise_calls == 1


def test_floating_input_window_does_not_install_generation_progress_strip(
    monkeypatch,
) -> None:
    """Input floating windows should not receive the output progress strip."""

    chrome_mod = _import_output_chrome_module()
    factory = chrome_mod.OutputFloatingChromeFactory(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    chrome = factory()

    assert chrome.generation_progress_strip is None


def test_floating_output_window_unregisters_generation_progress_strip() -> None:
    """Closing/redocking output should detach its registered progress strip."""

    chrome_mod = _import_output_chrome_module()
    strip = SimpleNamespace(
        setGeometry=lambda *_args: None,
        raise_=lambda: None,
    )
    unregistered: list[object] = []
    registry = SimpleNamespace(unregister=lambda value: unregistered.append(value))
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=registry,
    )
    chrome.generation_progress_strip = strip

    chrome._unregister_generation_progress_strip()

    assert unregistered == [strip]
    assert chrome._progress_strip_registry is None


def test_floating_output_reveal_state_refreshes_progress_visibility() -> None:
    """Reveal expansion changes should ask the progress registry to refresh."""

    chrome_mod = _import_output_chrome_module()
    strip = SimpleNamespace(
        setGeometry=lambda *_args: None,
        raise_=lambda: None,
    )
    refreshed: list[object] = []
    connected_callbacks: list[object] = []
    host = SimpleNamespace(
        expandedChanged=SimpleNamespace(connect=connected_callbacks.append)
    )
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=SimpleNamespace(
            refresh_visibility=lambda value: refreshed.append(value),
        ),
    )
    chrome.generation_reveal_host = host
    chrome.generation_progress_strip = strip
    fake = SimpleNamespace(width=lambda: 640)

    chrome._connect_generation_progress_visibility_refresh(fake)
    connected_callbacks[0](True)

    assert refreshed == [strip]
    assert chrome._progress_visibility_connected is True


def test_floating_output_reveal_state_emits_layout_change() -> None:
    """Reveal expansion is durable layout state even without live progress."""

    chrome_mod = _import_output_chrome_module()
    connected_callbacks: list[object] = []
    layout_changes: list[str] = []
    host = SimpleNamespace(
        expandedChanged=SimpleNamespace(connect=connected_callbacks.append)
    )
    chrome = chrome_mod.OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    chrome.generation_reveal_host = host
    chrome.generation_progress_strip = None
    fake = SimpleNamespace(
        layoutStateChanged=SimpleNamespace(
            emit=lambda: layout_changes.append("changed")
        ),
    )

    chrome._connect_generation_progress_visibility_refresh(fake)
    connected_callbacks[0](True)

    assert layout_changes == ["changed"]
    assert chrome._progress_visibility_connected is True


def test_undock_all_tabs_emits_hidden_visibility(monkeypatch) -> None:
    """Undocking all canvases should emit hidden-state visibility change."""
    mod = _import_canvas_module()

    class _Widget:
        def setParent(self, _parent) -> None:
            return None

    class _VBox:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setContentsMargins(self, *_args) -> None:
            return None

        def setSpacing(self, _spacing: int) -> None:
            return None

        def addWidget(self, _widget) -> None:
            return None

    class _Signal:
        def __init__(self) -> None:
            self.callbacks: list[object] = []

        def connect(self, _callback) -> None:
            self.callbacks.append(_callback)

    class _PivotItem:
        def __init__(self, *_args, **_kwargs) -> None:
            self.doubleClicked = _Signal()

        def setStyleSheet(self, _qss: str) -> None:
            return None

        def adjustSize(self) -> None:
            return None

    created_windows: dict[str, object] = {}

    class _FloatingWindow:
        def __init__(
            self,
            canvas_widget,
            label,
            redock_callback,
            *,
            backdrop_mode=None,
            generation_titlebar_control_registry=None,
            generation_progress_strip_registry=None,
        ) -> None:
            self.canvas_widget = canvas_widget
            self.label = label
            self.redock_callback = redock_callback
            self.backdrop_mode = backdrop_mode
            self.generation_titlebar_control_registry = (
                generation_titlebar_control_registry
            )
            self.generation_progress_strip_registry = generation_progress_strip_registry
            self.layoutStateChanged = _Signal()
            created_windows[label] = self

        def setAttribute(self, *_args, **_kwargs) -> None:
            return None

        def setWindowFlag(self, *_args, **_kwargs) -> None:
            return None

        def setWindowModality(self, *_args, **_kwargs) -> None:
            return None

        def setWindowTitle(self, *_args, **_kwargs) -> None:
            return None

        def setWindowIcon(self, *_args, **_kwargs) -> None:
            return None

        def resize(self, *_args, **_kwargs) -> None:
            return None

        def show(self) -> None:
            return None

    monkeypatch.setattr(mod, "QWidget", _Widget)
    monkeypatch.setattr(mod, "QVBoxLayout", _VBox)
    monkeypatch.setattr(mod, "DockablePivotItem", _PivotItem)
    monkeypatch.setattr(mod, "setFont", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "FloatingCanvasWindow", _FloatingWindow)
    monkeypatch.setattr(
        mod,
        "Qt",
        SimpleNamespace(WA_DeleteOnClose=1, Window=2, NonModal=3, Tool=4),
    )

    class _Pivot:
        def __init__(self) -> None:
            self.items = {"Input": object(), "Output": object()}
            self.current_route_key: str | None = "Input"
            self.current_items: list[str] = []
            self.visible_calls: list[bool] = []

        def currentRouteKey(self) -> str | None:
            return self.current_route_key

        def removeWidget(self, label: str) -> None:
            self.items.pop(label, None)
            if self.current_route_key == label:
                self.current_route_key = None

        def insertWidget(self, index: int, label: str, item: object) -> None:
            keys = [key for key in self.items if key != label]
            if index < 0 or index > len(keys):
                index = len(keys)
            keys.insert(index, label)
            values = dict(self.items)
            values[label] = item
            self.items = {key: values[key] for key in keys}

        def setCurrentItem(self, label: str) -> None:
            self.current_items.append(label)
            self.current_route_key = label

        def setVisible(self, visible: bool) -> None:
            self.visible_calls.append(visible)

    class _Stack:
        def __init__(self) -> None:
            self.current_indices: list[int] = []

        def removeWidget(self, _widget) -> None:
            return None

        def insertWidget(self, _index: int, _widget) -> None:
            return None

        def setCurrentIndex(self, index: int) -> None:
            self.current_indices.append(index)

    visibility_calls: list[bool] = []
    layout_calls: list[str] = []
    fake = SimpleNamespace(
        canvas_map={"Input": _Widget(), "Output": _Widget()},
        wrapper_map={"Input": object(), "Output": object()},
        tab_indices={"Input": 0, "Output": 1},
        floating_windows={},
        generation_titlebar_control_registry=None,
        pivot=_Pivot(),
        stack=_Stack(),
        canvas_region=SimpleNamespace(isVisible=lambda: True),
        visibility_changed=SimpleNamespace(
            emit=lambda visible: visibility_calls.append(visible)
        ),
        layout_state_changed=SimpleNamespace(
            emit=lambda: layout_calls.append("changed")
        ),
        window=lambda: SimpleNamespace(windowIcon=lambda: object()),
        _pivot_item_stylesheet=lambda: "",
    )
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )
    fake.all_tabs_empty = lambda: mod.CanvasTabManager.all_tabs_empty(fake)
    fake.undock_tab = lambda label: mod.CanvasTabManager.undock_tab(fake, label)

    mod.CanvasTabManager.undock_tab(fake, "Input")
    mod.CanvasTabManager.undock_tab(fake, "Output")

    assert "Input" in created_windows
    assert "Output" in created_windows
    assert visibility_calls == [False]
    assert layout_calls == ["changed", "changed"]


def test_redock_output_inserts_after_input_when_input_is_docked(monkeypatch) -> None:
    """Redocking output while input is docked should insert output at index 1."""
    mod = _import_canvas_module()

    class _Widget:
        def setParent(self, _parent) -> None:
            return None

    class _VBox:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setContentsMargins(self, *_args) -> None:
            return None

        def setSpacing(self, _spacing: int) -> None:
            return None

        def addWidget(self, _widget) -> None:
            return None

    class _Signal:
        def connect(self, _callback) -> None:
            return None

    class _PivotItem:
        def __init__(self, *_args, **_kwargs) -> None:
            self.doubleClicked = _Signal()

        def setStyleSheet(self, _qss: str) -> None:
            return None

        def adjustSize(self) -> None:
            return None

    created_windows: dict[str, object] = {}

    class _FloatingWindow:
        def __init__(
            self,
            canvas_widget,
            label,
            redock_callback,
            *,
            backdrop_mode=None,
            generation_titlebar_control_registry=None,
            generation_progress_strip_registry=None,
        ) -> None:
            self.canvas_widget = canvas_widget
            self.label = label
            self.redock_callback = redock_callback
            self.backdrop_mode = backdrop_mode
            self.generation_titlebar_control_registry = (
                generation_titlebar_control_registry
            )
            self.generation_progress_strip_registry = generation_progress_strip_registry
            created_windows[label] = self

        def setAttribute(self, *_args, **_kwargs) -> None:
            return None

        def setWindowFlag(self, *_args, **_kwargs) -> None:
            return None

        def setWindowModality(self, *_args, **_kwargs) -> None:
            return None

        def setWindowTitle(self, *_args, **_kwargs) -> None:
            return None

        def setWindowIcon(self, *_args, **_kwargs) -> None:
            return None

        def resize(self, *_args, **_kwargs) -> None:
            return None

        def show(self) -> None:
            return None

    monkeypatch.setattr(mod, "QWidget", _Widget)
    monkeypatch.setattr(mod, "QVBoxLayout", _VBox)
    monkeypatch.setattr(mod, "DockablePivotItem", _PivotItem)
    monkeypatch.setattr(mod, "setFont", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "FloatingCanvasWindow", _FloatingWindow)
    monkeypatch.setattr(
        mod,
        "Qt",
        SimpleNamespace(WA_DeleteOnClose=1, Window=2, NonModal=3, Tool=4),
    )

    class _Pivot:
        def __init__(self) -> None:
            self.items = {"Input": object(), "Output": object()}
            self.current_route_key: str | None = "Input"
            self.insert_calls: list[tuple[int, str]] = []

        def currentRouteKey(self) -> str | None:
            return self.current_route_key

        def removeWidget(self, label: str) -> None:
            self.items.pop(label, None)
            if self.current_route_key == label:
                self.current_route_key = None

        def insertWidget(self, index: int, label: str, item: object) -> None:
            self.insert_calls.append((index, label))
            keys = [key for key in self.items if key != label]
            if index < 0 or index > len(keys):
                index = len(keys)
            keys.insert(index, label)
            values = dict(self.items)
            values[label] = item
            self.items = {key: values[key] for key in keys}

        def setCurrentItem(self, label: str) -> None:
            self.current_route_key = label

        def setVisible(self, _visible: bool) -> None:
            return None

    class _Stack:
        def removeWidget(self, _widget) -> None:
            return None

        def insertWidget(self, _index: int, _widget) -> None:
            return None

        def setCurrentIndex(self, _index: int) -> None:
            return None

    visibility_calls: list[bool] = []
    fake = SimpleNamespace(
        canvas_map={"Input": _Widget(), "Output": _Widget()},
        wrapper_map={"Input": object(), "Output": object()},
        tab_indices={"Input": 0, "Output": 1},
        floating_windows={},
        generation_titlebar_control_registry=None,
        pivot=_Pivot(),
        stack=_Stack(),
        canvas_region=SimpleNamespace(isVisible=lambda: True),
        visibility_changed=SimpleNamespace(
            emit=lambda visible: visibility_calls.append(visible)
        ),
        window=lambda: SimpleNamespace(windowIcon=lambda: object()),
        _pivot_item_stylesheet=lambda: "",
    )
    fake.update_tab_visibility = lambda: mod.CanvasTabManager.update_tab_visibility(
        fake
    )
    fake.all_tabs_empty = lambda: mod.CanvasTabManager.all_tabs_empty(fake)
    fake.undock_tab = lambda label: mod.CanvasTabManager.undock_tab(fake, label)

    mod.CanvasTabManager.undock_tab(fake, "Output")
    created_windows["Output"].redock_callback(fake.canvas_map["Output"], "Output")

    assert (1, "Output") in fake.pivot.insert_calls
    assert fake.tab_indices["Output"] == 1
    assert visibility_calls == [True]


def test_redock_output_after_unavailable_input_shows_output_canvas() -> None:
    """Redocking Output should not reactivate an unavailable Input canvas."""

    _app()
    mod = _import_canvas_module()
    manager = mod.CanvasTabManager(
        pages=(
            mod.CanvasHostPage(
                label="Input",
                widget=QWidget(),
                fallback_label="Output",
            ),
            mod.CanvasHostPage(label="Output", widget=QWidget()),
        )
    )

    manager.set_canvas_available(
        "Input",
        False,
        reason="No input canvas nodes",
        fallback_label="Output",
    )
    manager.undock_tab("Output")
    floating_output = manager.floating_windows["Output"]
    floating_output.redock_callback(floating_output.canvas_widget, "Output")

    assert list(manager.pivot.items) == ["Output"]
    assert "Output (Empty)" not in manager.canvas_map
    assert manager.stack.indexOf(manager.wrapper_map["Input"]) == -1
    assert manager.stack.indexOf(manager.wrapper_map["Output"]) == 0
    assert manager.stack.currentWidget() is manager.wrapper_map["Output"]
