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

"""Adapt prepared prompt context-menu snapshots for existing menu presenters."""

from __future__ import annotations

from collections.abc import Callable, Hashable

from ..commands import PromptCommandSourceIdentity
from .context_menu_snapshot import (
    PromptContextMenuActionSnapshot,
    PromptContextMenuSnapshot,
    PromptContextMenuSnapshotController,
    PromptContextMenuSnapshotRequest,
)
from .danbooru_actions import (
    PromptDanbooruActionController,
)
from .diagnostics_controller import PromptDiagnosticsFeatureController
from .lora_metadata_controller import PromptLoraMetadataFeatureController
from .lora_trigger_word_controller import PromptLoraTriggerWordController
from .prompt_segment_preset_controller import PromptSegmentPresetController
from .scene_controller import PromptSceneFeatureController


class PromptContextMenuActionController:
    """Read prepared context-menu action snapshots through the snapshot owner."""

    def __init__(
        self,
        *,
        diagnostics: PromptDiagnosticsFeatureController,
        lora_metadata: PromptLoraMetadataFeatureController,
        lora_trigger_words: PromptLoraTriggerWordController,
        scene: PromptSceneFeatureController,
        segment_presets: PromptSegmentPresetController,
        danbooru: PromptDanbooruActionController,
        source_identity_provider: Callable[
            [],
            PromptCommandSourceIdentity | None,
        ],
        feature_profile_id_provider: Callable[[], Hashable | None],
    ) -> None:
        """Build the authoritative context-menu snapshot owner."""

        self._snapshot_controller = PromptContextMenuSnapshotController(
            diagnostics=diagnostics,
            lora_metadata=lora_metadata,
            lora_trigger_words=lora_trigger_words,
            scene=scene,
            segment_presets=segment_presets,
            danbooru=danbooru,
            source_identity_provider=source_identity_provider,
            feature_profile_id_provider=feature_profile_id_provider,
        )

    def prepared_action_snapshot_for_menu(
        self,
        *,
        source_position: int,
        selected_text: str,
        selection_range: tuple[int, int] | None = None,
        read_only: bool,
        rich_prompt_rendering_enabled: bool,
    ) -> PromptContextMenuActionSnapshot:
        """Return prepared prompt menu actions from the snapshot owner."""

        snapshot = self._snapshot_controller.snapshot_for_menu(
            PromptContextMenuSnapshotRequest(
                source_position=source_position,
                selected_text=selected_text,
                selection_range=selection_range,
                read_only=read_only,
                rich_prompt_rendering_enabled=rich_prompt_rendering_enabled,
            )
        )
        return snapshot.actions

    def prepare_menu_selection(
        self,
        *,
        selected_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> None:
        """Prepare selected-text menu state before snapshot reads."""

        self._snapshot_controller.prepare_menu_selection(
            selected_text=selected_text,
            selection_range=selection_range,
            read_only=read_only,
            reason=reason,
        )

    def prepare_menu_opening(self, *, source_position: int, reason: str) -> None:
        """Prepare source-position menu state before snapshot reads."""

        self._snapshot_controller.prepare_menu_opening(
            source_position=source_position,
            reason=reason,
        )

    def prepared_full_snapshot_for_menu(
        self,
        *,
        source_position: int,
        selected_text: str,
        selection_range: tuple[int, int] | None = None,
        read_only: bool,
        rich_prompt_rendering_enabled: bool,
    ) -> PromptContextMenuSnapshot:
        """Return the full identity-bearing snapshot for tests and later owners."""

        return self._snapshot_controller.snapshot_for_menu(
            PromptContextMenuSnapshotRequest(
                source_position=source_position,
                selected_text=selected_text,
                selection_range=selection_range,
                read_only=read_only,
                rich_prompt_rendering_enabled=rich_prompt_rendering_enabled,
            )
        )


__all__ = [
    "PromptContextMenuActionController",
    "PromptContextMenuActionSnapshot",
]
