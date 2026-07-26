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

"""Own prompt emphasis sessions and exact-weight interaction routing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QRectF
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QScrollBar

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSyntaxAction,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)

from ..commands.weight_commands import (
    PromptSyntaxWeightAction,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    PromptWeightCursorPolicy,
)
from ..core.projection.tokens import PromptProjectionToken, PromptWeightControlIdentity
from ..core.state.revisions import PromptSourceIdentity
from ..features.feature_profile_controller import PromptFeatureProfileController
from ..overlays.token_weight_gestures import (
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)
from ..projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)
from ..syntax_renderers import PromptSyntaxStateController
from .autocomplete_timing import PromptAutocompleteTimingController
from .emphasis_controller import (
    PromptEmphasisController,
    PromptEmphasisSyntaxAction,
)
from .exact_weight_controller import (
    PromptExactWeightController,
    PromptExactWeightProjectionHost,
)


class PromptWeightInteractionSelection(Protocol):
    """Describe the selection query needed by emphasis range logic."""

    def isEmpty(self) -> bool:
        """Return whether the selection has no source range."""


class PromptWeightInteractionCursor(Protocol):
    """Describe the cursor operations needed by emphasis selection logic."""

    def position(self) -> int:
        """Return the current cursor position."""

    def selection(self) -> PromptWeightInteractionSelection:
        """Return the current selection wrapper."""

    def selectionStart(self) -> int:
        """Return the inclusive selection start."""

    def selectionEnd(self) -> int:
        """Return the exclusive selection end."""

    def setPosition(self, position: int, mode: object | None = None) -> None:
        """Move or extend the cursor selection."""

    def select(self, mode: object) -> None:
        """Select one Qt-defined cursor range."""


class PromptWeightInteractionEditor(Protocol):
    """Describe editor commands and transient state used by weight interactions."""

    def textCursor(self) -> PromptWeightInteractionCursor:
        """Return the current editor cursor."""

    def setTextCursor(self, cursor: PromptWeightInteractionCursor) -> None:
        """Store one editor cursor."""

    def toPlainText(self) -> str:
        """Return current prompt source text."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return current source identity for prepared command rejection."""

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute one source-backed weight command."""

    def setFocus(self) -> None:
        """Restore prompt input focus."""

    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Show one short emphasis shell accent."""

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Store the sole emphasis adjustment session."""

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear the active emphasis adjustment session."""

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis adjustment session."""

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner,
    ) -> None:
        """Show one temporary neutral emphasis shell."""

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear the temporary neutral emphasis shell."""

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the temporary neutral shell."""

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the content range of the temporary neutral shell."""

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at a projected emphasis-content boundary."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the editor-visible vertical scroll bar."""


class PromptWeightSemanticRefreshPort(Protocol):
    """Describe semantic refresh ownership used after accepted weight commands."""

    def cancel_pending(self, *, reason: str) -> None:
        """Cancel stale queued semantic work."""


class PromptWeightInteraction:
    """Own emphasis and exact-weight feature interaction without a general host facade."""

    def __init__(
        self,
        *,
        editor: PromptWeightInteractionEditor,
        autocomplete_timing: PromptAutocompleteTimingController,
        syntax_state: PromptSyntaxStateController,
        document_service: PromptDocumentService,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        feature_profile: PromptFeatureProfileController,
        semantic_refresh: PromptWeightSemanticRefreshPort,
        projection: PromptExactWeightProjectionHost | None,
    ) -> None:
        """Construct one direct owner for all prompt weight interactions."""

        self._editor = editor
        self._autocomplete_timing = autocomplete_timing
        self._syntax_state = syntax_state
        self._mutation_service = mutation_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._feature_profile = feature_profile
        self._semantic_refresh = semantic_refresh
        self._emphasis = PromptEmphasisController(
            self, document_service=document_service
        )
        self._exact_weight = PromptExactWeightController(
            self, projection_host=projection
        )

    def modify_emphasis(self, delta: float) -> None:
        """Apply one keyboard emphasis adjustment."""

        self._emphasis.modify_emphasis(delta)

    def clear_keyboard_emphasis_session(self) -> None:
        """Clear keyboard-owned emphasis adjustment state."""

        self._emphasis.clear_keyboard_emphasis_session()

    def clear_mouse_emphasis_session(self) -> None:
        """Clear a mouse-owned emphasis adjustment session."""

        self._emphasis.clear_mouse_emphasis_session()

    def clear_transient_emphasis(self) -> None:
        """Clear every emphasis session and temporary neutral shell."""

        self._emphasis.clear_emphasis_adjustment_session(clear_transient_neutral=True)

    def apply_syntax_action(
        self,
        action: PromptSyntaxAction,
        *,
        owner: PromptEmphasisAdjustmentOwner = PromptEmphasisAdjustmentOwner.OVERLAY,
    ) -> None:
        """Apply one syntax action through the weight feature owner."""

        self._exact_weight.apply_syntax_action(action, emphasis_owner=owner)

    def apply_overlay_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Apply one overlay-owned syntax action."""

        self._exact_weight.apply_overlay_syntax_action(action)

    def apply_token_weight_step_intent(
        self,
        intent: PromptTokenWeightStepIntent,
    ) -> None:
        """Apply one token-weight step intent."""

        self._exact_weight.apply_token_weight_step_intent(intent)

    def apply_token_weight_wheel_step_intent(
        self,
        intent: PromptTokenWeightWheelStepIntent,
    ) -> None:
        """Apply one token-weight wheel intent."""

        self._exact_weight.apply_token_weight_wheel_step_intent(intent)

    def handle_visible_token_range_changed(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Publish one overlay-visible emphasis accent range."""

        self._exact_weight.handle_visible_token_range_changed(outer_range)

    def handle_visible_token_content_range_changed(
        self,
        content_range: tuple[int, int] | None,
    ) -> None:
        """Retire stale overlay-owned emphasis state."""

        self._exact_weight.handle_visible_token_content_range_changed(content_range)

    def begin_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact editing for one weighted token."""

        self._exact_weight.begin_exact_weight_edit(token)

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start projection-owned exact editing for one weighted token."""

        self._exact_weight.start_exact_weight_edit(token)

    def cancel_exact_weight_edit(self) -> None:
        """Cancel an active exact-weight edit."""

        self._exact_weight.cancel_exact_weight_edit()

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update the projection-owned exact-weight edit buffer."""

        self._exact_weight.update_exact_weight_edit(
            buffer_text=buffer_text,
            caret_index=caret_index,
            select_all=select_all,
        )

    def clear_exact_weight_edit(self) -> None:
        """Clear active exact-weight edit state without mutation."""

        self._exact_weight.clear_exact_weight_edit()

    def finalize_exact_weight_edit(self) -> None:
        """Commit a valid active exact-weight edit."""

        self._exact_weight.finalize_exact_weight_edit()

    def handle_exact_weight_key_press(self, event: QKeyEvent) -> bool:
        """Route one key to active exact-weight editing."""

        return self._exact_weight.handle_exact_weight_key_press(event)

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the token owning exact edit state."""

        return self._exact_weight.exact_weight_edit_token()

    def exact_weight_edit_active(self) -> bool:
        """Return whether exact-weight editing is active."""

        return self._exact_weight.exact_weight_edit_active()

    def update_exact_weight_caret(
        self,
        *,
        token: PromptProjectionToken,
        caret_index: int,
    ) -> None:
        """Move the exact-edit caret for one token."""

        self._exact_weight.update_exact_weight_caret(
            token=token,
            caret_index=caret_index,
        )

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return current projection-owned weight text geometry."""

        return self._exact_weight.token_weight_text_rect(token)

    @property
    def emphasis_feature_enabled(self) -> bool:
        """Return whether emphasis feature commands are enabled."""

        return self._feature_profile.emphasis_enabled

    def clear_autocomplete_for_emphasis(self) -> None:
        """Clear autocomplete before an emphasis command."""

        self._autocomplete_timing.clear_for_non_text_interaction()

    def textCursor(self) -> PromptWeightInteractionCursor:
        """Return the editor cursor for emphasis selection operations."""

        return self._editor.textCursor()

    def setTextCursor(self, cursor: PromptWeightInteractionCursor) -> None:
        """Persist an emphasis-updated cursor to the editor."""

        self._editor.setTextCursor(cursor)

    def setFocus(self) -> None:
        """Restore editor focus after an accepted weight command."""

        self._editor.setFocus()

    def active_syntax_span_for_emphasis(self) -> PromptSyntaxSpanView | None:
        """Return the active syntax span for keyboard emphasis."""

        return self._syntax_state.active_syntax_span

    def document_view_for_emphasis(self) -> PromptDocumentView:
        """Return the current syntax document snapshot."""

        return self._syntax_state.document_view

    def execute_emphasis_weight_action(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> PromptWeightCommandResult[object]:
        """Execute one emphasis weight command through the source boundary."""

        return self._execute_weight_action(action, cursor_policy=cursor_policy)

    def apply_emphasis_weight_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt an emphasis weight command result."""

        self._apply_weight_command_result(result)

    def refresh_emphasis_cursor_state(self) -> None:
        """Refresh active syntax state after emphasis moves the caret."""

        self._syntax_state.refresh_active_span()

    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Show one adjusted emphasis shell accent."""

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
        """Persist one emphasis adjustment session to its sole state owner."""

        self._editor.set_emphasis_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear the active emphasis adjustment session."""

        self._editor.clear_emphasis_adjustment_session()

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis adjustment session."""

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
        """Show a temporary neutral emphasis shell."""

        self._editor.show_transient_neutral_emphasis(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear the temporary neutral emphasis shell."""

        self._editor.clear_transient_neutral_emphasis()

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the temporary neutral shell owner."""

        return self._editor.transient_neutral_emphasis_owner()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the temporary neutral shell range."""

        return self._editor.transient_neutral_emphasis_range()

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place caret at a source-backed emphasis content boundary."""

        return self._editor.set_emphasis_caret_to_content_boundary(
            content_start=content_start,
            content_end=content_end,
            prefer_end=prefer_end,
        )

    def clear_keyboard_emphasis_session_for_exact_weight(self) -> None:
        """Clear keyboard emphasis before an overlay-owned weight action."""

        self._emphasis.clear_keyboard_emphasis_session()

    def clear_autocomplete_for_exact_weight(self) -> None:
        """Clear autocomplete before exact-weight interaction."""

        self._autocomplete_timing.clear_for_non_text_interaction()

    def set_focus_after_exact_weight_action(self) -> None:
        """Restore focus after exact-weight action routing."""

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
        """Apply an exact-weight emphasis action through the emphasis owner."""

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
        """Execute a non-emphasis exact-weight command."""

        return self._execute_weight_action(action, cursor_policy=cursor_policy)

    def apply_exact_weight_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt a non-emphasis exact-weight command result."""

        self._apply_weight_command_result(result)

    def clear_overlay_emphasis_session_for_exact_weight(self) -> None:
        """Clear overlay-owned emphasis session after overlay state changes."""

        self._emphasis.clear_emphasis_adjustment_session(
            owner=PromptEmphasisAdjustmentOwner.OVERLAY,
            clear_transient_neutral=True,
        )

    def preserve_surface_scroll_position_for_exact_weight(
        self,
        action: Callable[[], None],
    ) -> None:
        """Run exact-weight work without scrolling toward the text caret."""

        scroll_bar = self._editor.verticalScrollBar()
        scroll_value = scroll_bar.value()
        action()
        scroll_bar.setValue(
            max(scroll_bar.minimum(), min(scroll_bar.maximum(), scroll_value))
        )

    def _execute_weight_action(
        self,
        action: PromptSyntaxWeightAction,
        *,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> PromptWeightCommandResult[object]:
        """Execute one typed weight action through the source command boundary."""

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

    def _apply_weight_command_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt one source-applied weight result and refresh active syntax."""

        mutation = result.mutation
        if mutation is None:
            return
        self._semantic_refresh.cancel_pending(reason="state_applied")
        self._syntax_state.clear_pending_document_view()
        self._syntax_state.apply_mutation(
            mutation,
            current_text=self._editor.toPlainText(),
            render_plan=result.render_plan,
        )
        self._syntax_state.refresh_active_span()


__all__ = [
    "PromptWeightInteraction",
    "PromptWeightInteractionEditor",
    "PromptWeightSemanticRefreshPort",
]
