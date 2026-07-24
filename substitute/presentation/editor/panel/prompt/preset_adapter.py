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

"""Adapt panel model context and persisted presets to the prompt-editor port."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.model_metadata import (
    prompt_preset_listing_associations_for_catalog_item,
    prompt_preset_scope_options_for_catalog_item,
)
from substitute.application.user_presets import (
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetService,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshot,
    PanelActiveModelSnapshotController,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
    PromptSegmentPresetSource,
    PromptSegmentPresetSourceSnapshot,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope


@dataclass(frozen=True, slots=True)
class _PromptSegmentModelScopes:
    """Describe panel-derived prompt-segment listing and saving scopes."""

    listing_associations: tuple[UserPresetAssociation, ...]
    save_scopes: tuple[PresetSaveScope, ...]


class PanelPromptSegmentPresetAdapter(PromptSegmentPresetSource):
    """Provide prompt segment presets for one panel's prepared model context."""

    def __init__(
        self,
        *,
        user_preset_service: UserPresetService,
        active_model_snapshots: PanelActiveModelSnapshotController,
    ) -> None:
        """Store persistence and prepared panel-context collaborators."""

        self._user_preset_service = user_preset_service
        self._active_model_snapshots = active_model_snapshots

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return prompt segments for prepared exact, family, and Global scopes."""

        active_model_snapshot = self._active_model_snapshots.snapshot
        scopes = _prompt_segment_model_scopes(active_model_snapshot)
        scope_titles = {
            _association_key(scope.association): scope.title
            for scope in scopes.save_scopes
        }
        listing = self._user_preset_service.list_prompt_string_presets(
            scopes.listing_associations
        )
        sections = tuple(
            PromptSegmentPresetMenuSection(
                title=scope_titles.get(
                    _association_key(section.association),
                    section.title,
                ),
                presets=_menu_items_for_presets(section.presets),
            )
            for section in listing.sections
        )
        return PromptSegmentPresetSourceSnapshot(
            menu_model=PromptSegmentPresetMenuModel(
                sections=sections,
                save_scopes=scopes.save_scopes,
            ),
            catalog_identity=active_model_snapshot.identity,
            status=active_model_snapshot.status,
        )

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: PresetSaveScope,
    ) -> None:
        """Persist selected prompt text through the user preset service."""

        self._user_preset_service.save_prompt_string_preset(
            label=label,
            text=text,
            association=scope.association,
        )


def _prompt_segment_model_scopes(
    snapshot: PanelActiveModelSnapshot,
) -> _PromptSegmentModelScopes:
    """Derive prompt preset scopes from one prepared panel model snapshot."""

    options = prompt_preset_scope_options_for_catalog_item(
        snapshot.catalog_item,
        model_kind=snapshot.model_kind,
    )
    return _PromptSegmentModelScopes(
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


def _menu_items_for_presets(
    presets: tuple[UserPreset, ...],
) -> tuple[PromptSegmentPresetMenuItem, ...]:
    """Convert application prompt presets into presentation menu items."""

    return tuple(
        PromptSegmentPresetMenuItem(
            label=preset.label,
            text=_prompt_payload_for_preset(preset).text,
            tooltip=_prompt_payload_for_preset(preset).text,
        )
        for preset in presets
    )


def _prompt_payload_for_preset(preset: UserPreset) -> PromptStringPresetPayload:
    """Return prompt string payload for one prompt preset."""

    if not isinstance(preset.payload, PromptStringPresetPayload):
        raise TypeError("Prompt segment menu item requires a prompt string payload")
    return preset.payload


def _association_key(
    association: UserPresetAssociation,
) -> tuple[object, str | None, str]:
    """Return stable matching key for display-only association labels."""

    return (association.scope, association.provider, association.key)


__all__ = ["PanelPromptSegmentPresetAdapter"]
