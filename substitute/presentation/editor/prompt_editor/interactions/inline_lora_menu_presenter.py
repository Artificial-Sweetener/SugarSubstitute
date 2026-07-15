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

"""Present inline LoRA token context-menu actions from prepared feature state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction

from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
    ModelMetadataContextMenuActionBuilder,
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
    ModelMetadataMenuItem,
)

from ..features import (
    PromptLoraModelPageAction,
    PromptScenePositionContextSnapshot,
    PromptLoraTokenContext,
    PromptLoraTriggerWordsAction,
)
from ..projection.model import PromptProjectionToken
from .external_url_action_runner import PromptExternalUrlActionRunner
from .trigger_word_action_adapter import PromptTriggerWordActionAdapter


class PromptInlineLoraShellMenu(Protocol):
    """Describe the shell presentation hook for inline LoRA context menus."""

    def show_inline_lora_context_menu(
        self,
        *,
        global_pos: QPoint,
        trigger_action: QAction | None,
        metadata_menu_items: tuple[ModelMetadataMenuItem, ...],
    ) -> None:
        """Show prepared inline LoRA token context actions."""

    def set_context_insert_state(
        self,
        *,
        insert_position: int | None,
        should_replace_selection: bool | None = None,
    ) -> None:
        """Set the insertion target used by inline menu actions."""


class PromptInlineLoraMetadataActions(Protocol):
    """Describe catalog metadata actions consumed by the inline presenter."""

    def model_page_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
    ) -> PromptLoraModelPageAction | None:
        """Return a prepared model-page action for one inline LoRA token."""


class PromptInlineLoraTriggerWordActions(Protocol):
    """Describe trigger-word actions consumed by the inline presenter."""

    def inline_action(
        self,
        token_context: PromptLoraTokenContext,
        *,
        prompt_text: str,
    ) -> PromptLoraTriggerWordsAction | None:
        """Project a trigger action from cached inline token metadata."""


class PromptInlineLoraContextMenuPresenter:
    """Adapt projected LoRA token context into shell menu actions."""

    def __init__(
        self,
        *,
        lora_metadata: PromptInlineLoraMetadataActions,
        lora_trigger_words: PromptInlineLoraTriggerWordActions,
        prepared_scene_context_at_position: Callable[
            [int],
            PromptScenePositionContextSnapshot,
        ],
        trigger_word_action_adapter: PromptTriggerWordActionAdapter,
        shell_menu: PromptInlineLoraShellMenu,
        finish_pending_key_edit_block: Callable[[str], None],
        external_url_actions: PromptExternalUrlActionRunner,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    ) -> None:
        """Store inline LoRA action collaborators."""

        self._lora_metadata = lora_metadata
        self._lora_trigger_words = lora_trigger_words
        self._prepared_scene_context_at_position = prepared_scene_context_at_position
        self._trigger_word_action_adapter = trigger_word_action_adapter
        self._shell_menu = shell_menu
        self._finish_pending_key_edit_block = finish_pending_key_edit_block
        self._metadata_action_builder = ModelMetadataContextMenuActionBuilder(
            open_url=external_url_actions.open_civitai_model_page,
            action_handler=metadata_action_handler,
        )

    def show_lora_context_menu(self, token: object, global_pos: QPoint) -> None:
        """Show inline LoRA token actions for projected prompt decorations."""

        self._finish_pending_key_edit_block("lora_context_menu")
        if not isinstance(token, PromptProjectionToken):
            return
        token_context = self.token_context(token)
        metadata_menu_items = self.metadata_actions_for_token_context(token_context)
        trigger_action = self.inline_trigger_action_for_token_context(
            token_context,
            source_position=token.source_start,
        )
        self._shell_menu.set_context_insert_state(
            insert_position=token.source_end,
            should_replace_selection=False,
        )
        self._shell_menu.show_inline_lora_context_menu(
            global_pos=global_pos,
            trigger_action=trigger_action,
            metadata_menu_items=metadata_menu_items,
        )

    def token_context(self, token: PromptProjectionToken) -> PromptLoraTokenContext:
        """Return feature-owned value state for one projected LoRA token."""

        return PromptLoraTokenContext(
            prompt_name=token.detail_text,
            backend_value=token.lora_backend_value,
            display_name=token.display_text,
            trained_words=token.lora_trained_words,
            model_page_url=token.model_page_url,
        )

    def page_action_for_token_context(
        self,
        token_context: PromptLoraTokenContext,
    ) -> ModelMetadataMenuAction | None:
        """Return the shared CivitAI page action for prepared LoRA metadata."""

        prepared_action = self._lora_metadata.model_page_action_for_token(token_context)
        if prepared_action is None or prepared_action.command_request is None:
            return None
        return self._metadata_action_builder.civitai_page_action_for_target(
            ModelMetadataContextMenuTarget(
                title=token_context.display_name,
                backend_value=token_context.backend_value,
                model_kind="loras",
                model_page_url=prepared_action.command_request.payload.url,
                trained_words=token_context.trained_words,
            )
        )

    def metadata_actions_for_token_context(
        self,
        token_context: PromptLoraTokenContext,
    ) -> tuple[ModelMetadataMenuItem, ...]:
        """Return shared metadata actions for one inline LoRA token."""

        page_action = self.page_action_for_token_context(token_context)
        target = ModelMetadataContextMenuTarget(
            title=token_context.display_name,
            backend_value=token_context.backend_value,
            model_kind="loras",
            model_page_url=(
                None if page_action is None else token_context.model_page_url
            ),
            trained_words=token_context.trained_words,
        )
        return self._metadata_action_builder.menu_items_for_target(target)

    def inline_trigger_action_for_token_context(
        self,
        token_context: PromptLoraTokenContext,
        *,
        source_position: int,
    ) -> QAction | None:
        """Return an insert-trigger-words action for prepared LoRA metadata."""

        scene_context_snapshot = self._prepared_scene_context_at_position(
            source_position
        )
        if (
            scene_context_snapshot.context is None
            or not scene_context_snapshot.ready
            or scene_context_snapshot.stale
        ):
            return None
        prepared_action = self._lora_trigger_words.inline_action(
            token_context,
            prompt_text=scene_context_snapshot.context.effective_prompt_text,
        )
        return self._trigger_word_action_adapter.action_for_trigger_words(
            prepared_action
        )

    def trigger_words_action_label(self, display_name: str) -> str:
        """Return a width-bounded trigger-word action label for QAction rows."""

        return self._trigger_word_action_adapter.trigger_words_action_label(
            display_name
        )


__all__ = [
    "PromptInlineLoraContextMenuPresenter",
    "PromptInlineLoraMetadataActions",
    "PromptInlineLoraTriggerWordActions",
    "PromptInlineLoraShellMenu",
]
