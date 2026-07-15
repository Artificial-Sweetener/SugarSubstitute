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

"""Coordinate keyboard-owned prompt emphasis interactions."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, TypeAlias, TypeGuard, cast

from PySide6.QtGui import QTextCursor

from substitute.application.prompt_editor import (
    PromptAdjustEmphasisAction,
    PromptAdjustEmphasisContentAction,
    PromptDocumentService,
    PromptDocumentView,
    PromptMutation,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSyntaxAction,
    PromptSyntaxSpanView,
)

from ..commands import PromptWeightCommandResult, PromptWeightCursorPolicy
from ..projection.model import (
    PromptProjectionTokenKind,
    PromptWeightControlIdentity,
    prompt_weight_content_identity,
)
from ..projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)

PromptEmphasisSyntaxAction: TypeAlias = (
    PromptAdjustEmphasisAction
    | PromptAdjustEmphasisContentAction
    | PromptSetEmphasisWeightAction
    | PromptSetEmphasisWeightContentAction
)


def is_emphasis_weight_action(
    action: PromptSyntaxAction,
) -> TypeGuard[PromptEmphasisSyntaxAction]:
    """Return whether one syntax action targets emphasis weight source."""

    return isinstance(
        action,
        (
            PromptAdjustEmphasisAction,
            PromptAdjustEmphasisContentAction,
            PromptSetEmphasisWeightAction,
            PromptSetEmphasisWeightContentAction,
        ),
    )


class _SelectionLike(Protocol):
    """Describe the minimal selection wrapper used by cursor helpers."""

    def isEmpty(self) -> bool:
        """Return whether the current selection is empty."""


class _PromptEmphasisCursor(Protocol):
    """Describe the cursor API consumed by emphasis interaction logic."""

    def position(self) -> int:
        """Return the current cursor position."""

    def selection(self) -> _SelectionLike:
        """Return a Qt-like selection wrapper."""

    def selectionStart(self) -> int:
        """Return the inclusive selection start."""

    def selectionEnd(self) -> int:
        """Return the exclusive selection end."""

    def setPosition(self, pos: int, mode: object | None = None) -> None:
        """Move or extend the cursor selection."""

    def select(self, mode: object) -> None:
        """Select text using one QTextCursor selection mode."""


class PromptEmphasisHost(Protocol):
    """Expose the editor seams required by prompt emphasis interactions."""

    @property
    def emphasis_feature_enabled(self) -> bool:
        """Return whether emphasis shortcuts should mutate the prompt."""

    def clear_autocomplete_for_emphasis(self) -> None:
        """Clear autocomplete state before a non-text emphasis interaction."""

    def textCursor(self) -> _PromptEmphasisCursor:
        """Return the editor's live cursor object."""

    def setTextCursor(self, cursor: _PromptEmphasisCursor) -> None:
        """Persist the supplied cursor selection back to the editor."""

    def setFocus(self) -> None:
        """Restore editor focus after an inline emphasis action."""

    def active_syntax_span_for_emphasis(self) -> PromptSyntaxSpanView | None:
        """Return the active syntax span visible to keyboard emphasis."""

    def document_view_for_emphasis(self) -> PromptDocumentView:
        """Return the current prompt document snapshot."""

    def execute_emphasis_weight_action(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> PromptWeightCommandResult[object]:
        """Execute one emphasis action through the shared weight command path."""

    def apply_emphasis_weight_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one emphasis weight command."""

    def refresh_emphasis_cursor_state(self) -> None:
        """Refresh cursor-derived syntax state after emphasis moves the caret."""

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


class PromptEmphasisController:
    """Own keyboard emphasis sessions and source-backed emphasis mutations."""

    def __init__(
        self,
        host: PromptEmphasisHost,
        *,
        document_service: PromptDocumentService,
    ) -> None:
        """Store the emphasis host and pure document-query service."""

        self._host = host
        self._document_service = document_service

    def modify_emphasis(self, delta: float) -> None:
        """Apply one keyboard emphasis adjustment to the current editor selection."""

        if not self._host.emphasis_feature_enabled:
            return
        self._host.clear_autocomplete_for_emphasis()
        session = self._host.emphasis_adjustment_session()
        if (
            session is not None
            and session.owner is PromptEmphasisAdjustmentOwner.KEYBOARD
        ):
            self._apply_keyboard_emphasis_action(
                PromptAdjustEmphasisContentAction(
                    content_start=session.content_start,
                    content_end=session.content_end,
                    delta=delta,
                )
            )
            return
        cursor = self._host.textCursor()
        if cursor.selection().isEmpty():
            active_span = self._host.active_syntax_span_for_emphasis()
            if active_span is not None and active_span.kind == "emphasis":
                content_range = self._content_range_for_active_emphasis_span(
                    outer_start=active_span.start,
                    outer_end=active_span.end,
                )
                if content_range is None:
                    return
                self._start_emphasis_adjustment_session(
                    owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
                    content_start=content_range[0],
                    content_end=content_range[1],
                    caret_boundary=self._caret_boundary_for_active_emphasis_span(
                        cursor_position=cursor.position(),
                        outer_start=active_span.start,
                        outer_end=active_span.end,
                    ),
                    wheel_intent_identity=prompt_weight_content_identity(
                        kind=PromptProjectionTokenKind.EMPHASIS,
                        content_start=content_range[0],
                        content_end=content_range[1],
                    ),
                )
                self._apply_keyboard_emphasis_action(
                    PromptAdjustEmphasisAction(
                        outer_start=active_span.start,
                        outer_end=active_span.end,
                        delta=delta,
                    ),
                )
                return
            cursor = self._expand_cursor_to_emphasis_or_word(cursor)
            self._host.setTextCursor(cursor)
        if cursor.selection().isEmpty():
            return
        selected_content_range = (cursor.selectionStart(), cursor.selectionEnd())
        self._start_emphasis_adjustment_session(
            owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
            content_start=selected_content_range[0],
            content_end=selected_content_range[1],
            caret_boundary=self._caret_boundary_for_cursor_selection(
                cursor,
                content_start=selected_content_range[0],
                content_end=selected_content_range[1],
            ),
            wheel_intent_identity=prompt_weight_content_identity(
                kind=PromptProjectionTokenKind.EMPHASIS,
                content_start=selected_content_range[0],
                content_end=selected_content_range[1],
            ),
        )

        self._apply_keyboard_emphasis_action(
            PromptAdjustEmphasisContentAction(
                content_start=cursor.selectionStart(),
                content_end=cursor.selectionEnd(),
                delta=delta,
            )
        )

    def clear_keyboard_emphasis_session(self) -> None:
        """Clear the active keyboard-owned emphasis adjustment session."""

        self.clear_emphasis_adjustment_session(
            owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
            clear_transient_neutral=True,
        )

    def clear_mouse_emphasis_session(self) -> None:
        """Clear emphasis sessions after a mouse-owned syntax interaction."""

        self.clear_emphasis_adjustment_session(clear_transient_neutral=True)

    def clear_emphasis_adjustment_session(
        self,
        *,
        clear_transient_neutral: bool,
        owner: PromptEmphasisAdjustmentOwner | None = None,
    ) -> None:
        """Clear the active adjustment session and any neutral shell it owns."""

        session = self._host.emphasis_adjustment_session()
        if owner is not None and (session is None or session.owner is not owner):
            return
        self._host.clear_emphasis_adjustment_session()
        if not clear_transient_neutral:
            return
        transient_owner = self._host.transient_neutral_emphasis_owner()
        if transient_owner is None:
            return
        if (
            owner is None
            or transient_owner is self._transient_owner_for_adjustment_owner(owner)
        ):
            self._host.clear_transient_neutral_emphasis()

    def apply_emphasis_syntax_action(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        owner: PromptEmphasisAdjustmentOwner | None,
        clear_autocomplete: bool = True,
        restore_focus: bool = True,
        cursor_policy: PromptWeightCursorPolicy = "preserve_cursor",
    ) -> None:
        """Apply one emphasis-shaped syntax action through the command route."""

        if clear_autocomplete:
            self._host.clear_autocomplete_for_emphasis()
        emphasis_session = self._session_for_emphasis_action(action, owner=owner)
        show_transient_neutral = self._action_hits_transient_neutral(action)
        result = self._host.execute_emphasis_weight_action(
            action,
            cursor_policy=cursor_policy,
        )
        self._apply_emphasis_mutation(
            result,
            session=emphasis_session,
            show_transient_neutral=show_transient_neutral,
        )
        if restore_focus:
            self._host.setFocus()

    def _apply_keyboard_emphasis_action(
        self,
        action: PromptEmphasisSyntaxAction,
    ) -> None:
        """Apply one keyboard-owned emphasis action and refresh the active target."""

        self.apply_emphasis_syntax_action(
            action,
            owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        )

    def _apply_emphasis_mutation(
        self,
        result: PromptWeightCommandResult[object],
        *,
        session: PromptEmphasisAdjustmentSession | None,
        show_transient_neutral: bool,
    ) -> None:
        """Adopt one emphasis command without leaving selection highlight feedback."""

        mutation = result.mutation
        if mutation is None:
            return
        accent_range = self._emphasis_feedback_outer_range_for_mutation(mutation)
        updated_session = self._updated_emphasis_adjustment_session_from_mutation(
            mutation,
            session=session,
        )
        self._host.clear_transient_neutral_emphasis()
        self._host.apply_emphasis_weight_result(result)
        if updated_session is None:
            self._host.clear_emphasis_adjustment_session()
        else:
            self._host.set_emphasis_adjustment_session(
                owner=updated_session.owner,
                content_start=updated_session.content_start,
                content_end=updated_session.content_end,
                caret_boundary=updated_session.caret_boundary,
                wheel_intent_identity=updated_session.wheel_intent_identity,
            )
        if show_transient_neutral and updated_session is not None:
            self._host.show_transient_neutral_emphasis(
                content_start=updated_session.content_start,
                content_end=updated_session.content_end,
                owner=self._transient_owner_for_adjustment_owner(updated_session.owner),
            )
        if (
            updated_session is not None
            and updated_session.owner is PromptEmphasisAdjustmentOwner.KEYBOARD
            and self._host.set_emphasis_caret_to_content_boundary(
                content_start=updated_session.content_start,
                content_end=updated_session.content_end,
                prefer_end=updated_session.caret_boundary
                is PromptEmphasisCaretBoundary.END,
            )
        ):
            self._host.refresh_emphasis_cursor_state()
        if accent_range is not None:
            self._host.pulse_emphasis_feedback(
                outer_start=accent_range[0],
                outer_end=accent_range[1],
            )

    def _emphasis_feedback_outer_range_for_mutation(
        self,
        mutation: PromptMutation,
    ) -> tuple[int, int] | None:
        """Return the updated emphasis shell range that should pulse after mutation."""

        if mutation.selection_start is None or mutation.selection_end is None:
            return None
        span = self._document_service.emphasis_for_content_range(
            mutation.document_view,
            content_start=mutation.selection_start,
            content_end=mutation.selection_end,
        )
        if span is None:
            return None
        return (span.outer_start, span.outer_end)

    def _updated_emphasis_adjustment_session_from_mutation(
        self,
        mutation: PromptMutation,
        *,
        session: PromptEmphasisAdjustmentSession | None,
    ) -> PromptEmphasisAdjustmentSession | None:
        """Return the post-mutation adjustment session for one emphasis change."""

        if session is None:
            return None
        if mutation.selection_start is None or mutation.selection_end is None:
            return session
        if mutation.selection_start >= mutation.selection_end:
            return None
        return PromptEmphasisAdjustmentSession(
            owner=session.owner,
            content_start=mutation.selection_start,
            content_end=mutation.selection_end,
            caret_boundary=session.caret_boundary,
            wheel_intent_identity=session.wheel_intent_identity,
        )

    def _session_for_emphasis_action(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        owner: PromptEmphasisAdjustmentOwner | None,
    ) -> PromptEmphasisAdjustmentSession | None:
        """Start or reuse one shared emphasis-adjustment session for an action."""

        if owner is None:
            return None
        content_range = self._content_range_for_emphasis_action(action)
        if content_range is None:
            return None
        return self._start_emphasis_adjustment_session(
            owner=owner,
            content_start=content_range[0],
            content_end=content_range[1],
            caret_boundary=self._caret_boundary_for_content_range(
                content_start=content_range[0],
                content_end=content_range[1],
            ),
            wheel_intent_identity=self._wheel_intent_identity_for_emphasis_session(
                owner=owner,
                content_start=content_range[0],
                content_end=content_range[1],
            ),
        )

    def _start_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity,
    ) -> PromptEmphasisAdjustmentSession:
        """Persist one active emphasis-adjustment session on the editor surface."""

        self._host.set_emphasis_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )
        return cast(
            PromptEmphasisAdjustmentSession,
            self._host.emphasis_adjustment_session(),
        )

    def _wheel_intent_identity_for_emphasis_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
    ) -> PromptWeightControlIdentity:
        """Return the stable wheel identity for a new or continuing emphasis edit."""

        session = self._host.emphasis_adjustment_session()
        if (
            session is not None
            and session.owner is owner
            and session.wheel_intent_identity is not None
        ):
            return session.wheel_intent_identity
        return prompt_weight_content_identity(
            kind=PromptProjectionTokenKind.EMPHASIS,
            content_start=content_start,
            content_end=content_end,
        )

    @staticmethod
    def _transient_owner_for_adjustment_owner(
        owner: PromptEmphasisAdjustmentOwner,
    ) -> PromptTransientNeutralEmphasisOwner:
        """Return the transient-shell owner corresponding to one session owner."""

        if owner is PromptEmphasisAdjustmentOwner.KEYBOARD:
            return PromptTransientNeutralEmphasisOwner.KEYBOARD
        return PromptTransientNeutralEmphasisOwner.OVERLAY

    def _content_range_for_emphasis_action(
        self,
        action: PromptEmphasisSyntaxAction,
    ) -> tuple[int, int] | None:
        """Return the content range targeted by one typed emphasis action."""

        if isinstance(
            action,
            (PromptAdjustEmphasisContentAction, PromptSetEmphasisWeightContentAction),
        ):
            return (action.content_start, action.content_end)
        span = self._document_service.emphasis_for_outer_range(
            self._host.document_view_for_emphasis(),
            outer_start=action.outer_start,
            outer_end=action.outer_end,
        )
        if span is None:
            return None
        return (span.content_start, span.content_end)

    def _content_range_for_active_emphasis_span(
        self,
        *,
        outer_start: int,
        outer_end: int,
    ) -> tuple[int, int] | None:
        """Return the content range owned by one active emphasis shell."""

        span = self._document_service.emphasis_for_outer_range(
            self._host.document_view_for_emphasis(),
            outer_start=outer_start,
            outer_end=outer_end,
        )
        if span is None:
            return None
        return (span.content_start, span.content_end)

    def _caret_boundary_for_active_emphasis_span(
        self,
        *,
        cursor_position: int,
        outer_start: int,
        outer_end: int,
    ) -> PromptEmphasisCaretBoundary:
        """Return the stable caret boundary for one active emphasis shell."""

        content_range = self._content_range_for_active_emphasis_span(
            outer_start=outer_start,
            outer_end=outer_end,
        )
        if content_range is None:
            return PromptEmphasisCaretBoundary.END
        midpoint = content_range[0] + ((content_range[1] - content_range[0]) / 2.0)
        if cursor_position >= midpoint:
            return PromptEmphasisCaretBoundary.END
        return PromptEmphasisCaretBoundary.START

    def _caret_boundary_for_cursor_selection(
        self,
        cursor: _PromptEmphasisCursor,
        *,
        content_start: int,
        content_end: int,
    ) -> PromptEmphasisCaretBoundary:
        """Return the caret boundary implied by one selected content range."""

        _ = content_end
        if cursor.position() == content_start:
            return PromptEmphasisCaretBoundary.START
        return PromptEmphasisCaretBoundary.END

    def _caret_boundary_for_content_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> PromptEmphasisCaretBoundary:
        """Return the stable caret boundary for one content range."""

        active_session = self._host.emphasis_adjustment_session()
        if (
            active_session is not None
            and active_session.content_start == content_start
            and active_session.content_end == content_end
        ):
            return active_session.caret_boundary
        cursor = self._host.textCursor()
        if (
            content_start <= cursor.selectionStart() <= content_end
            and content_start <= cursor.selectionEnd() <= content_end
            and not cursor.selection().isEmpty()
        ):
            return self._caret_boundary_for_cursor_selection(
                cursor,
                content_start=content_start,
                content_end=content_end,
            )
        if content_start <= cursor.position() <= content_end:
            midpoint = content_start + ((content_end - content_start) / 2.0)
            if cursor.position() >= midpoint:
                return PromptEmphasisCaretBoundary.END
            return PromptEmphasisCaretBoundary.START
        return PromptEmphasisCaretBoundary.END

    def _expand_cursor_to_emphasis_or_word(
        self,
        cursor: _PromptEmphasisCursor,
    ) -> _PromptEmphasisCursor:
        """Select the innermost emphasis content or fall back to WordUnderCursor."""

        emphasis = self._document_service.emphasis_at_position(
            self._host.document_view_for_emphasis(),
            cursor.position(),
        )
        if emphasis is not None:
            self._set_cursor_selection(
                cursor,
                start=emphasis.content_start,
                end=emphasis.content_end,
            )
            return cursor

        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor

    def _action_hits_transient_neutral(
        self,
        action: PromptEmphasisSyntaxAction,
    ) -> bool:
        """Return whether one emphasis action resolves to visible transient neutral."""

        if isinstance(
            action,
            (PromptAdjustEmphasisContentAction, PromptSetEmphasisWeightContentAction),
        ):
            if isinstance(action, PromptAdjustEmphasisContentAction):
                span = self._document_service.emphasis_for_content_range(
                    self._host.document_view_for_emphasis(),
                    content_start=action.content_start,
                    content_end=action.content_end,
                )
                if span is None:
                    return False
                adjusted_weight = span.weight + Decimal(str(action.delta))
                return adjusted_weight.quantize(Decimal("0.00")) == Decimal("1.00")
            return Decimal(str(action.weight)).quantize(Decimal("0.00")) == Decimal(
                "1.00"
            )
        span = self._document_service.emphasis_for_outer_range(
            self._host.document_view_for_emphasis(),
            outer_start=action.outer_start,
            outer_end=action.outer_end,
        )
        if span is None:
            return False
        adjusted_weight = (
            span.weight + Decimal(str(action.delta))
            if isinstance(action, PromptAdjustEmphasisAction)
            else Decimal(str(action.weight))
        )
        return adjusted_weight.quantize(Decimal("0.00")) == Decimal("1.00")

    @staticmethod
    def _set_cursor_selection(
        cursor: _PromptEmphasisCursor,
        *,
        start: int,
        end: int,
    ) -> None:
        """Select one half-open source range on the supplied cursor."""

        cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
