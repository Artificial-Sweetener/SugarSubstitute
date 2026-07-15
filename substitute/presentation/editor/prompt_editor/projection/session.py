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

"""Track temporary expansion of collapsed projection tokens during direct editing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from substitute.application.prompt_editor import PromptDocumentView
from substitute.application.prompt_editor import PromptDiagnostic
from substitute.shared.logging.logger import get_logger, log_debug

from ..autocomplete_preview_state import PromptAutocompletePreviewState
from .model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptWeightControlIdentity,
    prompt_weight_control_identity,
)

_LOGGER = get_logger("presentation.editor.prompt_editor.projection_session")


class PromptTransientNeutralEmphasisOwner(str, Enum):
    """Describe which interaction path currently owns a transient neutral shell."""

    CARET = "caret"
    KEYBOARD = "keyboard"
    OVERLAY = "overlay"


class PromptEmphasisAdjustmentOwner(str, Enum):
    """Describe which interaction source currently owns emphasis adjustment."""

    KEYBOARD = "keyboard"
    OVERLAY = "overlay"


class PromptEmphasisCaretBoundary(str, Enum):
    """Describe which token-content edge should keep caret ownership stable."""

    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class PromptTransientNeutralEmphasis:
    """Track one synthetic neutral-emphasis shell shown only during adjustment."""

    content_start: int
    content_end: int
    display_weight_text: str = "1.00"
    owner: PromptTransientNeutralEmphasisOwner = (
        PromptTransientNeutralEmphasisOwner.CARET
    )


@dataclass(frozen=True, slots=True)
class PromptExactWeightEditState:
    """Track one projection-owned exact-weight edit session for an emphasis token."""

    token_id: str
    synthetic: bool
    outer_start: int
    outer_end: int
    content_start: int
    content_end: int
    original_value_text: str
    buffer_text: str
    slot_width: float
    caret_index: int
    select_all: bool


@dataclass(frozen=True, slots=True)
class PromptPendingAutoExactWeightEdit:
    """Track an auto-created emphasis token awaiting exact edit handoff."""

    source_text: str
    cursor_position: int


@dataclass(frozen=True, slots=True)
class PromptEmphasisAdjustmentSession:
    """Track one active emphasis-adjustment session owned by UI interaction."""

    owner: PromptEmphasisAdjustmentOwner
    content_start: int
    content_end: int
    caret_boundary: PromptEmphasisCaretBoundary
    wheel_intent_identity: PromptWeightControlIdentity | None = field(
        default=None,
        compare=False,
    )


@dataclass(frozen=True, slots=True)
class PromptTokenCollapseDecision:
    """Describe whether an expanded projection token may collapse."""

    collapsed: bool
    reason: str
    expanded_source_range: tuple[int, int] | None
    matching_syntax_span_present: bool = False


@dataclass(slots=True)
class PromptProjectionSession:
    """Own the minimal token-expansion state needed for direct token editing."""

    expanded_source_range: tuple[int, int] | None = None
    emphasis_adjustment_session_state: PromptEmphasisAdjustmentSession | None = None
    transient_neutral_emphasis: PromptTransientNeutralEmphasis | None = None
    exact_weight_edit: PromptExactWeightEditState | None = None
    pending_auto_exact_weight_edit: PromptPendingAutoExactWeightEdit | None = None
    autocomplete_preview: PromptAutocompletePreviewState | None = None
    search_match_ranges: tuple[tuple[int, int], ...] = ()
    active_search_match_index: int | None = None
    diagnostics: tuple[PromptDiagnostic, ...] = ()

    def is_expanded(self, token: PromptProjectionToken) -> bool:
        """Return whether the supplied token is currently expanded back to raw text."""

        return self.expanded_source_range == (token.source_start, token.source_end)

    def expand_token(self, token: PromptProjectionToken) -> None:
        """Expand one collapsed token back into its raw source text."""

        self.expanded_source_range = (token.source_start, token.source_end)

    def clear(self) -> None:
        """Collapse any expanded token back into the rendered projection."""

        self.expanded_source_range = None
        self.emphasis_adjustment_session_state = None
        self.transient_neutral_emphasis = None
        self.exact_weight_edit = None
        self.pending_auto_exact_weight_edit = None
        self.autocomplete_preview = None
        self.search_match_ranges = ()
        self.active_search_match_index = None
        self.diagnostics = ()

    def set_autocomplete_preview(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace the current projection-owned autocomplete preview state."""

        self.autocomplete_preview = preview_state

    def clear_autocomplete_preview(self) -> None:
        """Remove any active projection-owned autocomplete preview."""

        self.autocomplete_preview = None

    def set_search_matches(
        self,
        match_ranges: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Replace the transient search ranges rendered by the projection surface."""

        self.search_match_ranges = match_ranges
        self.active_search_match_index = active_index

    def clear_search_matches(self) -> None:
        """Clear any transient search highlight ranges from the projection session."""

        self.search_match_ranges = ()
        self.active_search_match_index = None

    def set_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Replace the transient diagnostic ranges."""

        self.diagnostics = diagnostics

    def clear_diagnostics(self) -> None:
        """Clear transient diagnostic ranges."""

        self.diagnostics = ()

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Store one active emphasis-adjustment session on the projection."""

        self.emphasis_adjustment_session_state = PromptEmphasisAdjustmentSession(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Remove any active emphasis-adjustment session from the projection."""

        self.emphasis_adjustment_session_state = None

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when one exists."""

        return self.emphasis_adjustment_session_state

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range when present."""

        session = self.emphasis_adjustment_session_state
        if session is None:
            return None
        return (session.content_start, session.content_end)

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active adjustment session still owns one content range."""

        session = self.emphasis_adjustment_session_state
        if session is None:
            return False
        return (
            session.content_start == content_start
            and session.content_end == content_end
        )

    def prompt_weight_wheel_identity(
        self,
        token: PromptProjectionToken,
    ) -> PromptWeightControlIdentity:
        """Return stable wheel ownership identity for one prompt weight token."""

        session = self.emphasis_adjustment_session_state
        if (
            token.kind is PromptProjectionTokenKind.EMPHASIS
            and session is not None
            and session.wheel_intent_identity is not None
            and token.content_start == session.content_start
            and token.content_end == session.content_end
        ):
            return session.wheel_intent_identity
        return prompt_weight_control_identity(token)

    def set_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner,
    ) -> None:
        """Show one synthetic neutral-emphasis shell for the supplied content range."""

        self.transient_neutral_emphasis = PromptTransientNeutralEmphasis(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )

    def clear_transient_neutral_emphasis(self) -> None:
        """Remove any synthetic neutral-emphasis shell from the session."""

        self.transient_neutral_emphasis = None

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Remove the transient shell only when the overlay interaction owns it."""

        emphasis = self.transient_neutral_emphasis
        if (
            emphasis is None
            or emphasis.owner is not PromptTransientNeutralEmphasisOwner.OVERLAY
        ):
            return
        self.transient_neutral_emphasis = None

    def start_exact_weight_edit(
        self,
        *,
        token_id: str,
        synthetic: bool,
        outer_start: int,
        outer_end: int,
        content_start: int,
        content_end: int,
        original_value_text: str,
        buffer_text: str,
        slot_width: float,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Start one projection-owned exact edit session for an emphasis number."""

        self.exact_weight_edit = PromptExactWeightEditState(
            token_id=token_id,
            synthetic=synthetic,
            outer_start=outer_start,
            outer_end=outer_end,
            content_start=content_start,
            content_end=content_end,
            original_value_text=original_value_text,
            buffer_text=buffer_text,
            slot_width=slot_width,
            caret_index=caret_index,
            select_all=select_all,
        )
        self.pending_auto_exact_weight_edit = None

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Replace the active exact edit buffer state while preserving token ownership."""

        edit_state = self.exact_weight_edit
        if edit_state is None:
            return
        self.exact_weight_edit = PromptExactWeightEditState(
            token_id=edit_state.token_id,
            synthetic=edit_state.synthetic,
            outer_start=edit_state.outer_start,
            outer_end=edit_state.outer_end,
            content_start=edit_state.content_start,
            content_end=edit_state.content_end,
            original_value_text=edit_state.original_value_text,
            buffer_text=buffer_text,
            slot_width=edit_state.slot_width,
            caret_index=caret_index,
            select_all=select_all,
        )

    def clear_exact_weight_edit(self) -> None:
        """Clear any active projection-owned exact emphasis edit session."""

        self.exact_weight_edit = None

    def set_pending_auto_exact_weight_edit(
        self,
        *,
        source_text: str,
        cursor_position: int,
    ) -> None:
        """Remember an auto-created emphasis token should enter exact edit."""

        self.pending_auto_exact_weight_edit = PromptPendingAutoExactWeightEdit(
            source_text=source_text,
            cursor_position=cursor_position,
        )

    def clear_pending_auto_exact_weight_edit(self) -> None:
        """Clear any pending auto-created exact edit handoff."""

        self.pending_auto_exact_weight_edit = None

    def exact_weight_edit_token_id(self) -> str | None:
        """Return the current exact-edit token identifier when exact edit is active."""

        edit_state = self.exact_weight_edit
        if edit_state is None:
            return None
        return edit_state.token_id

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the current synthetic neutral-emphasis content range when present."""

        emphasis = self.transient_neutral_emphasis
        if emphasis is None:
            return None
        return (emphasis.content_start, emphasis.content_end)

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the current transient neutral shell when present."""

        emphasis = self.transient_neutral_emphasis
        if emphasis is None:
            return None
        return emphasis.owner

    def transient_neutral_emphasis_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the transient neutral shell still covers one content range."""

        emphasis = self.transient_neutral_emphasis
        if emphasis is None:
            return False
        return (
            emphasis.content_start == content_start
            and emphasis.content_end == content_end
        )

    def selection_within_transient_neutral_emphasis(
        self,
        *,
        selection_start: int,
        selection_end: int,
    ) -> bool:
        """Return whether the supplied selection still belongs to the transient shell."""

        emphasis = self.transient_neutral_emphasis
        if emphasis is None:
            return False
        return (
            emphasis.content_start <= selection_start <= emphasis.content_end
            and emphasis.content_start <= selection_end <= emphasis.content_end
        )

    def collapse_if_cursor_left_token(
        self,
        document_view: PromptDocumentView,
        *,
        selection_start: int,
        selection_end: int,
    ) -> bool:
        """Collapse the expanded token once the caret leaves it and parsing is valid."""

        decision = self.collapse_decision(
            document_view,
            selection_start=selection_start,
            selection_end=selection_end,
        )
        _log_token_collapse_decision(
            decision,
            selection_start=selection_start,
            selection_end=selection_end,
        )
        if decision.collapsed and decision.expanded_source_range is not None:
            self.expanded_source_range = None
            return True
        return False

    def collapse_decision(
        self,
        document_view: PromptDocumentView,
        *,
        selection_start: int,
        selection_end: int,
    ) -> PromptTokenCollapseDecision:
        """Return the current expanded-token collapse decision without mutating state."""

        expanded_range = self.expanded_source_range
        if expanded_range is None:
            return PromptTokenCollapseDecision(
                collapsed=False,
                reason="no_expanded_token",
                expanded_source_range=None,
            )
        matching_syntax_span_present = any(
            span.start == expanded_range[0] and span.end == expanded_range[1]
            for span in document_view.syntax_spans
        )
        if (
            expanded_range[0] <= selection_start <= expanded_range[1]
            or expanded_range[0] <= selection_end <= expanded_range[1]
        ):
            return PromptTokenCollapseDecision(
                collapsed=False,
                reason="selection_inside_or_on_boundary",
                expanded_source_range=expanded_range,
                matching_syntax_span_present=matching_syntax_span_present,
            )
        if matching_syntax_span_present:
            return PromptTokenCollapseDecision(
                collapsed=True,
                reason="collapsed",
                expanded_source_range=expanded_range,
                matching_syntax_span_present=True,
            )
        return PromptTokenCollapseDecision(
            collapsed=False,
            reason="syntax_span_missing",
            expanded_source_range=expanded_range,
            matching_syntax_span_present=False,
        )


def _log_token_collapse_decision(
    decision: PromptTokenCollapseDecision,
    *,
    selection_start: int,
    selection_end: int,
) -> None:
    """Emit one expanded-token collapse diagnostic when a token is expanded."""

    expanded_range = decision.expanded_source_range
    if expanded_range is None:
        return
    log_debug(
        _LOGGER,
        "prompt_projection_token.collapse_decision",
        reason=decision.reason,
        expanded_source_start=expanded_range[0],
        expanded_source_end=expanded_range[1],
        selection_start=selection_start,
        selection_end=selection_end,
        matching_syntax_span_present=decision.matching_syntax_span_present,
    )


__all__ = [
    "PromptEmphasisAdjustmentOwner",
    "PromptEmphasisAdjustmentSession",
    "PromptEmphasisCaretBoundary",
    "PromptExactWeightEditState",
    "PromptProjectionSession",
    "PromptTokenCollapseDecision",
    "PromptTransientNeutralEmphasis",
    "PromptTransientNeutralEmphasisOwner",
]
