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

"""Own immutable theme-derived visual styles for prompt reorder chrome."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QColor
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)

from .chip_painter import PromptChipPaintStyle

_MINIMUM_TEXT_CONTRAST_RATIO = 4.5


def relative_luminance_component(component: float) -> float:
    """Convert one sRGB channel into its linear luminance component."""

    normalized = component / 255.0
    if normalized <= 0.03928:
        return normalized / 12.92
    return float(((normalized + 0.055) / 1.055) ** 2.4)


def relative_luminance(color: QColor) -> float:
    """Return the WCAG relative luminance for the supplied color."""

    red = float(color.red())
    green = float(color.green())
    blue = float(color.blue())
    return (
        (0.2126 * relative_luminance_component(red))
        + (0.7152 * relative_luminance_component(green))
        + (0.0722 * relative_luminance_component(blue))
    )


def contrast_ratio(foreground: QColor, background: QColor) -> float:
    """Return the WCAG contrast ratio for one foreground/background pair."""

    lighter = max(relative_luminance(foreground), relative_luminance(background))
    darker = min(relative_luminance(foreground), relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def readable_surface_text_color(*, preferred: QColor, background: QColor) -> QColor:
    """Choose readable text color while honoring the preferred tone when safe."""

    if contrast_ratio(preferred, background) >= _MINIMUM_TEXT_CONTRAST_RATIO:
        return QColor(preferred)

    dark_fallback = QColor(32, 34, 36)
    light_fallback = QColor(248, 249, 250)
    if contrast_ratio(light_fallback, background) >= contrast_ratio(
        dark_fallback,
        background,
    ):
        return light_fallback
    return dark_fallback


@dataclass(frozen=True, slots=True)
class PromptReorderVisualStyle:
    """Own palette-derived reorder colors independently of source and commands."""

    rest_fill: QColor
    rest_border: QColor
    hover_fill: QColor
    hover_border: QColor
    active_fill: QColor
    active_border: QColor
    drag_fill: QColor
    drag_border: QColor
    marker_color: QColor
    _rest_style: PromptChipPaintStyle = field(init=False, repr=False, compare=False)
    _hover_style: PromptChipPaintStyle = field(
        init=False,
        repr=False,
        compare=False,
    )
    _active_style: PromptChipPaintStyle = field(
        init=False,
        repr=False,
        compare=False,
    )
    _drag_style: PromptChipPaintStyle = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Prepare the four immutable interaction styles once per theme state."""

        object.__setattr__(
            self,
            "_rest_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.rest_fill),
                border_color=QColor(self.rest_border),
            ),
        )
        object.__setattr__(
            self,
            "_hover_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.hover_fill),
                border_color=QColor(self.hover_border),
            ),
        )
        object.__setattr__(
            self,
            "_active_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.active_fill),
                border_color=QColor(self.active_border),
            ),
        )
        object.__setattr__(
            self,
            "_drag_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.drag_fill),
                border_color=QColor(self.drag_border),
            ),
        )

    @classmethod
    def from_current_theme(cls) -> PromptReorderVisualStyle:
        """Build reorder colors from the current qfluent theme accent."""

        accent = QColor(themeColor())
        rest_border = QColor(accent)
        rest_border.setAlpha(96 if isDarkTheme() else 82)
        rest_fill = QColor(accent)
        rest_fill.setAlpha(18 if isDarkTheme() else 14)
        hover_fill = QColor(accent)
        hover_fill.setAlpha(28 if isDarkTheme() else 22)
        hover_border = QColor(accent)
        hover_border.setAlpha(138 if isDarkTheme() else 120)
        active_fill = QColor(accent)
        active_fill.setAlpha(34 if isDarkTheme() else 28)
        active_border = QColor(accent)
        active_border.setAlpha(160 if isDarkTheme() else 140)
        drag_fill = QColor(accent)
        drag_fill.setAlpha(38 if isDarkTheme() else 30)
        drag_border = QColor(accent)
        drag_border.setAlpha(176 if isDarkTheme() else 148)
        marker_color = QColor(accent)
        marker_color.setAlpha(240 if isDarkTheme() else 214)
        return cls(
            rest_fill=rest_fill,
            rest_border=rest_border,
            hover_fill=hover_fill,
            hover_border=hover_border,
            active_fill=active_fill,
            active_border=active_border,
            drag_fill=drag_fill,
            drag_border=drag_border,
            marker_color=marker_color,
        )

    def colors_for_segment(
        self,
        segment_index: int,
        *,
        dragged_segment_index: int | None,
        hovered_segment_index: int | None,
        active_segment_index: int | None,
    ) -> tuple[QColor, QColor]:
        """Return prepared chrome colors for one segment visual state."""

        if segment_index == dragged_segment_index:
            return QColor(self.drag_fill), QColor(self.drag_border)
        if segment_index == hovered_segment_index:
            return QColor(self.hover_fill), QColor(self.hover_border)
        if segment_index == active_segment_index:
            return QColor(self.active_fill), QColor(self.active_border)
        return QColor(self.rest_fill), QColor(self.rest_border)

    def paint_style_for_segment(
        self,
        segment_index: int,
        *,
        dragged_segment_index: int | None,
        hovered_segment_index: int | None,
        active_segment_index: int | None,
    ) -> PromptChipPaintStyle:
        """Return the prepared chip paint style for one segment."""

        if segment_index == dragged_segment_index:
            return self._drag_style
        if segment_index == hovered_segment_index:
            return self._hover_style
        if segment_index == active_segment_index:
            return self._active_style
        return self._rest_style

    def outline_style(
        self,
        *,
        opacity: float,
        outline_width: float,
    ) -> PromptChipPaintStyle:
        """Return the prepared outline style for landing previews."""

        return PromptChipPaintStyle(
            fill_color=QColor(self.active_fill),
            border_color=QColor(self.active_border),
            outline_only=True,
            outline_width=outline_width,
            opacity=opacity,
        )


__all__ = [
    "PromptReorderVisualStyle",
    "contrast_ratio",
    "readable_surface_text_color",
    "relative_luminance",
    "relative_luminance_component",
]
