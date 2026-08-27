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

"""Qualify search and hidden-field visibility through the field-sync owner."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from _pytest.monkeypatch import MonkeyPatch

import substitute.presentation.editor.panel.field_sync_controller as field_sync_mod
from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
    EditorPanelFieldSyncHost,
)


from tests.presentation.editor.panel.field_state.controller_support import (
    _CubeParent,
    _Widget,
)


def test_set_search_field_match_keys_reapplies_current_hidden_fields() -> None:
    """Field-search state should hide non-matches without changing policy hidden keys."""

    matching_key = ("CubeA", "KSampler", "sampler_name")
    hidden_key = ("CubeA", "KSampler", "seed")
    non_matching_key = ("CubeA", "KSampler", "cfg")
    matching_row = _Widget()
    hidden_row = _Widget()
    non_matching_row = _Widget()
    host = SimpleNamespace(
        _hidden_field_keys={hidden_key},
        _search_field_match_keys=None,
        _field_search_active=False,
        row_widgets={
            matching_key: (_Widget(), matching_row),
            hidden_key: (_Widget(), hidden_row),
            non_matching_key: (_Widget(), non_matching_row),
        },
        col_widgets={},
        card_wrappers={},
    )

    EditorPanelFieldSyncController(
        cast(EditorPanelFieldSyncHost, host)
    ).set_search_field_match_keys({matching_key}, active=True)

    assert host._hidden_field_keys == {hidden_key}
    assert host._search_field_match_keys == {matching_key}
    assert host._field_search_active is True
    assert matching_row.visible is True
    assert hidden_row.visible is False
    assert non_matching_row.visible is False


def test_apply_hidden_field_keys_hides_empty_cards_and_refreshes_height(
    monkeypatch: MonkeyPatch,
) -> None:
    """Card visibility should reflect hidden/search state and refresh on change."""

    reconciled: list[dict[object, object]] = []
    monkeypatch.setattr(
        field_sync_mod,
        "reconcile_node_card_body_separators",
        lambda rows: reconciled.append(dict(rows)),
    )
    cube_parent = _CubeParent()
    visible_key = ("CubeA", "NodeA", "visible")
    hidden_key = ("CubeA", "NodeA", "hidden")
    visible_row = _Widget()
    hidden_row = _Widget()
    card = _Widget(
        properties={"base_card_visible": True},
        parent=cube_parent,
    )
    host = SimpleNamespace(
        _hidden_field_keys=set(),
        _search_field_match_keys={visible_key},
        _field_search_active=True,
        row_widgets={
            visible_key: (_Widget(), visible_row),
            hidden_key: (_Widget(), hidden_row),
        },
        col_widgets={},
        card_wrappers={("CubeA", "NodeA"): card},
    )

    controller = EditorPanelFieldSyncController(cast(EditorPanelFieldSyncHost, host))
    controller.apply_hidden_field_keys({hidden_key})
    controller.set_search_field_match_keys(set(), active=True)

    assert visible_row.visible is False
    assert hidden_row.visible is False
    assert card.visible is False
    assert cube_parent.height_refreshes == 1
    assert reconciled


def test_apply_hidden_field_keys_updates_grouped_column_dividers() -> None:
    """Grouped column dividers should hide when only one column remains visible."""

    first_key = ("CubeA", "NodeA", "first")
    second_key = ("CubeA", "NodeA", "second")
    first_divider = _Widget(properties={"vertical_divider_for_field": first_key})
    second_divider = _Widget(properties={"vertical_divider_for_field": second_key})

    class _Layout:
        """Layout double exposing divider widgets."""

        def __init__(self, widgets: list[_Widget]) -> None:
            """Store ordered divider widgets."""

            self._widgets = widgets

        def count(self) -> int:
            """Return widget count."""

            return len(self._widgets)

        def itemAt(self, index: int) -> object:  # noqa: N802
            """Return a layout item for one widget."""

            return SimpleNamespace(widget=lambda: self._widgets[index])

    parent = SimpleNamespace(layout=lambda: _Layout([first_divider, second_divider]))
    row_container = _Widget()
    first_col = _Widget(properties={"field_key": first_key}, parent=parent)
    second_col = _Widget(properties={"field_key": second_key}, parent=parent)
    horizontal_divider = _Widget()
    host = SimpleNamespace(
        _hidden_field_keys=set(),
        _search_field_match_keys=None,
        _field_search_active=False,
        row_widgets={first_key: (horizontal_divider, _Widget())},
        col_widgets={
            first_key: (row_container, first_col, object()),
            second_key: (row_container, second_col, object()),
        },
        card_wrappers={},
    )

    EditorPanelFieldSyncController(
        cast(EditorPanelFieldSyncHost, host)
    ).apply_hidden_field_keys({second_key})

    assert first_col.visible is True
    assert second_col.visible is False
    assert row_container.visible is True
    assert first_divider.visible is False
    assert second_divider.visible is False
    assert horizontal_divider.visible is True
