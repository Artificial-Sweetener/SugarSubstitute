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

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import QWidget
from qfluentwidgets import RoundMenu  # type: ignore[import-untyped]

from substitute.application.node_behavior import (
    DimensionFieldPair,
    infer_dimension_field_pairs,
)
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuItem,
    DimensionPresetMenuModel,
    DimensionPresetMenuSection,
    DimensionPresetMenuSource,
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
    dimension_preset_source: DimensionPresetMenuSource | None = None,
) -> None:
    """Attach supported dimension actions to one eligible grouped row."""

    binding = _dimension_row_binding(fields, column_widgets)
    if binding is None or not _can_use_dimension_actions(binding):
        return
    row_container.setProperty(
        "dimension_field_group",
        [binding.pair.width_key, binding.pair.height_key],
    )
    _bind_context_menu(
        widget=row_container,
        binding=binding,
        side=None,
        dimension_preset_source=dimension_preset_source,
        position_mapper=row_container.mapToGlobal,
    )
    _bind_context_menu(
        widget=binding.width_column,
        binding=binding,
        side=DimensionSide.WIDTH,
        dimension_preset_source=dimension_preset_source,
    )
    _bind_context_menu(
        widget=binding.height_column,
        binding=binding,
        side=DimensionSide.HEIGHT,
        dimension_preset_source=dimension_preset_source,
    )
    for widget in _context_widgets_for_value_widget(binding.width_widget):
        _bind_context_menu(
            widget=widget,
            binding=binding,
            side=DimensionSide.WIDTH,
            dimension_preset_source=dimension_preset_source,
        )
    for widget in _context_widgets_for_value_widget(binding.height_widget):
        _bind_context_menu(
            widget=widget,
            binding=binding,
            side=DimensionSide.HEIGHT,
            dimension_preset_source=dimension_preset_source,
        )


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


def _bind_context_menu(
    *,
    widget: QWidget,
    binding: DimensionRowBinding,
    side: DimensionSide | None,
    dimension_preset_source: DimensionPresetMenuSource | None,
    position_mapper: Callable[[QPoint], QPoint] | None = None,
) -> None:
    """Bind the dimension menu to one widget and optional fixed side."""

    def show_menu(position: QPoint) -> None:
        """Show the context menu for this bound widget."""

        _show_dimension_context_menu(
            widget,
            position,
            binding,
            side,
            dimension_preset_source,
            position_mapper,
        )

    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    widget.customContextMenuRequested.connect(show_menu)


def _show_dimension_context_menu(
    source_widget: QWidget,
    position: QPoint,
    binding: DimensionRowBinding,
    fixed_side: DimensionSide | None,
    dimension_preset_source: DimensionPresetMenuSource | None,
    position_mapper: Callable[[QPoint], QPoint] | None,
) -> None:
    """Show QFluent actions for one grouped dimension row."""

    anchor_side = fixed_side or _side_for_row_position(binding, position)
    entries: list[MenuEntry] = [
        MenuItem(
            "dimension.swap",
            SWAP_DIMENSION_ACTION_TEXT,
            callback=lambda: _swap_dimension_values(binding),
        )
    ]
    saved_dimensions_model = (
        dimension_preset_source.current_dimension_preset_menu_model()
        if dimension_preset_source is not None
        else None
    )
    saved_dimensions_entry = _saved_dimensions_entry(
        binding,
        saved_dimensions_model,
    )
    if saved_dimensions_entry is not None:
        entries.append(saved_dimensions_entry)
    entries.append(_aspect_ratio_entry(binding, anchor_side))
    save_entry = _save_current_dimensions_entry(
        binding,
        dimension_preset_source,
        saved_dimensions_model,
    )
    if save_entry is not None:
        entries.append(MenuSeparator())
        entries.append(save_entry)
    menu = QFluentMenuRenderer(parent=source_widget).render(
        MenuModel(entries=tuple(entries))
    )
    _install_submenu_click_openers_for_tree(menu)
    global_position = (
        position_mapper(position)
        if position_mapper is not None
        else source_widget.mapToGlobal(position)
    )
    menu.exec(global_position)


def _saved_dimensions_entry(
    binding: DimensionRowBinding,
    menu_model: DimensionPresetMenuModel | None,
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
    sections: tuple[DimensionPresetMenuSection, ...],
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
    presets: tuple[DimensionPresetMenuItem, ...],
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
    preset: DimensionPresetMenuItem,
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
    dimension_preset_source: DimensionPresetMenuSource | None,
    menu_model: DimensionPresetMenuModel | None,
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


def _install_submenu_click_openers_for_tree(menu: RoundMenu) -> None:
    """Install click-to-open behavior for every rendered submenu row."""

    for submenu in getattr(menu, "_subMenus", ()):
        if isinstance(submenu, RoundMenu):
            _install_submenu_click_opener(menu, submenu)
            _install_submenu_click_openers_for_tree(submenu)


def _install_submenu_click_opener(parent_menu: RoundMenu, submenu: RoundMenu) -> None:
    """Install click-to-open behavior for a QFluent submenu row widget."""

    item = getattr(submenu, "menuItem", None)
    view = getattr(parent_menu, "view", None)
    if item is None or view is None:
        return
    item_widget = getattr(view, "itemWidget", None)
    if not callable(item_widget):
        return
    widget = item_widget(item)
    if not isinstance(widget, QWidget):
        return

    opener = _SubmenuClickOpener(parent_menu, submenu, parent_menu)
    widget.installEventFilter(opener)
    openers = getattr(parent_menu, "_substitute_submenu_click_openers", None)
    if not isinstance(openers, list):
        openers = []
        setattr(parent_menu, "_substitute_submenu_click_openers", openers)
    openers.append(opener)


class _SubmenuClickOpener(QObject):
    """Open a QFluent submenu row on click without closing the parent menu."""

    def __init__(
        self,
        parent_menu: RoundMenu,
        submenu: RoundMenu,
        parent: QObject,
    ) -> None:
        """Store the parent/submenu pair controlled by this event filter."""

        super().__init__(parent)
        self._parent_menu = parent_menu
        self._submenu = submenu

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Consume submenu row clicks and open the child menu."""

        _ = watched
        if event.type() == QEvent.Type.MouseButtonPress:
            QTimer.singleShot(0, self._open_submenu)
            return True
        if event.type() == QEvent.Type.MouseButtonRelease:
            return True
        return super().eventFilter(watched, event)

    def _open_submenu(self) -> None:
        """Open the submenu immediately using QFluent's submenu placement logic."""

        item = getattr(self._submenu, "menuItem", None)
        if item is None:
            return
        setattr(self._parent_menu, "lastHoverItem", item)
        setattr(self._parent_menu, "lastHoverSubMenuItem", item)
        timer = getattr(self._parent_menu, "timer", None)
        if timer is not None:
            stop = getattr(timer, "stop", None)
            if callable(stop):
                stop()
        open_timeout = getattr(self._parent_menu, "_onShowMenuTimeOut", None)
        if callable(open_timeout):
            open_timeout()


def _oriented_dimensions(
    preset: DimensionPresetMenuItem,
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
    "DimensionRowBinding",
    "DimensionSide",
    "LANDSCAPE_ASPECT_RATIOS",
    "PORTRAIT_ASPECT_RATIOS",
    "apply_saved_dimensions",
    "apply_aspect_ratio",
    "bind_dimension_row_actions",
]
