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

"""Prepare shared saved-dimension catalogs for editor presentation."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    translate_application_message,
)

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
from substitute.presentation.editor.panel.dimension_presets.models import (
    DimensionPresetCatalog,
    DimensionPresetCatalogSource,
    DimensionPresetItem,
    DimensionPresetSection,
)
from substitute.presentation.editor.panel.menus.preset_model_scope_policy import (
    dimension_preset_model_scopes,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.dimension_presets.catalog_source")


class EditorDimensionPresetCatalogSource(DimensionPresetCatalogSource):
    """Own prepared saved dimensions for one live editor panel."""

    def __init__(
        self,
        *,
        user_preset_service: UserPresetService,
        active_model_snapshots: PanelActiveModelSnapshotController,
    ) -> None:
        """Store services used to resolve global and model-family scopes."""

        self._user_preset_service = user_preset_service
        self._active_model_snapshots = active_model_snapshots
        self._catalog: DimensionPresetCatalog | None = None
        self._model_save_association: UserPresetAssociation | None = None

    def prepare_dimension_preset_catalog(self, *, reason: str) -> None:
        """Prepare saved dimensions for later menu or modal rendering."""

        try:
            catalog, save_association = self._prepare_catalog()
        except Exception as error:
            self._catalog = None
            self._model_save_association = None
            log_warning(
                _LOGGER,
                "Failed to prepare saved dimensions",
                reason=reason,
                error_type=type(error).__name__,
            )
            return
        self._catalog = catalog
        self._model_save_association = save_association

    def _prepare_catalog(
        self,
    ) -> tuple[DimensionPresetCatalog, UserPresetAssociation | None]:
        """Build saved dimensions for global and active model contexts."""

        scopes = dimension_preset_model_scopes(self._active_model_snapshots.snapshot)
        listing = self._user_preset_service.list_dimension_presets(
            scopes.listing_associations
        )
        sections = [
            DimensionPresetSection(
                title=translate_application_message(
                    "For %1", section.association.label
                ),
                presets=_items_for_presets(section.presets),
            )
            for section in listing.association_sections
        ]
        if listing.global_presets:
            sections.append(
                DimensionPresetSection(
                    title=app_text("Global"),
                    presets=_items_for_presets(listing.global_presets),
                )
            )
        return (
            DimensionPresetCatalog(
                sections=tuple(sections),
                model_save_label=scopes.save_label,
            ),
            scopes.save_association,
        )

    def current_dimension_preset_catalog(self) -> DimensionPresetCatalog | None:
        """Return the prepared catalog for any presentation renderer."""

        return self._catalog

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Persist dimensions globally and refresh prepared state."""

        self._user_preset_service.save_dimension_preset(
            width=width,
            height=height,
            association=GLOBAL_PRESET_ASSOCIATION,
        )
        self.prepare_dimension_preset_catalog(reason="dimension_preset_saved")

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Persist dimensions for the prepared active model family."""

        association = self._model_save_association
        if association is None:
            return
        self._user_preset_service.save_dimension_preset(
            width=width,
            height=height,
            association=association,
        )
        self.prepare_dimension_preset_catalog(reason="dimension_preset_saved")


def _items_for_presets(
    presets: tuple[UserPreset, ...],
) -> tuple[DimensionPresetItem, ...]:
    """Convert application presets into renderer-neutral items."""

    return tuple(
        DimensionPresetItem(
            label=preset.label,
            short_edge=_payload(preset).short_edge,
            long_edge=_payload(preset).long_edge,
        )
        for preset in presets
    )


def _payload(preset: UserPreset) -> DimensionPresetPayload:
    """Return a validated dimension payload."""

    if not isinstance(preset.payload, DimensionPresetPayload):
        raise TypeError("Dimension preset requires a dimension payload")
    return preset.payload


__all__ = ["EditorDimensionPresetCatalogSource"]
