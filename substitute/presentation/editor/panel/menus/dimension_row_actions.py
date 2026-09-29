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

"""Bind and render Qt context menus for grouped dimension rows."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import RoundMenu  # type: ignore[import-untyped]

from substitute.application.node_behavior import infer_dimension_field_pairs
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from substitute.presentation.widgets.menu_model import MenuEntry, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.widgets.qfluent_submenu_interaction import (
    install_submenu_click_openers,
)

from .dimension_commands import (
    can_use_dimension_actions,
    context_widgets_for_value_widget,
)
from .dimension_contract import (
    DimensionContextMenuContent,
    DimensionRowBinding,
    DimensionSide,
)
from .dimension_menu_projection import dimension_menu_entries


def bind_dimension_row_actions(
    *,
    row_container: QWidget,
    fields: list[tuple[str, QWidget]],
    column_widgets: Mapping[str, QWidget],
    dimension_preset_source: DimensionPresetCatalogSource | None = None,
) -> DimensionRowActions | None:
    """Attach supported dimension actions to one eligible grouped row."""

    binding = _dimension_row_binding(fields, column_widgets)
    if binding is None or not can_use_dimension_actions(binding):
        return None
    row_container.setProperty(
        "dimension_field_group",
        [binding.pair.width_key, binding.pair.height_key],
    )
    actions = DimensionRowActions(
        binding=binding,
        dimension_preset_source=dimension_preset_source,
    )
    actions.bind(
        widget=row_container,
        side=None,
        position_mapper=row_container.mapToGlobal,
    )
    actions.bind(widget=binding.width_column, side=DimensionSide.WIDTH)
    actions.bind(widget=binding.height_column, side=DimensionSide.HEIGHT)
    for widget in context_widgets_for_value_widget(binding.width_widget):
        actions.bind(widget=widget, side=DimensionSide.WIDTH)
    for widget in context_widgets_for_value_widget(binding.height_widget):
        actions.bind(widget=widget, side=DimensionSide.HEIGHT)
    return actions


class DimensionRowActions:
    """Own Qt menu binding and presentation for one grouped dimension row."""

    def __init__(
        self,
        *,
        binding: DimensionRowBinding,
        dimension_preset_source: DimensionPresetCatalogSource | None,
    ) -> None:
        """Store the row binding and shared preset owner."""

        self._binding = binding
        self._dimension_preset_source = dimension_preset_source
        self._content = DimensionContextMenuContent.FULL

    def show_save_only(self) -> None:
        """Restrict the row menu to saving its current dimensions."""

        self._content = DimensionContextMenuContent.SAVE_ONLY

    def bind(
        self,
        *,
        widget: QWidget,
        side: DimensionSide | None,
        position_mapper: Callable[[QPoint], QPoint] | None = None,
    ) -> None:
        """Bind this menu owner to one row interaction surface."""

        def show_menu(position: QPoint) -> None:
            """Show the current context-menu presentation for this widget."""

            self._show(
                source_widget=widget,
                position=position,
                fixed_side=side,
                position_mapper=position_mapper,
            )

        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(show_menu)

    def field_action_entries(
        self,
        context: FieldActionContext,
    ) -> tuple[MenuEntry, ...]:
        """Return node-menu actions without assuming a clicked dimension side."""

        del context
        return dimension_menu_entries(
            binding=self._binding,
            anchor_side=None,
            dimension_preset_source=self._dimension_preset_source,
            content=self._content,
        )

    def field_actions_available(self) -> bool:
        """Return whether the current dimension policy exposes any valid action."""

        return bool(
            dimension_menu_entries(
                binding=self._binding,
                anchor_side=None,
                dimension_preset_source=self._dimension_preset_source,
                content=self._content,
            )
        )

    def _show(
        self,
        *,
        source_widget: QWidget,
        position: QPoint,
        fixed_side: DimensionSide | None,
        position_mapper: Callable[[QPoint], QPoint] | None,
    ) -> None:
        """Render and open the menu using the row's current presentation."""

        anchor_side = fixed_side or _side_for_row_position(self._binding, position)
        menu = build_dimension_context_menu(
            source_widget=source_widget,
            binding=self._binding,
            anchor_side=anchor_side,
            dimension_preset_source=self._dimension_preset_source,
            content=self._content,
        )
        global_position = (
            position_mapper(position)
            if position_mapper is not None
            else source_widget.mapToGlobal(position)
        )
        menu.exec(global_position)


def build_dimension_context_menu(
    *,
    source_widget: QWidget,
    binding: DimensionRowBinding,
    anchor_side: DimensionSide | None,
    dimension_preset_source: DimensionPresetCatalogSource | None,
    include_swap: bool = True,
    content: DimensionContextMenuContent = DimensionContextMenuContent.FULL,
) -> RoundMenu:
    """Render dimension menu entries for one Qt presentation surface."""

    entries = dimension_menu_entries(
        binding=binding,
        anchor_side=anchor_side,
        dimension_preset_source=dimension_preset_source,
        include_swap=include_swap,
        content=content,
    )
    menu = QFluentMenuRenderer(parent=source_widget).render(MenuModel(entries=entries))
    install_submenu_click_openers(menu)
    return menu


def _side_for_row_position(
    binding: DimensionRowBinding,
    position: QPoint,
) -> DimensionSide:
    """Return the dimension side closest to a row-local context-menu position."""

    if binding.width_column.geometry().contains(position):
        return DimensionSide.WIDTH
    if binding.height_column.geometry().contains(position):
        return DimensionSide.HEIGHT
    width_distance = abs(position.x() - binding.width_column.geometry().center().x())
    height_distance = abs(position.x() - binding.height_column.geometry().center().x())
    if width_distance <= height_distance:
        return DimensionSide.WIDTH
    return DimensionSide.HEIGHT


def _dimension_row_binding(
    fields: list[tuple[str, QWidget]],
    column_widgets: Mapping[str, QWidget],
) -> DimensionRowBinding | None:
    """Return dimension-row binding metadata for an exact two-field pair."""

    if len(fields) != 2:
        return None
    pairs = infer_dimension_field_pairs(tuple(label for label, _widget in fields))
    if len(pairs) != 1:
        return None
    widgets_by_label = dict(fields)
    pair = pairs[0]
    width_widget = widgets_by_label.get(pair.width_key)
    height_widget = widgets_by_label.get(pair.height_key)
    width_column = column_widgets.get(pair.width_key)
    height_column = column_widgets.get(pair.height_key)
    if (
        width_widget is None
        or height_widget is None
        or width_column is None
        or height_column is None
    ):
        return None
    return DimensionRowBinding(
        pair=pair,
        width_widget=width_widget,
        height_widget=height_widget,
        width_column=width_column,
        height_column=height_column,
    )


__all__ = [
    "DimensionRowActions",
    "bind_dimension_row_actions",
    "build_dimension_context_menu",
]
