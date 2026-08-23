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

"""Test editor-panel hidden-field visibility contracts."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch


class _Widget:
    """Record visibility and Qt-style dynamic properties."""

    def __init__(
        self,
        parent: _Parent | None = None,
        properties: dict[str, object] | None = None,
    ) -> None:
        """Initialize widget state."""

        self.visible = True
        self._parent = parent
        self._properties = dict(properties or {})

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record a visibility update."""

        self.visible = visible

    def property(self, name: str) -> object | None:
        """Return one dynamic property."""

        return self._properties.get(name)

    def parentWidget(self) -> _Parent | None:  # noqa: N802
        """Return the parent widget."""

        return self._parent


class _LayoutItem:
    """Expose one layout widget."""

    def __init__(self, widget: _Widget) -> None:
        """Store the layout widget."""

        self._widget = widget

    def widget(self) -> _Widget:
        """Return the layout widget."""

        return self._widget


class _Layout:
    """Expose indexed layout widgets."""

    def __init__(self, widgets: list[_Widget]) -> None:
        """Store layout widgets."""

        self._widgets = widgets

    def count(self) -> int:
        """Return number of widgets."""

        return len(self._widgets)

    def itemAt(self, index: int) -> _LayoutItem:  # noqa: N802
        """Return one layout item."""

        return _LayoutItem(self._widgets[index])


class _Parent:
    """Expose one child layout."""

    def __init__(self, layout: _Layout) -> None:
        """Store the child layout."""

        self._layout = layout

    def layout(self) -> _Layout:
        """Return the child layout."""

        return self._layout


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_set_hidden_field_keys_hides_row_column_and_dividers(
    monkeypatch: MonkeyPatch,
) -> None:
    """Hidden key propagation should toggle row, column, and divider visibility."""

    module = _panel_module()
    import shiboken6

    monkeypatch.setattr(shiboken6, "isValid", lambda _object: True)

    row_key = ("CubeA", "MaskNode", "seed")
    column_key = ("CubeA", "MaskNode", "seed_col")
    row_divider = _Widget()
    row_widget = _Widget()
    row_container = _Widget()
    horizontal_divider = _Widget()
    column_key_property = list(column_key)

    vertical_divider = _Widget(
        properties={"vertical_divider_for_field": column_key_property}
    )
    parent_layout = _Layout([vertical_divider])
    column_parent = _Parent(parent_layout)
    column_widget = _Widget(
        parent=column_parent,
        properties={"field_key": column_key_property},
    )
    input_widget = _Widget()
    panel = SimpleNamespace(
        row_widgets={
            row_key: (row_divider, row_widget),
            column_key: (horizontal_divider, _Widget()),
        },
        col_widgets={
            column_key: (row_container, column_widget, input_widget),
        },
    )

    module.EditorPanel.set_hidden_field_keys(panel, {"seed", "seed_col"})

    assert row_divider.visible is False
    assert row_widget.visible is False
    assert column_widget.visible is False
    assert vertical_divider.visible is False
    assert row_container.visible is False
    assert horizontal_divider.visible is False
