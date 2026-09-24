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

"""Project current dimension state into presentation-neutral menu entries."""

from __future__ import annotations

from collections.abc import Callable

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetCatalogSource,
    DimensionPresetItem,
    DimensionPresetSection,
)
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuSection,
    MenuSeparator,
    MenuSubmenu,
)

from .dimension_commands import (
    apply_aspect_ratio,
    apply_saved_dimensions,
    current_positive_dimensions,
    swap_dimension_values,
)
from .dimension_contract import (
    LANDSCAPE_ASPECT_RATIOS,
    PORTRAIT_ASPECT_RATIOS,
    AspectRatioPreset,
    DimensionContextMenuContent,
    DimensionRowBinding,
    DimensionSide,
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
                callback=lambda: swap_dimension_values(binding),
            )
        )
    preset_catalog = (
        dimension_preset_source.current_dimension_preset_catalog()
        if dimension_preset_source is not None
        else None
    )
    if content is DimensionContextMenuContent.FULL:
        saved_entry = _saved_dimensions_entry(binding, preset_catalog)
        if saved_entry is not None:
            entries.append(saved_entry)
        anchor_sides = (
            (anchor_side,)
            if anchor_side is not None
            else (DimensionSide.WIDTH, DimensionSide.HEIGHT)
        )
        entries.extend(_aspect_ratio_entry(binding, side) for side in anchor_sides)
    save_entry = _save_current_dimensions_entry(
        binding,
        dimension_preset_source,
        preset_catalog,
    )
    if save_entry is not None:
        if entries:
            entries.append(MenuSeparator())
        entries.append(save_entry)
    return tuple(entries)


def _saved_dimensions_entry(
    binding: DimensionRowBinding,
    catalog: DimensionPresetCatalog | None,
) -> MenuSubmenu | None:
    """Return the saved dimensions submenu when saved presets exist."""

    if catalog is None or not catalog.sections:
        return None
    return MenuSubmenu(
        SET_DIMENSIONS_MENU_TEXT,
        entries=(
            _saved_dimension_orientation_entry(
                title=PORTRAIT_ASPECT_RATIO_MENU_TEXT,
                binding=binding,
                sections=catalog.sections,
                landscape=False,
            ),
            _saved_dimension_orientation_entry(
                title=LANDSCAPE_ASPECT_RATIO_MENU_TEXT,
                binding=binding,
                sections=catalog.sections,
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
                callback=_saved_dimension_callback(binding, width=width, height=height),
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
    source: DimensionPresetCatalogSource | None,
    catalog: DimensionPresetCatalog | None,
) -> MenuSubmenu | None:
    """Return save actions for the current dimension row values."""

    if source is None or catalog is None:
        return None
    current_dimensions = current_positive_dimensions(binding)
    if current_dimensions is None:
        return None
    width, height = current_dimensions
    if not catalog.can_save_globally and catalog.model_save_label is None:
        return None

    entries: list[MenuItem] = []
    if catalog.can_save_globally:
        entries.append(
            MenuItem(
                "dimension.save.global",
                SAVE_GLOBALLY_ACTION_TEXT,
                callback=lambda: source.save_current_dimensions_globally(width, height),
            )
        )
    if catalog.model_save_label is not None:
        entries.append(
            MenuItem(
                "dimension.save.model",
                app_text("Save for %1", catalog.model_save_label),
                callback=lambda: source.save_current_dimensions_for_model(
                    width, height
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


__all__ = ["dimension_menu_entries"]
