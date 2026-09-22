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

"""Compose the complete context-menu runtime for one prompt editor."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)

from ..commands.context_insertion import PromptContextInsertionService
from ..features import (
    PromptContextMenuSnapshotAssembler,
    PromptDanbooruActionController,
    PromptDiagnosticsFeatureController,
    PromptLoraMetadataPresentation,
    PromptLoraTriggerWordController,
    PromptSceneContextPublication,
    PromptScenePositionContextPreparation,
    PromptSegmentPresetController,
)
from ..interactions import (
    PromptClipboardHistoryActions,
    PromptContextMenuRequestPresenter,
    PromptExternalUrlActionRunner,
    PromptInlineLoraContextMenuPresenter,
    PromptLoraPickerPopupPresenter,
)
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..projection.undo_payload import PromptProjectionUndoPayload
from ..shell import PromptShellContextMenuController
from .context import PromptEditorCompositionContext
from .context_menu_preparation_factory import build_context_menu_preparation
from .menu_factory import PromptEditorMenuFactory


@dataclass(frozen=True, slots=True)
class PromptEditorMenuFeatureOwners:
    """Collect prepared feature owners consumed by menu presentation."""

    diagnostics: PromptDiagnosticsFeatureController
    lora_metadata: PromptLoraMetadataPresentation
    lora_trigger_words: PromptLoraTriggerWordController
    scene_publication: PromptSceneContextPublication
    scene_positions: PromptScenePositionContextPreparation
    segment_presets: PromptSegmentPresetController
    danbooru: PromptDanbooruActionController
    source_identity: Callable[[], PromptSourceIdentity | None]
    feature_profile_id: Callable[[], Hashable | None]


@dataclass(frozen=True, slots=True)
class PromptEditorMenuActionBindings:
    """Collect commands and services invoked by prepared menu actions."""

    context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload]
    lora_thumbnail_cache: PromptLoraThumbnailCache
    clipboard: PromptClipboardHistoryActions
    external_url_actions: PromptExternalUrlActionRunner
    open_danbooru_wiki_for_selection: Callable[[str], object]
    queue_scene: Callable[[str], None]
    is_read_only: Callable[[], bool]
    rich_prompt_rendering_enabled: Callable[[], bool]
    toggle_rich_prompt_rendering: Callable[[bool], None]
    metadata_action_handler: ModelMetadataContextActionHandler | None


@dataclass(frozen=True, slots=True)
class PromptEditorMenuHostBindings:
    """Describe shell geometry and interaction callbacks used by menus."""

    finish_pending_key_edit_block: Callable[[str], None]
    has_text_selection: Callable[[], bool]
    source_position_for_global_pos: Callable[[QPoint], int]
    current_source_position: Callable[[], int]
    prompt_menu_requires_custom_actions: Callable[[], bool]
    show_native_context_menu: Callable[[QContextMenuEvent], None]
    cursor_global_position: Callable[[], QPoint]


@dataclass(frozen=True, slots=True)
class PromptEditorMenuRuntime:
    """Own the mutually dependent presenters behind prompt menu behavior."""

    prompt_requests: PromptContextMenuRequestPresenter
    shell: PromptShellContextMenuController
    lora_picker: PromptLoraPickerPopupPresenter
    inline_lora: PromptInlineLoraContextMenuPresenter


class _PromptShellMenuReference:
    """Resolve the intentional picker-to-shell cycle after shell construction."""

    def __init__(self) -> None:
        """Create an unbound construction-only reference."""
        self._menu: PromptShellContextMenuController | None = None

    def bind(self, menu: PromptShellContextMenuController) -> None:
        """Bind the single shell menu produced by this runtime composition."""
        if self._menu is not None:
            raise RuntimeError("Prompt shell menu reference is already bound")
        self._menu = menu

    def last_context_menu_global_pos(self) -> QPoint | None:
        """Return popup placement from the bound shell menu."""
        if self._menu is None:
            raise RuntimeError("Prompt shell menu reference is not bound")
        return self._menu.last_context_menu_global_pos()


def build_prompt_editor_menu_runtime(
    context: PromptEditorCompositionContext,
    features: PromptEditorMenuFeatureOwners,
    actions: PromptEditorMenuActionBindings,
    host: PromptEditorMenuHostBindings,
) -> PromptEditorMenuRuntime:
    """Compose every menu presenter and bind their intentional runtime cycle."""

    menu_factory = PromptEditorMenuFactory(context)
    snapshot_assembler = PromptContextMenuSnapshotAssembler(
        diagnostics=features.diagnostics.presentation,
        lora_metadata=features.lora_metadata,
        lora_trigger_words=features.lora_trigger_words,
        scene_publication=features.scene_publication,
        scene_positions=features.scene_positions,
        segment_presets=features.segment_presets,
        danbooru=features.danbooru,
        source_identity_provider=features.source_identity,
        feature_profile_id_provider=features.feature_profile_id,
    )
    preparation = build_context_menu_preparation(
        segment_presets=features.segment_presets,
        danbooru=features.danbooru,
        scene=features.scene_positions,
        lora_trigger_words=features.lora_trigger_words,
    )
    shell_reference = _PromptShellMenuReference()
    lora_picker = menu_factory.build_lora_picker_popup_presenter(
        lora_metadata=features.lora_metadata,
        lora_thumbnail_cache=actions.lora_thumbnail_cache,
        context_insertion=actions.context_insertion,
        last_context_menu_global_pos=(shell_reference.last_context_menu_global_pos),
        cursor_global_position=host.cursor_global_position,
        external_url_actions=actions.external_url_actions,
        metadata_action_handler=actions.metadata_action_handler,
    )
    prompt_requests = menu_factory.build_prompt_menu_presenter(
        snapshot_reader=snapshot_assembler,
        preparation=preparation,
        segment_presets=features.segment_presets,
        context_insertion=actions.context_insertion,
        trigger_word_identity_validator=(
            features.lora_trigger_words.action_identity_is_current
        ),
        schedule_lora=lora_picker.open_lora_picker,
        open_danbooru_wiki_for_selection=(actions.open_danbooru_wiki_for_selection),
        queue_scene=actions.queue_scene,
        is_read_only=actions.is_read_only,
        rich_prompt_rendering_enabled=actions.rich_prompt_rendering_enabled,
        toggle_rich_prompt_rendering=actions.toggle_rich_prompt_rendering,
    )
    shell = PromptShellContextMenuController(
        host=context.editor,
        finish_pending_key_edit_block=host.finish_pending_key_edit_block,
        has_text_selection=host.has_text_selection,
        selected_prompt_range_and_text=(prompt_requests.selected_prompt_range_and_text),
        selected_prompt_text=prompt_requests.selected_prompt_text,
        restore_prompt_selection_snapshot=(
            prompt_requests.restore_prompt_selection_snapshot
        ),
        source_position_for_global_pos=host.source_position_for_global_pos,
        current_source_position=host.current_source_position,
        prompt_menu_requires_custom_actions=(host.prompt_menu_requires_custom_actions),
        show_native_context_menu=host.show_native_context_menu,
        clipboard_actions=actions.clipboard,
        prompt_menu_requests=prompt_requests,
    )
    shell_reference.bind(shell)
    inline_lora = menu_factory.build_inline_lora_menu_presenter(
        lora_metadata=features.lora_metadata,
        lora_trigger_words=features.lora_trigger_words,
        prepared_scene_context_at_position=(
            lambda source_position: features.scene_positions.prepare_position_context(
                source_position,
                reason="inline_lora_context_menu",
            )
        ),
        context_insertion=actions.context_insertion,
        shell_menu=shell,
        finish_pending_key_edit_block=host.finish_pending_key_edit_block,
        external_url_actions=actions.external_url_actions,
        metadata_action_handler=actions.metadata_action_handler,
    )
    return PromptEditorMenuRuntime(
        prompt_requests=prompt_requests,
        shell=shell,
        lora_picker=lora_picker,
        inline_lora=inline_lora,
    )


__all__ = [
    "PromptEditorMenuActionBindings",
    "PromptEditorMenuFeatureOwners",
    "PromptEditorMenuHostBindings",
    "PromptEditorMenuRuntime",
    "build_prompt_editor_menu_runtime",
]
