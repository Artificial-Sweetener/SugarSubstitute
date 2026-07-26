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

"""Coordinate prompt-editor UI interactions through application services."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import (
    QPointF,
    Qt,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTextCursor
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutation,
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSyntaxAction,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from ..commands.reorder_commands import PromptReorderCommandResult
from ..features import (
    PromptFeatureProfileController,
)
from ..models import PromptEditorInteractionMode
from ..syntax_renderers import PromptSyntaxStateController
from .autocomplete_controller import (
    PromptAutocompleteInputPort,
)
from .autocomplete_timing import (
    PromptAutocompleteTimingController,
)
from .keymap import PromptKeymapController
from .mouse_selection_controller import PromptMouseSelectionController
from .reorder_interaction import (
    PromptReorderInteractionEditor,
    PromptReorderInteractionHost,
    PromptReorderInteractionOwner,
)
from .reorder_overlay_port import PromptReorderOverlayFactory, PromptReorderOverlayPort
from .reorder_preview_publication import PromptReorderPreviewPublicationOwner
from .weight_interaction import PromptWeightInteraction


class _PromptEditorCursor(Protocol):
    """Describe cursor operations used by interaction-owned selection updates."""

    def setPosition(self, pos: int, mode: object | None = None) -> None:
        """Move or extend the cursor selection."""


class PromptInteractionEditor(Protocol):
    """Describe the narrow editor operations retained by interaction orchestration."""

    def textCursor(self) -> _PromptEditorCursor:
        """Return the editor's live cursor object."""

    def setTextCursor(self, cursor: _PromptEditorCursor) -> None:
        """Persist the supplied cursor selection back to the editor."""

    def toPlainText(self) -> str:
        """Return the editor's plain-text contents."""

    def has_pending_projection_update(self) -> bool:
        """Return whether projected presentation is waiting to catch up."""


class PromptSemanticRefreshPort(Protocol):
    """Describe semantic refresh scheduling used by interaction coordination."""

    def queue_source_changed(
        self,
        source_text: str,
        *,
        reason: str,
        prepared_document_view: PromptDocumentView | None = None,
        prepared_render_plan: PromptSyntaxRenderPlan | None = None,
    ) -> None:
        """Queue source text for stale-safe semantic refresh."""

    def flush(self, *, reason: str) -> None:
        """Synchronously apply pending semantic refresh work when needed."""

    def cancel_pending(self, *, reason: str) -> None:
        """Cancel pending or active semantic refresh work."""

    def rebase_same_text_source_identity(self) -> None:
        """Rebase semantic lineage after an unchanged source publication."""


class PromptInteractionController:
    """Own prompt-editor UI routing while delegating semantics to services."""

    def __init__(
        self,
        editor: PromptInteractionEditor,
        *,
        autocomplete: PromptAutocompleteInputPort,
        autocomplete_timing_controller: PromptAutocompleteTimingController,
        syntax_state: PromptSyntaxStateController,
        document_service: PromptDocumentService,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        feature_profile: PromptFeatureProfileController | None = None,
        semantic_refresh_controller: PromptSemanticRefreshPort,
        reorder_overlay_factory: PromptReorderOverlayFactory,
        weight_interaction: PromptWeightInteraction,
        reorder_preview_publication: PromptReorderPreviewPublicationOwner,
    ) -> None:
        """Store collaborators and initialize prompt interaction state."""

        self._editor = editor
        self._autocomplete = autocomplete
        self._syntax_state = syntax_state
        self._mutation_service = mutation_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._feature_profile = (
            feature_profile or PromptFeatureProfileController.from_legacy_syntax(None)
        )
        self._semantic_refresh = semantic_refresh_controller
        self._autocomplete_timing_controller = autocomplete_timing_controller
        self._weight_interaction = weight_interaction
        self._keymap = PromptKeymapController(self, weights=weight_interaction)
        self._mouse_selection = PromptMouseSelectionController(
            self,
            weights=weight_interaction,
        )
        self._reorder = PromptReorderInteractionOwner(
            cast(PromptReorderInteractionEditor, self._editor),
            host=cast(PromptReorderInteractionHost, self),
            document_service=document_service,
            mutation_service=self._mutation_service,
            syntax_service=self._syntax_service,
            syntax_profile=self._syntax_profile,
            preview_publication=reorder_preview_publication,
            overlay_factory=reorder_overlay_factory,
        )
        self.handle_cursor_position_changed()

    @property
    def segment_overlay(self) -> PromptReorderOverlayPort | None:
        """Return the live segment reorder overlay when it exists."""

        return self._reorder.segment_overlay

    @property
    def weight_interaction(self) -> PromptWeightInteraction:
        """Return the dedicated emphasis and exact-weight interaction owner."""

        return self._weight_interaction

    @property
    def interaction_mode(self) -> PromptEditorInteractionMode:
        """Return the active prompt-editor interaction mode."""

        return self._reorder.interaction_mode

    @property
    def document_view(self) -> PromptDocumentView:
        """Return the current application-owned prompt document view."""

        return self._syntax_state.document_view

    @property
    def syntax_render_plan(self) -> PromptSyntaxRenderPlan:
        """Return the current syntax render plan for characterization tests."""

        return self._syntax_state.render_plan

    @property
    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the current active syntax span for characterization tests."""

        return self._syntax_state.active_syntax_span

    def handle_text_changed(self) -> None:
        """Refresh cached prompt semantics after the editor text changes."""

        text = self._editor.toPlainText()
        self._handle_text_changed_measured_uninstrumented(text)

    def handle_document_semantics_changed(self) -> None:
        """Rebuild prompt state when source interpretation changes in place."""

        if (
            self._reorder.interaction_mode
            is PromptEditorInteractionMode.SEGMENT_REORDER
        ):
            self._reorder.cancel(
                PromptReorderCancelIntent(
                    reason="document_semantics_changed",
                    restore_selection=False,
                )
            )
        self._autocomplete_timing_controller.clear_for_non_text_interaction()
        self._weight_interaction.clear_transient_emphasis()
        self._syntax_state.clear_transient_state()
        self._semantic_refresh.queue_source_changed(
            self._editor.toPlainText(),
            reason="document_semantics_changed",
        )
        self._semantic_refresh.flush(reason="document_semantics_changed")

    def _handle_text_changed_measured_uninstrumented(self, text: str) -> None:
        """Queue prompt semantics after temporary timing starts."""

        self._autocomplete_timing_controller.cancel_pending_caret_refresh()
        if (
            self._reorder.interaction_mode
            is PromptEditorInteractionMode.SEGMENT_REORDER
            and self._syntax_state.pending_document_view is None
        ):
            self._reorder.cancel(
                PromptReorderCancelIntent(
                    reason="source_changed",
                    restore_selection=False,
                )
            )

        pending_document_view = self._syntax_state.pending_document_view
        if (
            pending_document_view is None
            and text == self._syntax_state.document_view.source_text
        ):
            self._semantic_refresh.rebase_same_text_source_identity()
            self.handle_cursor_position_changed()
            return
        if pending_document_view is None:
            self._weight_interaction.clear_transient_emphasis()
        self._semantic_refresh.queue_source_changed(
            text,
            reason="text_changed",
            prepared_document_view=pending_document_view,
        )

    def flush_pending_semantic_refresh(self, *, reason: str) -> None:
        """Synchronously apply any queued semantic prompt refresh."""

        self._semantic_refresh.flush(reason=reason)

    def _cancel_pending_semantic_refresh(self) -> None:
        """Drop queued semantic refresh work after an explicit state application."""

        self._syntax_state.clear_pending_document_view()
        self._semantic_refresh.cancel_pending(reason="state_applied")

    def has_lora_spans(self) -> bool:
        """Return whether the current document contains LoRA syntax spans."""

        return any(
            span.kind == "lora"
            for span in self._syntax_state.document_view.syntax_spans
        )

    def refresh_lora_render_metadata(self, *, reason: str) -> bool:
        """Refresh catalog-backed LoRA render metadata for the current document."""

        _ = reason
        if not self._syntax_profile.supports("lora"):
            return False
        if not self.has_lora_spans():
            return False
        self._syntax_state.replace_prompt_state(self._syntax_state.document_view)
        self.handle_cursor_position_changed()
        return True

    def handle_cursor_position_changed(self) -> None:
        """Refresh active syntax-aware state after caret movement."""

        self._syntax_state.refresh_active_span()

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle pre-edit key routing that should intercept normal text editing."""

        handled = self._keymap.handle_key_press(event)
        if handled and event.key() in {Qt.Key.Key_Escape, Qt.Key.Key_Tab}:
            self._autocomplete_timing_controller.clear_for_non_text_interaction()
        return handled

    def handle_emphasis_shortcut_accepted(self) -> None:
        """Mute autocomplete after a keyboard emphasis shortcut is accepted."""

        self._keymap.handle_emphasis_shortcut_accepted()

    def handle_post_key_press(self, event: QKeyEvent) -> None:
        """Handle post-edit prompt operations that depend on the updated text state."""

        self._keymap.handle_post_key_press(event)

    def handle_key_release(self, event: QKeyEvent) -> bool:
        """Commit modifier-owned interaction state when the owning key is released."""

        return self._keymap.handle_key_release(event)

    def enter_segment_reorder_mode_from_keymap(self) -> None:
        """Enter segment reorder mode for the keymap Alt path."""

        self._reorder.enter()

    def cancel_segment_reorder_mode_from_keymap(
        self,
        intent: PromptReorderCancelIntent,
    ) -> None:
        """Cancel segment reorder mode for the keymap Escape path."""

        self._reorder.cancel(intent)

    def commit_segment_reorder_mode_from_keymap(
        self,
        intent: PromptReorderCommitIntent,
    ) -> None:
        """Commit segment reorder mode for the keymap Alt-release path."""

        self._reorder.commit(intent)

    def move_keyboard_reorder_chip_from_keymap(
        self,
        intent: PromptReorderKeyboardMoveIntent,
    ) -> None:
        """Move one reorder chip through the existing reorder owner."""

        self._reorder.move_keyboard(intent)

    def handle_autocomplete_key_press_from_keymap(self, event: QKeyEvent) -> bool:
        """Delegate pre-edit autocomplete key handling to its Phase 11 owner."""

        return self._autocomplete.handle_key_press(event)

    def handle_autocomplete_post_key_press_from_keymap(
        self,
        event: QKeyEvent,
    ) -> None:
        """Delegate post-edit autocomplete refresh to its Phase 11 owner."""

        self._autocomplete_timing_controller.handle_post_key_press(event)

    def clear_autocomplete_for_emphasis_shortcut_from_keymap(self) -> None:
        """Clear autocomplete after keymap accepts an emphasis shortcut."""

        self._autocomplete_timing_controller.clear_for_non_text_interaction()

    def clear_autocomplete_for_non_text_key_from_keymap(self) -> None:
        """Clear autocomplete after a surface-owned non-text key is accepted."""

        self._autocomplete_timing_controller.clear_for_non_text_interaction()

    def flush_semantic_refresh_from_keymap(self, *, reason: str) -> None:
        """Flush pending semantic refresh for a keymap-owned reason."""

        self.flush_pending_semantic_refresh(reason=reason)

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Consume syntax-owned inline clicks before normal text editing."""

        return self._mouse_selection.handle_mouse_press(event)

    def syntax_action_at_mouse_position(
        self,
        position: QPointF,
    ) -> PromptSyntaxAction | None:
        """Return the prepared syntax action at one mouse position."""

        return self._syntax_state.syntax_action_at(position)

    def handle_mouse_release(self) -> None:
        """Refresh state after caret movement caused by mouse interaction."""

        self._mouse_selection.handle_mouse_release()

    def schedule_mouse_release_autocomplete_refresh(self) -> None:
        """Dismiss autocomplete after mouse-driven caret movement."""

        self._autocomplete_timing_controller.suppress_for_mouse_navigation()

    def refresh_mouse_release_cursor_state(self) -> None:
        """Refresh cursor-derived syntax state after mouse interaction."""

        self.handle_cursor_position_changed()

    def current_reorder_document_view(self) -> PromptDocumentView:
        """Return the current prompt document snapshot used for reorder entry."""

        return self._syntax_state.document_view

    def segment_reorder_enabled(self) -> bool:
        """Return whether segment reorder mode may be entered."""

        return self._feature_profile.segment_reorder_enabled

    def clear_transient_state_for_reorder(self) -> None:
        """Clear transient autocomplete, syntax, and emphasis state before reorder."""

        self._autocomplete_timing_controller.clear_for_non_text_interaction()
        self._syntax_state.clear_transient_state()
        self._weight_interaction.clear_transient_emphasis()

    def apply_reorder_result(
        self,
        result: PromptReorderCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one reorder command."""

        self._apply_reorder_command_result(result)

    def handle_focus_out(self) -> None:
        """Dismiss prompt-editor transient state after focus leaves interaction flow."""

        if (
            self._reorder.interaction_mode
            is PromptEditorInteractionMode.SEGMENT_REORDER
        ):
            return
        self._autocomplete_timing_controller.handle_focus_out()
        self._weight_interaction.clear_transient_emphasis()
        self._syntax_state.clear_transient_state()

    def handle_hide(self) -> None:
        """Clear prompt-editor transient state when the editor hides."""

        self._autocomplete_timing_controller.handle_hide()
        if self._reorder.segment_overlay is not None:
            self._reorder.cancel(
                PromptReorderCancelIntent(
                    reason="controller_hide",
                    restore_selection=False,
                )
            )
        self._weight_interaction.clear_transient_emphasis()
        self._syntax_state.clear_transient_state()

    def handle_resize(self) -> None:
        """Reposition prompt-editor overlays after the editor is resized."""

        if self._reorder.segment_overlay is not None:
            self._reorder.position()
        self._syntax_state.refresh_geometry()
        if self._editor.has_pending_projection_update():
            return
        self._autocomplete.refresh_geometry()

    def handle_move(self) -> None:
        """Reposition prompt-editor overlays after layouts move the editor."""

        self._syntax_state.refresh_geometry()
        if self._editor.has_pending_projection_update():
            return
        self._autocomplete.refresh_geometry()

    def handle_viewport_scroll(self) -> None:
        """Reposition prompt-editor overlays after the viewport scrolls."""

        if self._reorder.segment_overlay is not None:
            self._reorder.position()
        self._syntax_state.refresh_geometry()
        if self._editor.has_pending_projection_update():
            return
        self._autocomplete.refresh_geometry()

    def _apply_mutation(
        self,
        mutation: PromptMutation,
        *,
        block_signals: bool = False,
        render_plan: PromptSyntaxRenderPlan | None = None,
    ) -> None:
        """Adopt prompt state for a mutation that did not change source text."""

        _ = block_signals
        applied = self._syntax_state.apply_mutation(
            mutation,
            current_text=self._editor.toPlainText(),
            render_plan=render_plan,
        )
        if not applied:
            return

        self._cancel_pending_semantic_refresh()

        if mutation.selection_start is not None and mutation.selection_end is not None:
            cursor = self._editor.textCursor()
            self._set_cursor_selection(
                cursor,
                start=mutation.selection_start,
                end=mutation.selection_end,
            )
            self._editor.setTextCursor(cursor)

        self.handle_cursor_position_changed()

    def _apply_reorder_command_result(
        self,
        result: PromptReorderCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one source-applied reorder command."""

        mutation = result.mutation
        if mutation is None:
            return
        self._cancel_pending_semantic_refresh()
        self._syntax_state.apply_mutation(
            mutation,
            current_text=self._editor.toPlainText(),
            render_plan=result.render_plan,
        )
        self.handle_cursor_position_changed()

    @staticmethod
    def _set_cursor_selection(
        cursor: _PromptEditorCursor,
        *,
        start: int,
        end: int,
    ) -> None:
        """Select one half-open source range on the supplied cursor."""

        cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)


def _contains_position(
    *,
    start: int,
    end: int,
    position: int,
    inclusive_end: bool,
) -> bool:
    """Return whether one half-open source range contains the supplied position."""

    if inclusive_end:
        return start <= position <= end
    return start <= position < end


__all__ = [
    "PromptInteractionController",
    "PromptInteractionEditor",
    "PromptSemanticRefreshPort",
]
