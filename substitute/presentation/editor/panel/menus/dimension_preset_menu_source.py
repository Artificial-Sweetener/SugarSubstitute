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

"""Prepare saved dimension preset snapshots for panel context menus."""

from __future__ import annotations

from substitute.application.user_presets import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    UserPreset,
    UserPresetAssociation,
    UserPresetService,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuItem,
    DimensionPresetMenuModel,
    DimensionPresetMenuSection,
    DimensionPresetMenuSource,
)
from substitute.presentation.editor.panel.menus.preset_model_scope_policy import (
    dimension_preset_model_scopes,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.menus.dimension_preset_menu_source")


class EditorDimensionPresetMenuSource(DimensionPresetMenuSource):
    """Own prepared saved dimension menu data for one live editor panel."""

    def __init__(
        self,
        *,
        user_preset_service: UserPresetService,
        active_model_snapshots: PanelActiveModelSnapshotController,
    ) -> None:
        """Store collaborators needed to prepare active checkpoint family state."""

        self._user_preset_service = user_preset_service
        self._active_model_snapshots = active_model_snapshots
        self._menu_model: DimensionPresetMenuModel | None = None
        self._model_save_association: UserPresetAssociation | None = None

    def prepare_dimension_preset_menu_model(self, *, reason: str) -> None:
        """Prepare saved dimensions for later context-menu rendering."""

        try:
            menu_model, save_association = self._prepared_dimension_preset_model()
        except Exception as error:
            self._menu_model = None
            self._model_save_association = None
            log_warning(
                _LOGGER,
                "Failed to prepare saved dimensions for context menu",
                reason=reason,
                error_type=type(error).__name__,
            )
            return
        self._menu_model = menu_model
        self._model_save_association = save_association

    def _prepared_dimension_preset_model(
        self,
    ) -> tuple[DimensionPresetMenuModel, UserPresetAssociation | None]:
        """Build saved dimensions for global and active model-family contexts."""

        scopes = dimension_preset_model_scopes(self._active_model_snapshots.snapshot)
        listing = self._user_preset_service.list_dimension_presets(
            scopes.listing_associations
        )
        sections = [
            DimensionPresetMenuSection(
                title=f"For {section.association.label}",
                presets=_menu_items_for_presets(section.presets),
            )
            for section in listing.association_sections
        ]
        if listing.global_presets:
            sections.append(
                DimensionPresetMenuSection(
                    title="Global",
                    presets=_menu_items_for_presets(listing.global_presets),
                )
            )
        return (
            DimensionPresetMenuModel(
                sections=tuple(sections),
                model_save_label=scopes.save_label,
                can_save_globally=True,
            ),
            scopes.save_association,
        )

    def current_dimension_preset_menu_model(
        self,
    ) -> DimensionPresetMenuModel | None:
        """Return the prepared saved-dimension model for menu rendering."""

        return self._menu_model

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Persist the current dimensions globally and refresh prepared state."""

        self._user_preset_service.save_dimension_preset(
            width=width,
            height=height,
            association=GLOBAL_PRESET_ASSOCIATION,
        )
        self.prepare_dimension_preset_menu_model(reason="dimension_preset_saved")

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Persist current dimensions for the prepared active model family."""

        association = self._model_save_association
        if association is None:
            return
        self._user_preset_service.save_dimension_preset(
            width=width,
            height=height,
            association=association,
        )
        self.prepare_dimension_preset_menu_model(reason="dimension_preset_saved")


def _menu_items_for_presets(
    presets: tuple[UserPreset, ...],
) -> tuple[DimensionPresetMenuItem, ...]:
    """Convert application presets into presentation menu items."""

    return tuple(
        DimensionPresetMenuItem(
            label=preset.label,
            short_edge=_dimension_payload_for_preset(preset).short_edge,
            long_edge=_dimension_payload_for_preset(preset).long_edge,
        )
        for preset in presets
    )


def _dimension_payload_for_preset(preset: UserPreset) -> DimensionPresetPayload:
    """Return the dimension payload for a dimension preset."""

    if not isinstance(preset.payload, DimensionPresetPayload):
        raise TypeError("Dimension preset menu item requires a dimension payload")
    return preset.payload


__all__ = ["EditorDimensionPresetMenuSource"]
