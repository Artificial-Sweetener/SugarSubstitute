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

"""Bind context-menu actions for grouped dimension rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, TypeGuard, cast

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import app_text

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import RoundMenu  # type: ignore[import-untyped]

from substitute.application.node_behavior import (
    DimensionFieldPair,
    infer_dimension_field_pairs,
)
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetCatalogSource,
    DimensionPresetItem,
    DimensionPresetSection,
)
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSection,
    MenuSeparator,
    MenuSubmenu,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.presentation.widgets.qfluent_submenu_interaction import (
    install_submenu_click_openers,
)

SWAP_DIMENSION_ACTION_TEXT: ApplicationMessage = app_text("Swap width & height")
SET_DIMENSIONS_MENU_TEXT: ApplicationMessage = app_text("Set dimensions")
SAVE_CURRENT_DIMENSIONS_MENU_TEXT: ApplicationMessage = app_text(
    "Save current dimensions"
)
SAVE_GLOBALLY_ACTION_TEXT: ApplicationMessage = app_text("Save globally")
SET_RATIO_BY_WIDTH_MENU_TEXT: ApplicationMessage = app_text("Set ratio by Width")
SET_RATIO_BY_HEIGHT_MENU_TEXT: ApplicationMessage = app_text("Set ratio by Height")
LANDSCAPE_ASPECT_RATIO_MENU_TEXT: ApplicationMessage = app_text("Landscape")
PORTRAIT_ASPECT_RATIO_MENU_TEXT: ApplicationMessage = app_text("Portrait")


class DimensionSide(Enum):
    """Identify which dimension field anchors a row action."""

    WIDTH = "width"
    HEIGHT = "height"


class DimensionContextMenuContent(Enum):
    """Select the dimension actions exposed by one presentation surface."""

    FULL = "full"
    SAVE_ONLY = "save_only"


@dataclass(frozen=True)
class AspectRatioPreset:
    """Describe one width-to-height aspect-ratio menu option."""

    label: str
    width_units: int
    height_units: int


@dataclass(frozen=True)
class DimensionRowBinding:
    """Store widgets and columns for one actionable dimension row."""

    pair: DimensionFieldPair
    width_widget: QWidget
    height_widget: QWidget
    width_column: QWidget
    height_column: QWidget


LANDSCAPE_ASPECT_RATIOS = (
    AspectRatioPreset("1:1", 1, 1),
    AspectRatioPreset("5:4", 5, 4),
    AspectRatioPreset("4:3", 4, 3),
    AspectRatioPreset("3:2", 3, 2),
    AspectRatioPreset("16:9", 16, 9),
    AspectRatioPreset("2:1", 2, 1),
    AspectRatioPreset("21:9", 21, 9),
)

PORTRAIT_ASPECT_RATIOS = (
    AspectRatioPreset("1:1", 1, 1),
    AspectRatioPreset("4:5", 4, 5),
    AspectRatioPreset("3:4", 3, 4),
    AspectRatioPreset("2:3", 2, 3),
    AspectRatioPreset("9:16", 9, 16),
    AspectRatioPreset("1:2", 1, 2),
    AspectRatioPreset("9:21", 9, 21),
)


def bind_dimension_row_actions(
    *,
    row_container: QWidget,
    fields: list[tuple[str, QWidget]],
    column_widgets: Mapping[str, QWidget],
    dimension_preset_source: DimensionPresetCatalogSource | None = None,
) -> DimensionRowActions | None:
    """Attach supported dimension actions to one eligible grouped row."""

    binding = _dimension_row_binding(fields, column_widgets)
    if binding is None or not _can_use_dimension_actions(binding):
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
    actions.bind(
        widget=binding.width_column,
        side=DimensionSide.WIDTH,
    )
    actions.bind(
        widget=binding.height_column,
        side=DimensionSide.HEIGHT,
    )
    for widget in _context_widgets_for_value_widget(binding.width_widget):
        actions.bind(
            widget=widget,
            side=DimensionSide.WIDTH,
        )
    for widget in _context_widgets_for_value_widget(binding.height_widget):
        actions.bind(
            widget=widget,
            side=DimensionSide.HEIGHT,
        )
    return actions


class DimensionRowActions:
    """Own the context-menu presentation for one grouped dimension row."""

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


def apply_aspect_ratio(
    binding: DimensionRowBinding,
    *,
    anchor_side: DimensionSide,
    preset: AspectRatioPreset,
) -> None:
    """Apply a ratio while preserving the clicked dimension side."""

    if anchor_side is DimensionSide.WIDTH:
        anchor_value = _read_field_widget_value(binding.width_widget)
        write_target = _field_value_writer(binding.height_widget)
        if not _is_numeric_value(anchor_value) or write_target is None:
            return
        target_value = round(
            float(anchor_value) * preset.height_units / preset.width_units
        )
        write_target(int(target_value))
        return

    anchor_value = _read_field_widget_value(binding.height_widget)
    write_target = _field_value_writer(binding.width_widget)
    if not _is_numeric_value(anchor_value) or write_target is None:
        return
    target_value = round(float(anchor_value) * preset.width_units / preset.height_units)
    write_target(int(target_value))


def apply_saved_dimensions(
    binding: DimensionRowBinding,
    *,
    width: int,
    height: int,
) -> None:
    """Apply one saved absolute dimension pair to both row widgets."""

    write_width = _field_value_writer(binding.width_widget)
    write_height = _field_value_writer(binding.height_widget)
    if write_width is None or write_height is None:
        return
    write_width(width)
    write_height(height)


def build_dimension_context_menu(
    *,
    source_widget: QWidget,
    binding: DimensionRowBinding,
    anchor_side: DimensionSide | None,
    dimension_preset_source: DimensionPresetCatalogSource | None,
    include_swap: bool = True,
    content: DimensionContextMenuContent = DimensionContextMenuContent.FULL,
) -> RoundMenu:
    """Build reusable dimension actions for the requested presentation surface."""

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


def dimension_menu_entries(
    *,
    binding: DimensionRowBinding,
    anchor_side: DimensionSide | None,
    dimension_preset_source: DimensionPresetCatalogSource | None,
    include_swap: bool = True,
    content: DimensionContextMenuContent = DimensionContextMenuContent.FULL,
) -> tuple[MenuEntry, ...]:
    """Return current dimension actions for any presentation surface."""

    entries: list[MenuEntry] = []
    if content is DimensionContextMenuContent.FULL and include_swap:
        entries.append(
            MenuItem(
                "dimension.swap",
                SWAP_DIMENSION_ACTION_TEXT,
                callback=lambda: _swap_dimension_values(binding),
            )
        )
    saved_dimensions_model = (
        dimension_preset_source.current_dimension_preset_catalog()
        if dimension_preset_source is not None
        else None
    )
    if content is DimensionContextMenuContent.FULL:
        saved_dimensions_entry = _saved_dimensions_entry(
            binding,
            saved_dimensions_model,
        )
        if saved_dimensions_entry is not None:
            entries.append(saved_dimensions_entry)
        ratio_anchor_sides = (
            (anchor_side,)
            if anchor_side is not None
            else (DimensionSide.WIDTH, DimensionSide.HEIGHT)
        )
        entries.extend(
            _aspect_ratio_entry(binding, ratio_anchor_side)
            for ratio_anchor_side in ratio_anchor_sides
        )
    save_entry = _save_current_dimensions_entry(
        binding,
        dimension_preset_source,
        saved_dimensions_model,
    )
    if save_entry is not None:
        if entries:
            entries.append(MenuSeparator())
        entries.append(save_entry)
    return tuple(entries)


def _saved_dimensions_entry(
    binding: DimensionRowBinding,
    menu_model: DimensionPresetCatalog | None,
) -> MenuSubmenu | None:
    """Return the saved dimensions submenu when saved presets exist."""

    if menu_model is None or not menu_model.sections:
        return None

    return MenuSubmenu(
        SET_DIMENSIONS_MENU_TEXT,
        entries=(
            _saved_dimension_orientation_entry(
                title=PORTRAIT_ASPECT_RATIO_MENU_TEXT,
                binding=binding,
                sections=menu_model.sections,
                landscape=False,
            ),
            _saved_dimension_orientation_entry(
                title=LANDSCAPE_ASPECT_RATIO_MENU_TEXT,
                binding=binding,
                sections=menu_model.sections,
                landscape=True,
            ),
        ),
    )


def _saved_dimension_orientation_entry(
    *,
    title: str,
    binding: DimensionRowBinding,
    sections: tuple[DimensionPresetSection, ...],
    landscape: bool,
) -> MenuSubmenu:
    """Return one orientation submenu grouped by preset specificity sections."""

    entries: list[MenuEntry] = []
    for section_index, section in enumerate(sections):
        if section_index > 0:
            entries.append(MenuSeparator())
        entries.append(
            MenuSection(
                entries=_saved_dimension_entries(
                    binding=binding,
                    presets=section.presets,
                    landscape=landscape,
                ),
                title=section.title,
            )
        )
    return MenuSubmenu(title, entries=tuple(entries))


def _saved_dimension_entries(
    *,
    binding: DimensionRowBinding,
    presets: tuple[DimensionPresetItem, ...],
    landscape: bool,
) -> tuple[MenuItem, ...]:
    """Return saved dimension actions for one specificity section."""

    entries: list[MenuItem] = []
    for preset in presets:
        width, height = _oriented_dimensions(preset, landscape=landscape)
        entries.append(
            MenuItem(
                f"dimension.saved.{width}x{height}.{preset.label}",
                _saved_dimension_action_text(preset, width, height),
                callback=_saved_dimension_callback(
                    binding,
                    width=width,
                    height=height,
                ),
            )
        )
    return tuple(entries)


def _saved_dimension_callback(
    binding: DimensionRowBinding,
    *,
    width: int,
    height: int,
) -> Callable[[], None]:
    """Return a callback that applies one saved dimension preset."""

    return lambda: apply_saved_dimensions(binding, width=width, height=height)


def _saved_dimension_action_text(
    preset: DimensionPresetItem,
    width: int,
    height: int,
) -> str:
    """Return readable action text for one oriented saved dimension."""

    dimension_text = f"{width} x {height}"
    canonical_text = f"{preset.short_edge} x {preset.long_edge}"
    if preset.label.strip() in {canonical_text, dimension_text}:
        return dimension_text
    return f"{preset.label} {dimension_text}"


def _save_current_dimensions_entry(
    binding: DimensionRowBinding,
    dimension_preset_source: DimensionPresetCatalogSource | None,
    menu_model: DimensionPresetCatalog | None,
) -> MenuSubmenu | None:
    """Return save actions for the current dimension row values."""

    if dimension_preset_source is None or menu_model is None:
        return None
    current_dimensions = _current_positive_dimensions(binding)
    if current_dimensions is None:
        return None
    width, height = current_dimensions
    if not menu_model.can_save_globally and menu_model.model_save_label is None:
        return None

    entries: list[MenuItem] = []
    if menu_model.can_save_globally:
        entries.append(
            MenuItem(
                "dimension.save.global",
                SAVE_GLOBALLY_ACTION_TEXT,
                callback=lambda: (
                    dimension_preset_source.save_current_dimensions_globally(
                        width,
                        height,
                    )
                ),
            )
        )

    if menu_model.model_save_label is not None:
        entries.append(
            MenuItem(
                "dimension.save.model",
                app_text("Save for %1", menu_model.model_save_label),
                callback=lambda: (
                    dimension_preset_source.save_current_dimensions_for_model(
                        width,
                        height,
                    )
                ),
            )
        )
    return MenuSubmenu(SAVE_CURRENT_DIMENSIONS_MENU_TEXT, entries=tuple(entries))


def _oriented_dimensions(
    preset: DimensionPresetItem,
    *,
    landscape: bool,
) -> tuple[int, int]:
    """Return width and height for one saved preset orientation."""

    if landscape:
        return preset.long_edge, preset.short_edge
    return preset.short_edge, preset.long_edge


def _aspect_ratio_entry(
    binding: DimensionRowBinding,
    anchor_side: DimensionSide,
) -> MenuSubmenu:
    """Return the nested aspect-ratio menu for one anchor side."""

    return MenuSubmenu(
        _set_ratio_menu_text(anchor_side),
        entries=(
            MenuSubmenu(
                LANDSCAPE_ASPECT_RATIO_MENU_TEXT,
                entries=_aspect_ratio_entries(
                    binding=binding,
                    anchor_side=anchor_side,
                    presets=LANDSCAPE_ASPECT_RATIOS,
                ),
            ),
            MenuSubmenu(
                PORTRAIT_ASPECT_RATIO_MENU_TEXT,
                entries=_aspect_ratio_entries(
                    binding=binding,
                    anchor_side=anchor_side,
                    presets=PORTRAIT_ASPECT_RATIOS,
                ),
            ),
        ),
    )


def _aspect_ratio_entries(
    *,
    binding: DimensionRowBinding,
    anchor_side: DimensionSide,
    presets: tuple[AspectRatioPreset, ...],
) -> tuple[MenuItem, ...]:
    """Return aspect-ratio preset actions for one submenu."""

    return tuple(
        MenuItem(
            f"dimension.aspect.{anchor_side.value}.{preset.label}",
            preset.label,
            callback=_aspect_ratio_callback(
                binding,
                anchor_side=anchor_side,
                preset=preset,
            ),
        )
        for preset in presets
    )


def _aspect_ratio_callback(
    binding: DimensionRowBinding,
    *,
    anchor_side: DimensionSide,
    preset: AspectRatioPreset,
) -> Callable[[], None]:
    """Return a callback that applies one aspect-ratio preset."""

    return lambda: apply_aspect_ratio(
        binding,
        anchor_side=anchor_side,
        preset=preset,
    )


def _set_ratio_menu_text(anchor_side: DimensionSide) -> str:
    """Return the aspect-ratio submenu title for one anchor side."""

    if anchor_side is DimensionSide.WIDTH:
        return SET_RATIO_BY_WIDTH_MENU_TEXT
    return SET_RATIO_BY_HEIGHT_MENU_TEXT


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


def _current_positive_dimensions(
    binding: DimensionRowBinding,
) -> tuple[int, int] | None:
    """Return current positive integer dimensions for save actions."""

    width_value = _read_field_widget_value(binding.width_widget)
    height_value = _read_field_widget_value(binding.height_widget)
    if not _is_numeric_value(width_value) or not _is_numeric_value(height_value):
        return None
    width = int(round(float(width_value)))
    height = int(round(float(height_value)))
    if width <= 0 or height <= 0:
        return None
    return width, height


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


def _can_use_dimension_actions(binding: DimensionRowBinding) -> bool:
    """Return whether both dimension widgets expose supported value accessors."""

    return (
        _field_value_reader(binding.width_widget) is not None
        and _field_value_reader(binding.height_widget) is not None
        and _field_value_writer(binding.width_widget) is not None
        and _field_value_writer(binding.height_widget) is not None
    )


def _swap_dimension_values(binding: DimensionRowBinding) -> None:
    """Swap width and height widget values for one dimension row."""

    width_value = _read_field_widget_value(binding.width_widget)
    height_value = _read_field_widget_value(binding.height_widget)
    write_width = _field_value_writer(binding.width_widget)
    write_height = _field_value_writer(binding.height_widget)
    if (
        width_value is None
        or height_value is None
        or write_width is None
        or write_height is None
    ):
        return
    write_width(height_value)
    write_height(width_value)


def _context_widgets_for_value_widget(widget: QWidget) -> tuple[QWidget, ...]:
    """Return widgets that should open the dimension context menu for a value."""

    target = _field_value_target(widget)
    if isinstance(target, QWidget) and target is not widget:
        return (widget, target)
    return (widget,)


def _field_value_target(widget: QWidget) -> Any:
    """Return the inner value-owning widget for composite field controls."""

    return getattr(widget, "spinbox", widget)


def _read_field_widget_value(widget: QWidget) -> object | None:
    """Return a supported field widget value, or ``None`` when unsupported."""

    reader = _field_value_reader(widget)
    if reader is None:
        return None
    return reader()


def _field_value_reader(widget: QWidget) -> Callable[[], object] | None:
    """Return a supported field widget getter without invoking it."""

    target = _field_value_target(widget)
    value = getattr(target, "value", None)
    if callable(value):
        return cast(Callable[[], object], value)
    text = getattr(target, "text", None)
    if callable(text):
        return cast(Callable[[], object], text)
    current_text = getattr(target, "currentText", None)
    if callable(current_text):
        return cast(Callable[[], object], current_text)
    return None


def _field_value_writer(widget: QWidget) -> Callable[[object], None] | None:
    """Return a supported field widget setter, or ``None`` when unsupported."""

    target = _field_value_target(widget)
    set_value = getattr(target, "setValue", None)
    if callable(set_value):
        return cast(Callable[[object], None], set_value)
    set_text = getattr(target, "setText", None)
    if callable(set_text):
        return cast(Callable[[object], None], set_text)
    set_current_text = getattr(target, "setCurrentText", None)
    if callable(set_current_text):
        return cast(Callable[[object], None], set_current_text)
    return None


def _is_numeric_value(value: object | None) -> TypeGuard[int | float]:
    """Return whether a widget value can anchor integer dimension math."""

    return isinstance(value, (int, float)) and not isinstance(value, bool)


__all__ = [
    "AspectRatioPreset",
    "DimensionContextMenuContent",
    "DimensionRowBinding",
    "DimensionRowActions",
    "DimensionSide",
    "LANDSCAPE_ASPECT_RATIOS",
    "PORTRAIT_ASPECT_RATIOS",
    "apply_saved_dimensions",
    "apply_aspect_ratio",
    "bind_dimension_row_actions",
    "build_dimension_context_menu",
    "dimension_menu_entries",
]
