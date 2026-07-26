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

"""Compose explicit context-menu preparation callbacks."""

from __future__ import annotations

from ..features import (
    PromptContextMenuPreparationLifecycle,
    PromptDanbooruActionController,
    PromptLoraTriggerWordController,
    PromptScenePositionContextPreparation,
    PromptSegmentPresetController,
)


def build_context_menu_preparation(
    *,
    segment_presets: PromptSegmentPresetController,
    danbooru: PromptDanbooruActionController,
    scene: PromptScenePositionContextPreparation,
    lora_trigger_words: PromptLoraTriggerWordController,
) -> PromptContextMenuPreparationLifecycle:
    """Bind feature owners to the context-menu preparation lifecycle."""

    return PromptContextMenuPreparationLifecycle(
        prepare_segment_selection=(
            lambda selected_text, selection_range, read_only, reason: (
                segment_presets.prepare_menu_snapshot_for_selection(
                    selected_text=selected_text,
                    selection_range=selection_range,
                    read_only=read_only,
                    reason=reason,
                )
            )
        ),
        prepare_danbooru_selection=(
            lambda selection_text, selection_range, read_only, reason: (
                danbooru.prepare_menu_snapshot_for_selection(
                    selection_text=selection_text,
                    selection_range=selection_range,
                    read_only=read_only,
                    reason=reason,
                )
            )
        ),
        prepare_scene_position=(
            lambda source_position, reason: scene.prepare_position_context(
                source_position,
                reason=reason,
            )
        ),
        prewarm_trigger_words=lora_trigger_words.prewarm_prompt,
    )
