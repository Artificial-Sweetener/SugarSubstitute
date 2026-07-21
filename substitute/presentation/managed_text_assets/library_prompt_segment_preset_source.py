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

"""Provide global saved prompt segments outside workflow editor panels."""

from __future__ import annotations

from substitute.application.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetService,
)
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
    PromptSegmentPresetSource,
    PromptSegmentPresetSourceSnapshot,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope

_GLOBAL_SCOPE = PresetSaveScope(
    title="Global",
    full_label="Global",
    association=GLOBAL_PRESET_ASSOCIATION,
)


class LibraryPromptSegmentPresetSource(PromptSegmentPresetSource):
    """Expose global prompt-segment presets to caller-neutral editors."""

    def __init__(self, user_preset_service: UserPresetService) -> None:
        """Store the application preset service."""

        self._user_preset_service = user_preset_service

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return global saved prompt segments and the global save scope."""

        listing = self._user_preset_service.list_prompt_string_presets(
            (GLOBAL_PRESET_ASSOCIATION,)
        )
        sections = tuple(
            PromptSegmentPresetMenuSection(
                title=section.title,
                presets=tuple(_menu_item(preset) for preset in section.presets),
            )
            for section in listing.sections
        )
        return PromptSegmentPresetSourceSnapshot(
            menu_model=PromptSegmentPresetMenuModel(
                sections=sections,
                save_scopes=(_GLOBAL_SCOPE,),
            ),
            catalog_identity=CatalogSnapshotIdentity(
                catalog_revision="global-prompt-segments"
            ),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: PresetSaveScope,
    ) -> None:
        """Persist one selected prompt segment under the global association."""

        if scope.association != GLOBAL_PRESET_ASSOCIATION:
            raise ValueError("Library prompt segments support only the Global scope.")
        self._user_preset_service.save_prompt_string_preset(
            label=label,
            text=text,
            association=GLOBAL_PRESET_ASSOCIATION,
        )


def _menu_item(preset: UserPreset) -> PromptSegmentPresetMenuItem:
    """Convert one prompt-string preset to a menu item."""

    payload = preset.payload
    if not isinstance(payload, PromptStringPresetPayload):
        raise TypeError("Prompt segment preset requires a prompt-string payload.")
    return PromptSegmentPresetMenuItem(
        label=preset.label,
        text=payload.text,
        tooltip=payload.text,
    )


__all__ = ["LibraryPromptSegmentPresetSource"]
