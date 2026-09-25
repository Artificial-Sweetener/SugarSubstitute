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

"""Apply dimension transforms through supported field-widget value ports."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeGuard, cast

from PySide6.QtWidgets import QWidget

from .dimension_contract import AspectRatioPreset, DimensionRowBinding, DimensionSide


def apply_aspect_ratio(
    binding: DimensionRowBinding,
    *,
    anchor_side: DimensionSide,
    preset: AspectRatioPreset,
) -> None:
    """Apply a ratio while preserving the clicked dimension side."""

    if anchor_side is DimensionSide.WIDTH:
        anchor_value = read_field_widget_value(binding.width_widget)
        write_target = field_value_writer(binding.height_widget)
        if not is_numeric_value(anchor_value) or write_target is None:
            return
        target_value = round(
            float(anchor_value) * preset.height_units / preset.width_units
        )
        write_target(int(target_value))
        return

    anchor_value = read_field_widget_value(binding.height_widget)
    write_target = field_value_writer(binding.width_widget)
    if not is_numeric_value(anchor_value) or write_target is None:
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

    write_width = field_value_writer(binding.width_widget)
    write_height = field_value_writer(binding.height_widget)
    if write_width is None or write_height is None:
        return
    write_width(width)
    write_height(height)


def swap_dimension_values(binding: DimensionRowBinding) -> None:
    """Swap width and height widget values for one dimension row."""

    width_value = read_field_widget_value(binding.width_widget)
    height_value = read_field_widget_value(binding.height_widget)
    write_width = field_value_writer(binding.width_widget)
    write_height = field_value_writer(binding.height_widget)
    if (
        width_value is None
        or height_value is None
        or write_width is None
        or write_height is None
    ):
        return
    write_width(height_value)
    write_height(width_value)


def current_positive_dimensions(
    binding: DimensionRowBinding,
) -> tuple[int, int] | None:
    """Return current positive integer dimensions for save actions."""

    width_value = read_field_widget_value(binding.width_widget)
    height_value = read_field_widget_value(binding.height_widget)
    if not is_numeric_value(width_value) or not is_numeric_value(height_value):
        return None
    width = int(round(float(width_value)))
    height = int(round(float(height_value)))
    if width <= 0 or height <= 0:
        return None
    return width, height


def can_use_dimension_actions(binding: DimensionRowBinding) -> bool:
    """Return whether both dimension widgets expose supported value accessors."""

    return (
        field_value_reader(binding.width_widget) is not None
        and field_value_reader(binding.height_widget) is not None
        and field_value_writer(binding.width_widget) is not None
        and field_value_writer(binding.height_widget) is not None
    )


def context_widgets_for_value_widget(widget: QWidget) -> tuple[QWidget, ...]:
    """Return widgets that should open the dimension context menu for a value."""

    target = field_value_target(widget)
    if isinstance(target, QWidget) and target is not widget:
        return (widget, target)
    return (widget,)


def read_field_widget_value(widget: QWidget) -> object | None:
    """Return a supported field widget value, or ``None`` when unsupported."""

    reader = field_value_reader(widget)
    return reader() if reader is not None else None


def field_value_target(widget: QWidget) -> Any:
    """Return the inner value-owning widget for composite field controls."""

    return getattr(widget, "spinbox", widget)


def field_value_reader(widget: QWidget) -> Callable[[], object] | None:
    """Return a supported field widget getter without invoking it."""

    target = field_value_target(widget)
    for attribute in ("value", "text", "currentText"):
        reader = getattr(target, attribute, None)
        if callable(reader):
            return cast(Callable[[], object], reader)
    return None


def field_value_writer(widget: QWidget) -> Callable[[object], None] | None:
    """Return a supported field widget setter, or ``None`` when unsupported."""

    target = field_value_target(widget)
    for attribute in ("setValue", "setText", "setCurrentText"):
        writer = getattr(target, attribute, None)
        if callable(writer):
            return cast(Callable[[object], None], writer)
    return None


def is_numeric_value(value: object | None) -> TypeGuard[int | float]:
    """Return whether a widget value can anchor integer dimension math."""

    return isinstance(value, (int, float)) and not isinstance(value, bool)


__all__ = [
    "apply_aspect_ratio",
    "apply_saved_dimensions",
    "can_use_dimension_actions",
    "context_widgets_for_value_widget",
    "current_positive_dimensions",
    "swap_dimension_values",
]
