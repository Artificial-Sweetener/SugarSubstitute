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

"""Own construction of the prompt projection and its editing collaborators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.application.ports import (
    PromptTagLexiconSnapshot,
    PromptTagLexiconSnapshotProvider,
)
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.application.prompt_editor.editing.structured_text import (
    PromptStructuredTextMutationService,
)
from substitute.infrastructure.persistence.qt_prompt_parenthesis_education_state import (
    QtPromptParenthesisEducationState,
)

from ..async_work import (
    PromptLoraThumbnailPreloader,
    QtDanbooruUrlImportDispatcher,
)
from ..commands.autocomplete_commands import PromptAutocompleteCommandService
from ..commands.diagnostic_commands import PromptDiagnosticCommandService
from ..commands.execution import PromptEditExecution
from ..commands.reorder_commands import PromptReorderCommandService
from ..commands.source_service import PromptSourceCommandService
from ..commands.trigger_word_commands import PromptTriggerWordCommandService
from ..commands.weight_commands import PromptWeightCommandService
from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..features import PromptDanbooruPasteImportController
from ..interactions.clipboard_history_controller import PromptClipboardHistoryActions
from ..interactions.parenthesis_education_controller import (
    PromptParenthesisEducationController,
)
from ..interactions.region_inline_editor import PromptRegionInlineEditor
from ..interactions.region_pointer_controller import PromptRegionPointerController
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..projection.surface import PromptProjectionSurface
from ..projection.undo_payload import PromptProjectionUndoPayload
from ..qt_lifecycle import qt_object_is_alive
from .collaborator_bundle import PromptEditorConstructionInputs
from .context import PromptEditorCompositionContext
from .editing_runtime_factory import PromptProjectionEditingRuntimeBuilder
from .execution_factory import PromptEditorExecutionFactory


@dataclass(frozen=True, slots=True)
class PromptEditorProjectionCollaborators:
    """Carry projection-surface construction results."""

    lora_thumbnail_cache: PromptLoraThumbnailCache
    lora_thumbnail_preloader: PromptLoraThumbnailPreloader
    surface: PromptProjectionSurface
    edit_execution: PromptEditExecution[PromptProjectionUndoPayload]
    source_commands: PromptSourceCommandService[PromptProjectionUndoPayload]
    autocomplete_commands: PromptAutocompleteCommandService[PromptProjectionUndoPayload]
    diagnostic_commands: PromptDiagnosticCommandService[PromptProjectionUndoPayload]
    weight_commands: PromptWeightCommandService[PromptProjectionUndoPayload]
    reorder_commands: PromptReorderCommandService[PromptProjectionUndoPayload]
    trigger_word_commands: PromptTriggerWordCommandService[PromptProjectionUndoPayload]
    structured_text_mutations: PromptStructuredTextMutationService
    parenthesis_education_controller: PromptParenthesisEducationController
    danbooru_paste_import_controller: PromptDanbooruPasteImportController[Any]
    clipboard_history_controller: PromptClipboardHistoryActions
    shell_padding_fill_plane: QWidget
    fill_plane: QWidget


def _build_editing_session() -> PromptEditingSession[PromptProjectionUndoPayload]:
    """Create the source-backed editing session before projection wiring."""
    return PromptEditingSession[PromptProjectionUndoPayload](
        source_text="",
        source_revision=0,
        cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
        max_undo_states=100,
        max_redo_states=100,
    )


def _publish_region_hover(
    editor: QWidget,
    surface: PromptProjectionSurface,
    region_index: int | None,
) -> None:
    """Update local chrome and publish panel-level regional hover intent."""
    surface.set_region_hovered(region_index)
    signal = getattr(editor, "regionHovered", None)
    emit = getattr(signal, "emit", None)
    if callable(emit):
        emit(region_index)


class PromptEditorProjectionFactory:
    """Build the projection surface and its complete editing command boundary."""

    def __init__(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        execution: PromptEditorExecutionFactory,
    ) -> None:
        """Retain construction dependencies shared by projection collaborators."""
        self._inputs = inputs
        self._context = context
        self._execution = execution

    def build(
        self,
        *,
        paste_completed: Callable[[str], None],
    ) -> PromptEditorProjectionCollaborators:
        """Build the projection surface and passive fill-plane widgets."""
        inputs = self._inputs
        context = self._context
        lora_thumbnail_cache = PromptLoraThumbnailCache(
            inputs.thumbnail_asset_repository
        )
        lora_thumbnail_preloader = PromptLoraThumbnailPreloader(
            cache=lora_thumbnail_cache,
            asset_repository=inputs.thumbnail_asset_repository,
            parent=context.editor,
            executor=self._execution.build_task_executor(
                owner_label="prompt-thumbnail"
            ),
        )
        tag_snapshot = PromptTagLexiconSnapshot()
        if isinstance(
            inputs.prompt_autocomplete_gateway,
            PromptTagLexiconSnapshotProvider,
        ):
            tag_snapshot = (
                inputs.prompt_autocomplete_gateway.prepared_prompt_tag_snapshot()
            )
        source_normalizer = PromptSourceNormalizationService(tag_snapshot=tag_snapshot)
        structured_text_mutations = PromptStructuredTextMutationService(
            inputs.prompt_document_semantics
        )
        editing_session = _build_editing_session()
        editing_runtime_builder = PromptProjectionEditingRuntimeBuilder(
            session=editing_session,
            normalizer=source_normalizer,
            structured_text_mutations=structured_text_mutations,
            danbooru_dispatcher=QtDanbooruUrlImportDispatcher(
                context.editor,
                is_alive=qt_object_is_alive,
                executor=self._execution.build_task_executor(
                    owner_label="prompt-danbooru-import"
                ),
            ),
            paste_completed=paste_completed,
        )
        surface = PromptProjectionSurface(
            context.shell_viewport,
            editing_session=editing_session,
            editing_runtime_factory=editing_runtime_builder,
            document_semantics=inputs.prompt_document_semantics,
            lora_thumbnail_cache=lora_thumbnail_cache,
            lora_thumbnail_preloader=lora_thumbnail_preloader,
        )
        parenthesis_education_controller = PromptParenthesisEducationController(
            state=QtPromptParenthesisEducationState(),
            target=surface,
            parent=context.editor,
        )
        surface.implicitParenthesisAuthored.connect(
            parenthesis_education_controller.handle_authored_nested_parentheses
        )
        surface.set_defer_source_rebuilds_until_prompt_state(True)
        edit_execution = surface.edit_execution
        source_commands = surface.source_commands
        region_inline_editor = PromptRegionInlineEditor(
            viewport=surface.viewport(),
            target_provider=surface.region_edit_target,
            scroll_offset=surface.projection_scroll_offset,
            active_region_sink=surface.set_region_editing,
            draft_sink=surface.set_region_editing_draft,
        )
        region_pointer_controller = PromptRegionPointerController(
            document_view=surface.prompt_document_view,
            source_commands=source_commands,
            scroll_offset=surface.projection_scroll_offset,
            cursor_position=lambda: surface.cursor_position,
            inline_editor=region_inline_editor,
            hover_sink=lambda index: _publish_region_hover(
                context.editor,
                surface,
                index,
            ),
        )
        surface.pointer_interactions.set_region_double_click_handler(
            region_pointer_controller.handle_double_click
        )
        surface.pointer_interactions.set_region_hover_handler(
            region_pointer_controller.handle_hover
        )
        surface.pointer_interactions.set_region_keyboard_rename_handler(
            region_pointer_controller.handle_keyboard_rename
        )
        autocomplete_commands = PromptAutocompleteCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
            structured_text_mutations=structured_text_mutations,
        )
        diagnostic_commands = PromptDiagnosticCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        weight_commands = PromptWeightCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        reorder_commands = PromptReorderCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        trigger_word_commands = PromptTriggerWordCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
            structured_text_mutations=structured_text_mutations,
        )
        shell_padding_fill_plane = context.fill_plane_factory(
            context.fill_plane_host,
            surface,
            context.editor,
            shell_padding_only=True,
        )
        fill_plane = context.fill_plane_factory(
            context.fill_plane_host,
            surface,
            context.shell_viewport,
            shell_padding_only=False,
        )
        return PromptEditorProjectionCollaborators(
            lora_thumbnail_cache=lora_thumbnail_cache,
            lora_thumbnail_preloader=lora_thumbnail_preloader,
            surface=surface,
            edit_execution=edit_execution,
            source_commands=source_commands,
            autocomplete_commands=autocomplete_commands,
            diagnostic_commands=diagnostic_commands,
            weight_commands=weight_commands,
            reorder_commands=reorder_commands,
            trigger_word_commands=trigger_word_commands,
            structured_text_mutations=structured_text_mutations,
            parenthesis_education_controller=parenthesis_education_controller,
            danbooru_paste_import_controller=(
                editing_runtime_builder.danbooru_controller
            ),
            clipboard_history_controller=surface.history.clipboard_history_actions,
            shell_padding_fill_plane=shell_padding_fill_plane,
            fill_plane=fill_plane,
        )
