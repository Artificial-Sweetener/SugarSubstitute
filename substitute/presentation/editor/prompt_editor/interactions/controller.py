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

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTextCursor
from PySide6.QtWidgets import QScrollBar

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptMutation,
    PromptMutationService,
    PromptSyntaxAction,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
    PromptSyntaxSpanView,
)

from ..features import (
    PromptAutocompleteQueryController,
    PromptFeatureProfileController,
)
from ..syntax_renderers import PromptSyntaxStateController
from .autocomplete_controller import (
    PromptAutocompleteController,
    PromptAutocompleteQueryRefreshController,
)
from .autocomplete_timing import (
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)
from .emphasis_controller import (
    PromptEmphasisController,
    PromptEmphasisHost,
    PromptEmphasisSyntaxAction,
)
from .exact_weight_controller import (
    PromptExactWeightController,
    PromptExactWeightHost,
    PromptExactWeightProjectionHost,
)
from .keymap import PromptKeymapController
from .mouse_selection_controller import PromptMouseSelectionController
from .reorder_controller import (
    PromptReorderController,
    PromptReorderEditorHost,
    PromptReorderHost,
    PromptReorderOverlayFactory,
    PromptReorderOverlayPort,
)
from ..commands import (
    PromptCommandSourceIdentity,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    PromptSyntaxWeightAction,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    PromptWeightCursorPolicy,
)
from ..models import (
    PromptEditorInteractionMode,
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from ..overlays.token_weight_gestures import (
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)
from ..projection.model import PromptProjectionToken, PromptWeightControlIdentity
from ..projection.reorder_preview import PromptReorderPreviewState
from ..projection.reorder_preview_projection import (
    PromptReorderPreviewProjectionProvider,
)
from ..projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)


class _SelectionLike(Protocol):
    """Describe the minimal selection wrapper used by cursor helpers."""

    def isEmpty(self) -> bool:
        """Return whether the current selection is empty."""


class _PromptEditorCursor(Protocol):
    """Describe the cursor API consumed by prompt interaction logic."""

    def position(self) -> int:
        """Return the current cursor position."""

    def selection(self) -> _SelectionLike:
        """Return a Qt-like selection wrapper."""

    def selectionStart(self) -> int:
        """Return the inclusive selection start."""

    def selectionEnd(self) -> int:
        """Return the exclusive selection end."""

    def selectedText(self) -> str:
        """Return the selected document text."""

    def setPosition(self, pos: int, mode: object | None = None) -> None:
        """Move or extend the cursor selection."""

    def beginEditBlock(self) -> None:
        """Start a grouped edit operation."""

    def endEditBlock(self) -> None:
        """Finish a grouped edit operation."""

    def hasSelection(self) -> bool:
        """Return whether the cursor currently has a selection."""

    def select(self, mode: object) -> None:
        """Select text using one QTextCursor selection mode."""


class _PromptEditingSurface(Protocol):
    """Describe the editor behavior required by prompt interaction logic."""

    def textCursor(self) -> _PromptEditorCursor:
        """Return the editor's live cursor object."""

    def setTextCursor(self, cursor: _PromptEditorCursor) -> None:
        """Persist the supplied cursor selection back to the editor."""

    def toPlainText(self) -> str:
        """Return the editor's plain-text contents."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity used by prepared commands."""

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute one prepared prompt weight action through commands."""

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]:
        """Execute one prepared prompt reorder action through commands."""

    def setFocus(self) -> None:
        """Restore input focus to the editor after one inline click."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the editor-visible vertical scrollbar."""

    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Show transient visual feedback for one adjusted emphasis shell."""

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Store one active emphasis-adjustment session on the editor surface."""

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear any active emphasis-adjustment session from the editor surface."""

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when one exists."""

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range when present."""

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active emphasis-adjustment session owns one range."""

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Project a temporary neutral emphasis shell over one plain content range."""

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear any temporary neutral emphasis shell from the editor surface."""

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Clear transient neutral emphasis only when overlay interaction owns it."""

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the content range currently owned by a temporary neutral shell."""

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the current temporary neutral shell."""

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at one projected emphasis-content boundary when possible."""

    def set_reorder_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
    ) -> None:
        """Replace the explicit reorder preview state painted by the editor surface."""

    def clear_reorder_preview_state(self) -> None:
        """Clear any active reorder preview state from the editor surface."""

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the syntax span currently owned by the editor caret model."""

    def has_pending_projection_update(self) -> bool:
        """Return whether projected presentation is waiting to catch up."""

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Synchronously apply pending projected presentation work."""


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


class PromptInteractionController:
    """Own prompt-editor UI routing while delegating semantics to services."""

    _REORDER_PREVIEW_SYNC_INTERVAL_MS = 16

    def __init__(
        self,
        editor: _PromptEditingSurface,
        *,
        autocomplete: PromptAutocompleteController,
        autocomplete_minimum_prefix_length: int = 2,
        autocomplete_timing_controller: PromptAutocompleteTimingController
        | None = None,
        syntax_state: PromptSyntaxStateController,
        document_service: PromptDocumentService,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        feature_profile: PromptFeatureProfileController | None = None,
        semantic_refresh_controller: PromptSemanticRefreshPort,
        reorder_overlay_factory: PromptReorderOverlayFactory,
        exact_weight_projection: PromptExactWeightProjectionHost | None = None,
        reorder_preview_projection_provider: (
            PromptReorderPreviewProjectionProvider | None
        ) = None,
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
        autocomplete_timing = autocomplete_timing_controller
        if autocomplete_timing is None:
            autocomplete_query_refresh = PromptAutocompleteQueryRefreshController(
                autocomplete=self._autocomplete,
                query_controller=PromptAutocompleteQueryController(
                    document_service=document_service,
                    feature_profile=self._feature_profile,
                    minimum_prefix_length=autocomplete_minimum_prefix_length,
                ),
            )
            autocomplete_source_snapshots = PromptAutocompleteSourceSnapshotController(
                self._editor,
                document_view_provider=lambda: self._syntax_state.document_view,
                feature_profile=self._feature_profile,
            )
            autocomplete_timing = PromptAutocompleteTimingController(
                source_snapshots=autocomplete_source_snapshots,
                lifecycle_requester=autocomplete_query_refresh,
                lora_autocomplete_enabled=(
                    lambda: self._feature_profile.lora_autocomplete_enabled
                ),
            )
        self._autocomplete_timing_controller = autocomplete_timing
        self._keymap = PromptKeymapController(self)
        self._mouse_selection = PromptMouseSelectionController(self)
        self._emphasis = PromptEmphasisController(
            cast(PromptEmphasisHost, self),
            document_service=document_service,
        )
        self._exact_weight = PromptExactWeightController(
            cast(PromptExactWeightHost, self),
            projection_host=exact_weight_projection,
        )
        preview_projection_provider = reorder_preview_projection_provider
        if preview_projection_provider is None:
            preview_projection_provider = PromptReorderPreviewProjectionProvider(
                document_service=document_service,
                syntax_service=self._syntax_service,
                syntax_profile=self._syntax_profile,
            )
        self._reorder = PromptReorderController(
            cast(PromptReorderEditorHost, self._editor),
            host=cast(PromptReorderHost, self),
            document_service=document_service,
            mutation_service=self._mutation_service,
            syntax_service=self._syntax_service,
            syntax_profile=self._syntax_profile,
            preview_projection_provider=preview_projection_provider,
            overlay_factory=reorder_overlay_factory,
        )
        self.handle_cursor_position_changed()

    @property
    def segment_overlay(self) -> PromptReorderOverlayPort | None:
        """Return the live segment reorder overlay when it exists."""

        return self._reorder.segment_overlay

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

    @property
    def emphasis_feature_enabled(self) -> bool:
        """Return whether emphasis shortcuts should mutate the prompt."""

        return self._feature_profile.emphasis_enabled

    def clear_autocomplete_for_emphasis(self) -> None:
        """Clear autocomplete state before a non-text emphasis interaction."""

        self._autocomplete_timing_controller.clear_for_non_text_interaction()

    def textCursor(self) -> _PromptEditorCursor:
        """Return the editor cursor for emphasis interaction hosts."""

        return self._editor.textCursor()

    def setTextCursor(self, cursor: _PromptEditorCursor) -> None:
        """Persist an emphasis selection cursor back to the editor."""

        self._editor.setTextCursor(cursor)

    def setFocus(self) -> None:
        """Restore editor focus after an inline emphasis action."""

        self._editor.setFocus()

    def active_syntax_span_for_emphasis(self) -> PromptSyntaxSpanView | None:
        """Return the active syntax span visible to keyboard emphasis."""

        return self._syntax_state.active_syntax_span

    def document_view_for_emphasis(self) -> PromptDocumentView:
        """Return the current prompt document snapshot for emphasis queries."""

        return self._syntax_state.document_view

    def execute_emphasis_weight_action(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> PromptWeightCommandResult[object]:
        """Execute one emphasis action through the shared weight command path."""

        return self._editor.execute_weight_action(
            PromptWeightActionRequest(
                action=action,
                source_identity=self._editor.prompt_command_source_identity(),
                cursor_policy=cursor_policy,
            ),
            mutation_service=self._mutation_service,
            syntax_service=self._syntax_service,
            syntax_profile=self._syntax_profile,
        )

    def apply_emphasis_weight_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one emphasis weight command."""

        self._apply_weight_command_result(result)

    def refresh_emphasis_cursor_state(self) -> None:
        """Refresh cursor-derived syntax state after emphasis moves the caret."""

        self.handle_cursor_position_changed()

    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Show transient visual feedback for one adjusted emphasis shell."""

        self._editor.pulse_emphasis_feedback(
            outer_start=outer_start,
            outer_end=outer_end,
        )

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Store one active emphasis-adjustment session on the editor surface."""

        self._editor.set_emphasis_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear any active emphasis-adjustment session from the editor surface."""

        self._editor.clear_emphasis_adjustment_session()

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when one exists."""

        return self._editor.emphasis_adjustment_session()

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Project a temporary neutral emphasis shell over one plain content range."""

        self._editor.show_transient_neutral_emphasis(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear any temporary neutral emphasis shell from the editor surface."""

        self._editor.clear_transient_neutral_emphasis()

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the current temporary neutral shell."""

        return self._editor.transient_neutral_emphasis_owner()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the content range of the current temporary neutral shell."""

        return self._editor.transient_neutral_emphasis_range()

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at one projected emphasis-content boundary when possible."""

        return self._editor.set_emphasis_caret_to_content_boundary(
            content_start=content_start,
            content_end=content_end,
            prefer_end=prefer_end,
        )

    def clear_keyboard_emphasis_session_for_exact_weight(self) -> None:
        """Clear keyboard-owned emphasis state before overlay weight edits."""

        self._emphasis.clear_keyboard_emphasis_session()

    def clear_autocomplete_for_exact_weight(self) -> None:
        """Clear autocomplete state before a non-text weight interaction."""

        self._autocomplete_timing_controller.clear_for_non_text_interaction()

    def set_focus_after_exact_weight_action(self) -> None:
        """Restore editor focus after an overlay or syntax weight action."""

        self._editor.setFocus()

    def apply_emphasis_weight_action_from_exact(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        owner: PromptEmphasisAdjustmentOwner | None,
        clear_autocomplete: bool,
        restore_focus: bool,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> None:
        """Apply one emphasis action through the Phase 12.6 emphasis owner."""

        self._emphasis.apply_emphasis_syntax_action(
            action,
            owner=owner,
            clear_autocomplete=clear_autocomplete,
            restore_focus=restore_focus,
            cursor_policy=cursor_policy,
        )

    def execute_exact_weight_action(
        self,
        action: PromptSyntaxWeightAction,
        *,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> PromptWeightCommandResult[object]:
        """Execute one non-emphasis weight action through the command boundary."""

        return self._editor.execute_weight_action(
            PromptWeightActionRequest(
                action=action,
                source_identity=self._editor.prompt_command_source_identity(),
                cursor_policy=cursor_policy,
            ),
            mutation_service=self._mutation_service,
            syntax_service=self._syntax_service,
            syntax_profile=self._syntax_profile,
        )

    def apply_exact_weight_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one exact-weight command."""

        self._apply_weight_command_result(result)

    def clear_overlay_emphasis_session_for_exact_weight(self) -> None:
        """Clear overlay-owned emphasis state after overlay visibility changes."""

        self._emphasis.clear_emphasis_adjustment_session(
            owner=PromptEmphasisAdjustmentOwner.OVERLAY,
            clear_transient_neutral=True,
        )

    def preserve_surface_scroll_position_for_exact_weight(
        self,
        action: Callable[[], None],
    ) -> None:
        """Run one token-weight commit without scrolling toward the text caret."""

        scroll_bar = self._editor.verticalScrollBar()
        scroll_value = scroll_bar.value()
        action()
        scroll_bar.setValue(
            max(scroll_bar.minimum(), min(scroll_bar.maximum(), scroll_value))
        )

    def apply_token_weight_step_intent(
        self,
        intent: PromptTokenWeightStepIntent,
    ) -> None:
        """Apply one overlay arrow-step intent through the exact-weight owner."""

        self._exact_weight.apply_token_weight_step_intent(intent)

    def apply_token_weight_wheel_step_intent(
        self,
        intent: PromptTokenWeightWheelStepIntent,
    ) -> None:
        """Apply one wheel-step intent through the exact-weight owner."""

        self._exact_weight.apply_token_weight_wheel_step_intent(intent)

    def begin_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact edit mode through the exact-weight interaction owner."""

        self._exact_weight.begin_exact_weight_edit(token)

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact edit mode through the exact-weight interaction owner."""

        self._exact_weight.start_exact_weight_edit(token)

    def cancel_exact_weight_edit(self) -> None:
        """Cancel exact edit mode through the exact-weight interaction owner."""

        self._exact_weight.cancel_exact_weight_edit()

    def finalize_exact_weight_edit(self) -> None:
        """Commit or cancel exact edit through the exact-weight interaction owner."""

        self._exact_weight.finalize_exact_weight_edit()

    def update_exact_weight_caret(
        self,
        *,
        token: PromptProjectionToken,
        caret_index: int,
    ) -> None:
        """Move the projection-owned exact-weight caret."""

        self._exact_weight.update_exact_weight_caret(
            token=token,
            caret_index=caret_index,
        )

    def handle_exact_weight_key_press(self, event: QKeyEvent) -> bool:
        """Handle one exact-weight edit key press through the interaction owner."""

        return self._exact_weight.handle_exact_weight_key_press(event)

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update exact edit buffer state through the interaction owner."""

        self._exact_weight.update_exact_weight_edit(
            buffer_text=buffer_text,
            caret_index=caret_index,
            select_all=select_all,
        )

    def clear_exact_weight_edit(self) -> None:
        """Clear exact edit mode through the interaction owner."""

        self._exact_weight.clear_exact_weight_edit()

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning exact edit state."""

        return self._exact_weight.exact_weight_edit_token()

    def exact_weight_edit_active(self) -> bool:
        """Return whether exact edit mode is active."""

        return self._exact_weight.exact_weight_edit_active()

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the painted weight-text rect for one token."""

        return self._exact_weight.token_weight_text_rect(token)

    def handle_text_changed(self) -> None:
        """Refresh cached prompt semantics after the editor text changes."""

        text = self._editor.toPlainText()
        self._handle_text_changed_measured(text)

    def handle_document_semantics_changed(self) -> None:
        """Rebuild prompt state when source interpretation changes in place."""

        if (
            self._reorder.interaction_mode
            is PromptEditorInteractionMode.SEGMENT_REORDER
        ):
            self._reorder.cancel_segment_reorder_mode(restore_selection=False)
        self._autocomplete_timing_controller.clear_for_non_text_interaction()
        self._emphasis.clear_emphasis_adjustment_session(clear_transient_neutral=True)
        self._syntax_state.clear_transient_state()
        self._semantic_refresh.queue_source_changed(
            self._editor.toPlainText(),
            reason="document_semantics_changed",
        )
        self._semantic_refresh.flush(reason="document_semantics_changed")

    def _handle_text_changed_measured(self, text: str) -> None:
        """Queue prompt semantics after handle_text_changed starts probe timing."""

        self._handle_text_changed_measured_uninstrumented(text)

    def _handle_text_changed_measured_uninstrumented(self, text: str) -> None:
        """Queue prompt semantics after temporary timing starts."""

        self._autocomplete_timing_controller.cancel_pending_caret_refresh()
        if (
            self._reorder.interaction_mode
            is PromptEditorInteractionMode.SEGMENT_REORDER
            and self._syntax_state.pending_document_view is None
        ):
            self._reorder.cancel_segment_reorder_mode(restore_selection=False)

        pending_document_view = self._syntax_state.pending_document_view
        if (
            pending_document_view is None
            and text == self._syntax_state.document_view.source_text
        ):
            self.handle_cursor_position_changed()
            return
        if pending_document_view is None:
            self._emphasis.clear_emphasis_adjustment_session(
                clear_transient_neutral=True
            )
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

        self._reorder.enter_segment_reorder_mode()

    def cancel_segment_reorder_mode_from_keymap(
        self,
        intent: PromptReorderCancelIntent,
    ) -> None:
        """Cancel segment reorder mode for the keymap Escape path."""

        self._reorder.handle_reorder_cancel_intent(intent)

    def commit_segment_reorder_mode_from_keymap(
        self,
        intent: PromptReorderCommitIntent,
    ) -> None:
        """Commit segment reorder mode for the keymap Alt-release path."""

        self._reorder.commit_and_close_segment_overlay(intent)

    def move_keyboard_reorder_chip_from_keymap(
        self,
        intent: PromptReorderKeyboardMoveIntent,
    ) -> None:
        """Move one reorder chip through the existing reorder owner."""

        self._reorder.move_keyboard_reorder_chip(intent)

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

    def clear_keyboard_emphasis_session_from_keymap(self) -> None:
        """Clear keyboard-owned emphasis state after Ctrl release."""

        self._emphasis.clear_keyboard_emphasis_session()

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Consume syntax-owned inline clicks before normal text editing."""

        return self._mouse_selection.handle_mouse_press(event)

    def clear_mouse_emphasis_session(self) -> None:
        """Clear transient emphasis state for a mouse-owned syntax action."""

        self._emphasis.clear_mouse_emphasis_session()

    def syntax_action_at_mouse_position(
        self,
        position: QPointF,
    ) -> PromptSyntaxAction | None:
        """Return the prepared syntax action at one mouse position."""

        return self._syntax_state.syntax_action_at(position)

    def apply_mouse_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Apply a mouse-selected syntax action through the feature owner."""

        self.apply_syntax_action(action)

    def apply_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Apply one typed syntax action through the shared mutation route."""

        self._exact_weight.apply_syntax_action(
            action,
            emphasis_owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        )

    def apply_overlay_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Apply one overlay-owned syntax action through the shared mutation route."""

        self._exact_weight.apply_overlay_syntax_action(action)

    def handle_mouse_release(self) -> None:
        """Refresh state after caret movement caused by mouse interaction."""

        self._mouse_selection.handle_mouse_release()

    def schedule_mouse_release_autocomplete_refresh(self) -> None:
        """Dismiss autocomplete after mouse-driven caret movement."""

        self._autocomplete_timing_controller.suppress_for_mouse_navigation()

    def refresh_mouse_release_cursor_state(self) -> None:
        """Refresh cursor-derived syntax state after mouse interaction."""

        self.handle_cursor_position_changed()

    def handle_overlay_visible_token_changed(
        self,
        content_range: tuple[int, int] | None,
    ) -> None:
        """End overlay-owned emphasis adjustment when overlay ownership moves elsewhere."""

        self._exact_weight.handle_visible_token_content_range_changed(content_range)

    def handle_overlay_visible_token_range_changed(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Publish overlay-owned emphasis accent range through exact-weight owner."""

        self._exact_weight.handle_visible_token_range_changed(outer_range)

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
        self._emphasis.clear_emphasis_adjustment_session(clear_transient_neutral=True)

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
        self._emphasis.clear_emphasis_adjustment_session(clear_transient_neutral=True)
        self._syntax_state.clear_transient_state()

    def handle_hide(self) -> None:
        """Clear prompt-editor transient state when the editor hides."""

        self._autocomplete_timing_controller.handle_hide()
        if self._reorder.segment_overlay is not None:
            self._reorder.cancel_segment_reorder_mode(restore_selection=False)
        self._emphasis.clear_emphasis_adjustment_session(clear_transient_neutral=True)
        self._syntax_state.clear_transient_state()

    def handle_resize(self) -> None:
        """Reposition prompt-editor overlays after the editor is resized."""

        if self._reorder.segment_overlay is not None:
            self._reorder.position_segment_overlay()
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
            self._reorder.position_segment_overlay()
        self._syntax_state.refresh_geometry()
        if self._editor.has_pending_projection_update():
            return
        self._autocomplete.refresh_geometry()

    def modify_emphasis(self, delta: float) -> None:
        """Apply one emphasis adjustment to the current editor selection."""

        self._emphasis.modify_emphasis(delta)

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

    def _apply_weight_command_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one source-applied weight command."""

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


__all__ = ["PromptInteractionController", "PromptSemanticRefreshPort"]
