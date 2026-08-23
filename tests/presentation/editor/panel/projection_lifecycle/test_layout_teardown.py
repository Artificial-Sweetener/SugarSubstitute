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

"""Test full projection layout teardown."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


class _DisposableWidget:
    """Record deferred deletion of one layout widget."""

    def __init__(self) -> None:
        """Initialize deletion state."""

        self.deleted = False

    def deleteLater(self) -> None:  # noqa: N802
        """Record deferred deletion."""

        self.deleted = True


class _LayoutItem:
    """Expose one widget or nested layout from a clearable layout."""

    def __init__(
        self,
        *,
        widget: _DisposableWidget | None = None,
        layout: object | None = None,
    ) -> None:
        """Initialize one layout item payload."""

        self._widget = widget
        self._layout = layout

    def widget(self) -> _DisposableWidget | None:
        """Return the item widget."""

        return self._widget

    def layout(self) -> object | None:
        """Return the nested layout."""

        return self._layout


class _Layout:
    """Remove layout items in insertion order."""

    def __init__(self, items: list[_LayoutItem]) -> None:
        """Store removable items."""

        self._items = items

    def count(self) -> int:
        """Return remaining item count."""

        return len(self._items)

    def takeAt(self, index: int) -> _LayoutItem:  # noqa: N802
        """Remove and return one layout item."""

        return self._items.pop(index)


def _coordinator_module() -> ModuleType:
    """Return the production projection coordinator module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )


def _lifecycle_module() -> ModuleType:
    """Return the production projection lifecycle module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.projection_lifecycle"
    )


def test_clear_layout_resets_reveal_maps_and_deletes_layout_widgets(
    monkeypatch: MonkeyPatch,
) -> None:
    """Layout teardown should reset reveal maps and dispose tracked items."""

    coordinator_module = _coordinator_module()
    lifecycle_module = _lifecycle_module()
    debug_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        lifecycle_module,
        "log_debug",
        lambda _logger, message, **context: debug_calls.append((message, context)),
    )
    deleted_widget = _DisposableWidget()
    nested_layout = object()
    recursive_calls: list[object] = []
    cleanup_calls: list[str] = []
    panel = SimpleNamespace(
        cube_widgets={"CubeA": object()},
        cube_sections={"CubeA": object()},
        meta_registry=SimpleNamespace(
            cleanup_dead_node_link_widgets=lambda: cleanup_calls.append("node"),
            clear_node_link_title_surfaces=lambda: cleanup_calls.append("surfaces"),
        ),
        node_link_widgets={("CubeA", "identity"): object()},
        node_link_title_surfaces={("CubeA", "identity"): object()},
        row_widgets={"row": object()},
        col_widgets={"col": object()},
        input_widgets_by_field_key={("CubeA", "NodeA", "seed"): object()},
        card_wrappers={("CubeA", "NodeA"): object()},
        _cube_visibility_btns={"CubeA": object()},
        _cube_visibility_menus={"CubeA": object()},
        _layout=_Layout(
            [
                _LayoutItem(widget=deleted_widget),
                _LayoutItem(layout=nested_layout),
            ]
        ),
        cube_headers={"CubeA": object()},
        cube_positions={"CubeA": 12},
        _stack_order=["CubeA"],
        _cube_states={},
        _clear_layout_recursive=lambda layout: recursive_calls.append(layout),
        clear_model_field_load_progress=lambda: cleanup_calls.append("models"),
    )

    coordinator_module.EditorPanelProjectionCoordinator(panel).clear_layout()

    assert cleanup_calls == ["models", "node", "surfaces"]
    assert panel.cube_widgets == {}
    assert panel.cube_sections == {}
    assert panel.node_link_widgets == {}
    assert panel.node_link_title_surfaces == {}
    assert panel.row_widgets == {}
    assert panel.col_widgets == {}
    assert panel.input_widgets_by_field_key == {}
    assert panel.card_wrappers == {}
    assert panel._cube_visibility_btns == {}
    assert panel._cube_visibility_menus == {}
    assert panel.cube_headers == {}
    assert panel.cube_positions == {}
    assert deleted_widget.deleted is True
    assert recursive_calls == [nested_layout]
    assert debug_calls == [
        (
            "Clearing editor panel layout",
            {
                "card_wrapper_count": 1,
                "cube_position_count": 1,
                "cube_visibility_button_count": 1,
                "cube_visibility_menu_count": 1,
                "cube_widget_count": 1,
                "cube_header_count": 1,
                "node_link_widget_count": 1,
            },
        ),
        (
            "Cleared editor panel layout",
            {
                "card_wrapper_count": 0,
                "cube_position_count": 0,
                "cube_visibility_button_count": 0,
                "cube_visibility_menu_count": 0,
                "cube_widget_count": 0,
                "cube_header_count": 0,
                "node_link_widget_count": 0,
            },
        ),
    ]
