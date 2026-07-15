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

"""Characterization tests for shared reorderable tab base behavior."""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from types import ModuleType, SimpleNamespace

import pytest

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "reorderable base characterization tests require non-xdist execution",
        allow_module_level=True,
    )


def _clear_gui_stubs() -> None:
    """Drop lightweight GUI stubs so real modules can import cleanly."""
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "QCoreApplication"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    for name in list(sys.modules):
        if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
            sys.modules.pop(name, None)
    qframe = sys.modules.get("qframelesswindow")
    if qframe is not None and not hasattr(qframe, "WindowEffect"):
        for name in list(sys.modules):
            if name == "qframelesswindow" or name.startswith("qframelesswindow."):
                sys.modules.pop(name, None)
    sys.modules.pop("substitute.presentation.widgets.cursor_tooltip_filter", None)
    sys.modules.pop("substitute.presentation.workflows.reorderable_tabs_base", None)


def _import_base_module() -> ModuleType:
    """Import shared reorderable tab base module."""
    _clear_gui_stubs()
    return importlib.import_module(
        "substitute.presentation.workflows.reorderable_tabs_base"
    )


def test_check_index_decorator_returns_default_for_out_of_range_index() -> None:
    """Decorator should short-circuit and return configured fallback."""
    mod = _import_base_module()

    class _Container:
        items = [1]

    @mod.checkIndex("fallback")
    def _value_at(container, index: int) -> object:
        return container.items[index]

    container = _Container()
    assert _value_at(container, 0) == 1
    assert _value_at(container, 5) == "fallback"


def test_base_set_tab_shadow_enabled_propagates_to_all_items() -> None:
    """Changing tab-shadow setting should update every tab item exactly once."""
    mod = _import_base_module()
    item_calls: list[tuple[str, bool]] = []
    fake = SimpleNamespace(
        _isTabShadowEnabled=True,
        items=[
            SimpleNamespace(
                setShadowEnabled=lambda enabled: item_calls.append(("a", enabled))
            ),
            SimpleNamespace(
                setShadowEnabled=lambda enabled: item_calls.append(("b", enabled))
            ),
        ],
        isTabShadowEnabled=lambda: fake._isTabShadowEnabled,
    )

    mod.ReorderableTabBarBase.setTabShadowEnabled(fake, False)

    assert fake._isTabShadowEnabled is False
    assert item_calls == [("a", False), ("b", False)]


def test_base_set_scrollable_updates_item_min_width_by_mode() -> None:
    """setScrollable should apply max/min width as item minimum widths."""
    mod = _import_base_module()
    widths: list[int] = []
    fake = SimpleNamespace(
        _isScrollable=False,
        _tabMaxWidth=240,
        _tabMinWidth=64,
        items=[SimpleNamespace(setMinimumWidth=lambda width: widths.append(width))],
    )

    mod.ReorderableTabBarBase.setScrollable(fake, True)
    mod.ReorderableTabBarBase.setScrollable(fake, False)

    assert widths == [240, 64]
    assert fake._isScrollable is False


def test_base_set_tabs_closable_routes_through_display_mode() -> None:
    """setTabsClosable should map bool to shared close-mode enum values."""
    mod = _import_base_module()
    modes: list[object] = []
    fake = SimpleNamespace(setCloseButtonDisplayMode=lambda mode: modes.append(mode))

    mod.ReorderableTabBarBase.setTabsClosable(fake, True)
    mod.ReorderableTabBarBase.setTabsClosable(fake, False)

    assert modes == [
        mod.ReorderableCloseButtonDisplayMode.ALWAYS,
        mod.ReorderableCloseButtonDisplayMode.NEVER,
    ]


def test_tab_tool_button_normalize_icon_state_handles_invalid_and_valid_inputs() -> (
    None
):
    """Icon-state normalization should coerce invalid payloads to a safe Qt enum."""
    mod = _import_base_module()

    normalize = mod.ReorderableTabToolButton._normalize_icon_state
    assert normalize(None) == mod.QIcon.State.Off
    assert normalize("invalid") == mod.QIcon.State.Off
    assert normalize(mod.QIcon.State.On) == mod.QIcon.State.On


def test_tab_tool_button_resolve_themed_icon_preserves_non_fluent_icons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Themed icon resolution should colorize Fluent icons but preserve QIcon objects."""
    mod = _import_base_module()

    plain_icon = mod.QIcon()
    assert mod.ReorderableTabToolButton._resolve_themed_icon(plain_icon) is plain_icon

    monkeypatch.setattr(
        mod.FluentIcon.CLOSE,
        "icon",
        lambda **_kwargs: mod.QIcon(),
    )
    themed_icon = mod.ReorderableTabToolButton._resolve_themed_icon(
        mod.FluentIcon.CLOSE
    )
    assert isinstance(themed_icon, mod.QIcon)


def test_tab_tool_button_draw_icon_signature_keeps_safe_default_state() -> None:
    """Draw signature default must remain a valid Qt icon state, never None."""
    mod = _import_base_module()
    signature = inspect.signature(mod.ReorderableTabToolButton._drawIcon)

    state_default = signature.parameters["state"].default
    assert state_default == mod.QIcon.State.Off


def test_tab_item_paint_event_does_not_call_super_paint_event() -> None:
    """Custom tab paint flow should avoid base paint to prevent duplicate text rendering."""
    mod = _import_base_module()
    source = inspect.getsource(mod.ReorderableTabItemBase.paintEvent)

    assert "super().paintEvent(event)" not in source


def test_tab_item_installs_cursor_anchored_tooltip_filter() -> None:
    """Tab items should install the shared cursor tooltip filter."""

    mod = _import_base_module()
    source = inspect.getsource(mod.ReorderableTabItemBase._initWidget)

    assert "install_cursor_tooltip_filter" in source
    assert "show_delay_ms=1000" in source
