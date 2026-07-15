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

"""Contract tests for field-sync hidden-field visibility."""

from __future__ import annotations

import importlib
from types import SimpleNamespace


def _import_module():
    """Import the field-sync controller module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.field_sync_controller"
    )


class _Widget:
    """Widget double with visibility and dynamic-property support."""

    def __init__(self, parent=None, props: dict | None = None) -> None:
        self.visible = True
        self._parent = parent
        self._props = dict(props or {})

    def setVisible(self, visible: bool) -> None:
        """Record visibility changes."""

        self.visible = visible

    def property(self, name: str):
        """Return one dynamic property."""

        return self._props.get(name)

    def setProperty(self, name: str, value) -> None:
        """Set one dynamic property."""

        self._props[name] = value

    def parentWidget(self):
        """Return the parent widget."""

        return self._parent


class _LayoutItem:
    """Layout item wrapper exposing a widget."""

    def __init__(self, widget) -> None:
        self._widget = widget

    def widget(self):
        """Return the contained widget."""

        return self._widget


class _Layout:
    """Simple layout exposing count and itemAt."""

    def __init__(self, widgets: list[object]) -> None:
        self._widgets = widgets

    def count(self) -> int:
        """Return widget count."""

        return len(self._widgets)

    def itemAt(self, index: int):
        """Return layout item at one index."""

        return _LayoutItem(self._widgets[index])


class _Parent:
    """Widget double exposing a layout."""

    def __init__(self, layout: _Layout) -> None:
        self._layout = layout

    def layout(self) -> _Layout:
        """Return the child layout."""

        return self._layout


def test_apply_hidden_field_keys_hides_rows_columns_and_dividers() -> None:
    """Applying hidden keys should toggle all tracked row and column widgets."""

    mod = _import_module()
    row_key = ("CubeA", "MaskNode", "seed")
    col_key = ("CubeA", "MaskNode", "seed_col")
    row_divider = _Widget()
    row_widget = _Widget()
    row_container = _Widget()
    horizontal_divider = _Widget()
    vertical_divider = _Widget(props={"vertical_divider_for_field": list(col_key)})
    parent_layout = _Layout([vertical_divider])
    col_parent = _Parent(parent_layout)
    col_widget = _Widget(parent=col_parent, props={"field_key": list(col_key)})
    input_widget = _Widget()

    panel = SimpleNamespace(
        _hidden_field_keys=set(),
        row_widgets={
            row_key: (row_divider, row_widget),
            col_key: (horizontal_divider, _Widget()),
        },
        col_widgets={col_key: (row_container, col_widget, input_widget)},
    )

    mod.EditorPanelFieldSyncController(panel).apply_hidden_field_keys(
        {"seed", "seed_col"}
    )

    assert panel._hidden_field_keys == {"seed", "seed_col"}
    assert row_divider.visible is False
    assert row_widget.visible is False
    assert col_widget.visible is False
    assert vertical_divider.visible is False
    assert row_container.visible is False
    assert horizontal_divider.visible is False


def test_update_all_hidden_fields_clears_when_snapshot_is_missing() -> None:
    """Missing snapshots should clear the hidden-field set."""

    mod = _import_module()
    panel = SimpleNamespace(
        _hidden_field_keys={"seed"},
        row_widgets={},
        col_widgets={},
        _build_behavior_snapshot=lambda **_kwargs: None,
    )

    mod.EditorPanelFieldSyncController(panel).update_all_hidden_fields(
        search_hidden_keys={"scheduler"}
    )

    assert panel._hidden_field_keys == set()


def test_update_all_hidden_fields_merges_keys_across_aliases() -> None:
    """Snapshot application should merge hidden keys from every cube alias."""

    mod = _import_module()
    snapshot = SimpleNamespace(
        hidden_field_keys_by_alias={
            "CubeA": {"seed"},
            "CubeB": {("CubeB", "ksampler", "scheduler")},
        }
    )
    panel = SimpleNamespace(
        _hidden_field_keys=set(),
        row_widgets={},
        col_widgets={},
        _build_behavior_snapshot=lambda **_kwargs: snapshot,
    )

    mod.EditorPanelFieldSyncController(panel).update_all_hidden_fields()

    assert panel._hidden_field_keys == {
        "seed",
        ("CubeB", "ksampler", "scheduler"),
    }


def test_apply_hidden_field_keys_field_search_keeps_only_matching_rows_visible() -> (
    None
):
    """Field-search state should hide non-matching rows without mutating policy-hidden keys."""

    mod = _import_module()
    matching_key = ("CubeA", "KSampler", "sampler_name")
    non_matching_key = ("CubeA", "KSampler", "cfg")
    matching_divider = _Widget()
    matching_row = _Widget()
    non_matching_divider = _Widget()
    non_matching_row = _Widget()
    panel = SimpleNamespace(
        _hidden_field_keys=set(),
        _search_field_match_keys={matching_key},
        _field_search_active=True,
        row_widgets={
            matching_key: (matching_divider, matching_row),
            non_matching_key: (non_matching_divider, non_matching_row),
        },
        col_widgets={},
    )

    mod.EditorPanelFieldSyncController(panel).apply_hidden_field_keys(set())

    assert matching_divider.visible is True
    assert matching_row.visible is True
    assert non_matching_divider.visible is False
    assert non_matching_row.visible is False


def test_apply_hidden_field_keys_hides_card_when_all_local_rows_are_hidden() -> None:
    """Cards emptied by tuple-scoped hidden rows should hide and later reappear."""

    mod = _import_module()
    field_key = ("CubeA", "prompt_encode_style", "encode_style")
    row_divider = _Widget()
    row_widget = _Widget()
    card = _Widget(
        props={
            "base_card_visible": True,
            "has_title_controls": False,
        }
    )
    panel = SimpleNamespace(
        _hidden_field_keys=set(),
        row_widgets={field_key: (row_divider, row_widget)},
        col_widgets={},
        card_wrappers={("CubeA", "prompt_encode_style"): card},
    )

    mod.EditorPanelFieldSyncController(panel).apply_hidden_field_keys({field_key})

    assert row_divider.visible is False
    assert row_widget.visible is False
    assert card.visible is False

    mod.EditorPanelFieldSyncController(panel).apply_hidden_field_keys(set())

    assert row_divider.visible is True
    assert row_widget.visible is True
    assert card.visible is True


def test_apply_hidden_field_keys_keeps_empty_title_control_cards_visible() -> None:
    """Cards with title controls should remain visible when local rows are hidden."""

    mod = _import_module()
    field_key = ("CubeA", "vae_override", "vae_name")
    card = _Widget(
        props={
            "base_card_visible": True,
            "has_title_controls": True,
        }
    )
    panel = SimpleNamespace(
        _hidden_field_keys=set(),
        row_widgets={field_key: (_Widget(), _Widget())},
        col_widgets={},
        card_wrappers={("CubeA", "vae_override"): card},
    )

    mod.EditorPanelFieldSyncController(panel).apply_hidden_field_keys({field_key})

    assert card.visible is True


def test_apply_hidden_field_keys_preserves_policy_hidden_cards() -> None:
    """Empty-card visibility should not override node policy/search hidden state."""

    mod = _import_module()
    field_key = ("CubeA", "prompt_encode_style", "encode_style")
    card = _Widget(
        props={
            "base_card_visible": False,
            "has_title_controls": False,
        }
    )
    panel = SimpleNamespace(
        _hidden_field_keys=set(),
        row_widgets={field_key: (_Widget(), _Widget())},
        col_widgets={},
        card_wrappers={("CubeA", "prompt_encode_style"): card},
    )

    mod.EditorPanelFieldSyncController(panel).apply_hidden_field_keys(set())

    assert card.visible is False
