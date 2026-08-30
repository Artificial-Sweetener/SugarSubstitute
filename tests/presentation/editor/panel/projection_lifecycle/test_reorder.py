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

"""Test projection lifecycle cube-widget reordering."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace


class _Widget:
    """Record parent changes made while reordering layout widgets."""

    def __init__(self) -> None:
        """Initialize parent-change recording."""

        self.parents: list[object | None] = []

    def setParent(self, parent: object | None) -> None:  # noqa: N802
        """Record one parent assignment."""

        self.parents.append(parent)


class _LayoutItem:
    """Expose one widget or spacer from an ordered layout."""

    def __init__(self, *, widget: _Widget | None = None, spacer: bool = False) -> None:
        """Initialize an item with one layout payload."""

        self._widget = widget
        self._spacer = spacer

    def widget(self) -> _Widget | None:
        """Return the contained widget when present."""

        return self._widget

    def spacerItem(self) -> object | None:  # noqa: N802
        """Return a spacer sentinel when present."""

        return object() if self._spacer else None


class _OrderedLayout:
    """Record ordered cube widget and spacing insertion."""

    def __init__(self, items: list[_LayoutItem]) -> None:
        """Initialize queued source items and added items."""

        self._items = items
        self.added: list[tuple[str, object]] = []

    def count(self) -> int:
        """Return remaining source item count."""

        return len(self._items)

    def takeAt(self, index: int) -> _LayoutItem:  # noqa: N802
        """Remove and return one source item."""

        return self._items.pop(index)

    def addSpacing(self, spacing: int) -> None:  # noqa: N802
        """Record one inserted spacing item."""

        self.added.append(("spacing", spacing))

    def addWidget(self, widget: _Widget) -> None:  # noqa: N802
        """Record one inserted cube widget."""

        self.added.append(("widget", widget))


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_reorder_cube_widgets_applies_stack_order_and_refreshes_links() -> None:
    """Reordering should rebuild layout order and refresh link/visibility state."""

    panel_module = _panel_module()
    first_widget = _Widget()
    second_widget = _Widget()
    layout = _OrderedLayout(
        [
            _LayoutItem(widget=first_widget),
            _LayoutItem(spacer=True),
            _LayoutItem(widget=second_widget),
        ]
    )
    registry_calls: list[str] = []
    panel = SimpleNamespace(
        CUBE_SPACING=panel_module.EditorPanel.CUBE_SPACING,
        _stack_order=["B", "A"],
        _cube_states=None,
        _layout=layout,
        cube_widgets={"A": first_widget, "B": second_widget},
        meta_registry=SimpleNamespace(
            update_node_link_widgets=lambda: registry_calls.append("node"),
            update_sampler_link_widgets=lambda: registry_calls.append("sampler"),
            update_scheduler_link_widgets=lambda: registry_calls.append("scheduler"),
        ),
        sanitize_prompt_link_state=lambda: registry_calls.append("prompt_state"),
        reconcile_prompt_link_state=lambda **_kwargs: None,
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "recompute"
        ),
    )
    panel._ordered_buffers = lambda: panel_module.EditorPanel._ordered_buffers(panel)
    panel._refresh_sampler_scheduler_link_state = lambda: (
        panel_module.EditorPanel._refresh_sampler_scheduler_link_state(panel)
    )
    panel._refresh_link_widgets = lambda: (
        panel_module.EditorPanel._refresh_link_widgets(panel)
    )

    panel_module.EditorPanel.reorder_cube_widgets(panel)

    assert layout.added == [
        ("spacing", panel_module.EditorPanel.CUBE_SPACING),
        ("widget", second_widget),
        ("spacing", panel_module.EditorPanel.CUBE_SPACING),
        ("widget", first_widget),
    ]
    assert registry_calls == [
        "prompt_state",
        "node",
        "sampler",
        "scheduler",
        "recompute",
    ]
