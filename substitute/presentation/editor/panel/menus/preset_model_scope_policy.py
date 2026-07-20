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

"""Derive consumer-specific preset scopes from resolved active-model state."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from dataclasses import dataclass

from substitute.application.model_metadata import (
    prompt_preset_listing_associations_for_catalog_item,
    prompt_preset_scope_options_for_catalog_item,
)
from substitute.application.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    UserPresetAssociation,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshot,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope


@dataclass(frozen=True, slots=True)
class PromptSegmentModelScopes:
    """Describe prompt-segment listing and saving scopes."""

    listing_associations: tuple[UserPresetAssociation, ...]
    save_scopes: tuple[PresetSaveScope, ...]


@dataclass(frozen=True, slots=True)
class DimensionPresetModelScopes:
    """Describe dimension-preset model-family policy."""

    listing_associations: tuple[UserPresetAssociation, ...]
    save_association: UserPresetAssociation | None
    save_label: str | None


@dataclass(frozen=True, slots=True)
class NodeInputPresetModelScopes:
    """Describe node-input preset listing and saving scopes."""

    listing_associations: tuple[UserPresetAssociation, ...]
    save_scopes: tuple[PresetSaveScope, ...]


def prompt_segment_model_scopes(
    snapshot: PanelActiveModelSnapshot,
) -> PromptSegmentModelScopes:
    """Return prompt-segment policy for one resolved model snapshot."""

    options = prompt_preset_scope_options_for_catalog_item(
        snapshot.catalog_item,
        model_kind=snapshot.model_kind,
    )
    return PromptSegmentModelScopes(
        listing_associations=prompt_preset_listing_associations_for_catalog_item(
            snapshot.catalog_item
        ),
        save_scopes=tuple(
            PresetSaveScope(
                title=option.title,
                full_label=option.full_label,
                association=option.association,
            )
            for option in options
        ),
    )


def dimension_preset_model_scopes(
    snapshot: PanelActiveModelSnapshot,
) -> DimensionPresetModelScopes:
    """Return dimension-preset family policy for one resolved model snapshot."""

    association = (
        snapshot.family_associations[0] if snapshot.family_associations else None
    )
    return DimensionPresetModelScopes(
        listing_associations=snapshot.family_associations,
        save_association=association,
        save_label=association.label if association is not None else None,
    )


def node_input_preset_model_scopes(
    snapshot: PanelActiveModelSnapshot,
) -> NodeInputPresetModelScopes:
    """Return node-input preset family and Global policy."""

    return NodeInputPresetModelScopes(
        listing_associations=(
            *snapshot.family_associations,
            GLOBAL_PRESET_ASSOCIATION,
        ),
        save_scopes=(
            PresetSaveScope(
                title=app_text("Global"),
                full_label=app_text("Global"),
                association=GLOBAL_PRESET_ASSOCIATION,
            ),
            *tuple(
                PresetSaveScope(
                    title=association.label,
                    full_label=app_text("Base model: %1", association.label),
                    association=association,
                )
                for association in snapshot.family_associations
            ),
        ),
    )


__all__ = [
    "DimensionPresetModelScopes",
    "NodeInputPresetModelScopes",
    "PromptSegmentModelScopes",
    "dimension_preset_model_scopes",
    "node_input_preset_model_scopes",
    "prompt_segment_model_scopes",
]
