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

"""Own prompt-editor context-menu and LoRA-popup composition."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)

from ..commands.context_insertion import PromptContextInsertionService
from ..commands.feature_commands import PromptFeatureSnapshotIdentity
from ..features import (
    PromptContextMenuPreparationLifecycle,
    PromptContextMenuSnapshotAssembler,
    PromptLoraMetadataPresentation,
    PromptLoraTriggerWordController,
    PromptScenePositionContextSnapshot,
    PromptSegmentPresetController,
)
from ..interactions import (
    PromptContextMenuRequestPresenter,
    PromptExternalUrlActionRunner,
    PromptInlineLoraContextMenuPresenter,
    PromptInlineLoraShellMenu,
    PromptLoraPickerPopupPresenter,
    PromptLoraPickerPopupView,
    PromptTriggerWordActionAdapter,
)
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..overlays import show_lora_picker_popup
from ..projection.undo_payload import PromptProjectionUndoPayload
from .context import PromptEditorCompositionContext

type _PromptSceneContextReader = Callable[[int], PromptScenePositionContextSnapshot]


class PromptEditorMenuFactory:
    """Build context menus and LoRA popups against one shell context."""

    def __init__(self, context: PromptEditorCompositionContext) -> None:
        """Retain the shell context shared by menu presentation owners."""
        self._context = context

    def build_prompt_menu_presenter(
        self,
        *,
        snapshot_reader: PromptContextMenuSnapshotAssembler,
        preparation: PromptContextMenuPreparationLifecycle,
        segment_presets: PromptSegmentPresetController,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        trigger_word_identity_validator: Callable[
            [PromptFeatureSnapshotIdentity], bool
        ],
        schedule_lora: Callable[[], None],
        open_danbooru_wiki_for_selection: Callable[[str], object],
        queue_scene: Callable[[str], None],
        is_read_only: Callable[[], bool],
        rich_prompt_rendering_enabled: Callable[[], bool],
        toggle_rich_prompt_rendering: Callable[[bool], None],
    ) -> PromptContextMenuRequestPresenter:
        """Build the prompt context-menu request presenter."""
        return PromptContextMenuRequestPresenter(
            snapshot_reader=snapshot_reader,
            preparation=preparation,
            segment_presets=segment_presets,
            trigger_word_action_adapter=PromptTriggerWordActionAdapter(
                action_parent=self._context.editor,
                text_insertion_executor=context_insertion,
                identity_validator=trigger_word_identity_validator,
            ),
            schedule_lora=schedule_lora,
            open_danbooru_wiki_for_selection=open_danbooru_wiki_for_selection,
            queue_scene=queue_scene,
            is_read_only=is_read_only,
            rich_prompt_rendering_enabled=rich_prompt_rendering_enabled,
            toggle_rich_prompt_rendering=toggle_rich_prompt_rendering,
        )

    def build_inline_lora_menu_presenter(
        self,
        *,
        lora_metadata: PromptLoraMetadataPresentation,
        lora_trigger_words: PromptLoraTriggerWordController,
        prepared_scene_context_at_position: _PromptSceneContextReader,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        shell_menu: PromptInlineLoraShellMenu,
        finish_pending_key_edit_block: Callable[[str], None],
        external_url_actions: PromptExternalUrlActionRunner,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    ) -> PromptInlineLoraContextMenuPresenter:
        """Build the inline LoRA context-menu presenter."""
        return PromptInlineLoraContextMenuPresenter(
            lora_metadata=lora_metadata,
            lora_trigger_words=lora_trigger_words,
            prepared_scene_context_at_position=prepared_scene_context_at_position,
            trigger_word_action_adapter=PromptTriggerWordActionAdapter(
                action_parent=self._context.editor,
                text_insertion_executor=context_insertion,
                identity_validator=lora_trigger_words.action_identity_is_current,
            ),
            shell_menu=shell_menu,
            finish_pending_key_edit_block=finish_pending_key_edit_block,
            external_url_actions=external_url_actions,
            metadata_action_handler=metadata_action_handler,
        )

    def build_lora_picker_popup_presenter(
        self,
        *,
        lora_metadata: PromptLoraMetadataPresentation,
        lora_thumbnail_cache: PromptLoraThumbnailCache,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        last_context_menu_global_pos: Callable[[], QPoint | None],
        cursor_global_position: Callable[[], QPoint],
        external_url_actions: PromptExternalUrlActionRunner,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    ) -> PromptLoraPickerPopupPresenter:
        """Build the LoRA picker popup presenter."""

        def create_lora_picker_popup(
            parent: QWidget,
            items: Iterable[PromptLoraCatalogItem],
            *,
            thumbnail_cache: PromptLoraThumbnailCache,
            global_position: QPoint,
        ) -> PromptLoraPickerPopupView:
            """Create the concrete overlay popup behind the presenter protocol."""
            return cast(
                PromptLoraPickerPopupView,
                show_lora_picker_popup(
                    parent,
                    items,
                    thumbnail_cache=thumbnail_cache,
                    global_position=global_position,
                    open_url=external_url_actions.open_civitai_model_page,
                    metadata_action_handler=metadata_action_handler,
                ),
            )

        return PromptLoraPickerPopupPresenter(
            parent=self._context.editor,
            data_source=lora_metadata,
            thumbnail_cache=lora_thumbnail_cache,
            text_insertion_executor=context_insertion,
            popup_factory=create_lora_picker_popup,
            last_context_menu_global_pos=last_context_menu_global_pos,
            cursor_global_position=cursor_global_position,
        )
