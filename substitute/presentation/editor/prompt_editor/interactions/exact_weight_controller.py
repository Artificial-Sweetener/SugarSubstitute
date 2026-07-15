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

"""Coordinate overlay-driven exact prompt weight interactions."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
import re
from typing import Protocol, TypeGuard

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QKeyEvent

from substitute.application.prompt_editor import (
    PromptAdjustEmphasisAction,
    PromptAdjustEmphasisContentAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
    PromptSyntaxAction,
)

from ..overlays.token_weight_gestures import (
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)
from ..commands import (
    PromptSyntaxWeightAction,
    PromptWeightCommandResult,
    PromptWeightCursorPolicy,
)
from ..projection.model import PromptProjectionToken, PromptProjectionTokenKind
from ..projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptTransientNeutralEmphasisOwner,
)
from .emphasis_controller import (
    PromptEmphasisSyntaxAction,
    is_emphasis_weight_action,
)


_EXACT_WEIGHT_EDIT_PATTERN = re.compile(r"-?\d*(?:\.\d{0,2})?")
_MINIMUM_EXACT_WEIGHT = Decimal("0.05")


def is_weight_syntax_action(
    action: PromptSyntaxAction,
) -> TypeGuard[PromptSyntaxWeightAction]:
    """Return whether one syntax action belongs to the weight command scope."""

    if is_emphasis_weight_action(action):
        return True
    return isinstance(
        action,
        (
            PromptAdjustLoraWeightAction,
            PromptSetLoraWeightAction,
            PromptSetWildcardTagAction,
            PromptAdjustWildcardTagAction,
        ),
    )


class PromptExactWeightHost(Protocol):
    """Expose the non-visual editor seams needed by exact-weight coordination."""

    def clear_keyboard_emphasis_session_for_exact_weight(self) -> None:
        """Clear keyboard-owned emphasis state before overlay-owned weight edits."""

    def clear_autocomplete_for_exact_weight(self) -> None:
        """Clear autocomplete state before a non-text weight interaction."""

    def set_focus_after_exact_weight_action(self) -> None:
        """Restore editor focus after an overlay or syntax weight action."""

    def apply_emphasis_weight_action_from_exact(
        self,
        action: PromptEmphasisSyntaxAction,
        *,
        owner: PromptEmphasisAdjustmentOwner | None,
        clear_autocomplete: bool,
        restore_focus: bool,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> None:
        """Apply one emphasis-shaped action through the emphasis interaction owner."""

    def execute_exact_weight_action(
        self,
        action: PromptSyntaxWeightAction,
        *,
        cursor_policy: PromptWeightCursorPolicy,
    ) -> PromptWeightCommandResult[object]:
        """Execute one non-emphasis weight action through the command boundary."""

    def apply_exact_weight_result(
        self,
        result: PromptWeightCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one exact-weight command."""

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when one exists."""

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the active transient neutral-emphasis content range, if any."""

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the active transient neutral-emphasis owner, if any."""

    def clear_overlay_emphasis_session_for_exact_weight(self) -> None:
        """Clear overlay-owned emphasis state after overlay visibility changes."""

    def preserve_surface_scroll_position_for_exact_weight(
        self,
        action: Callable[[], None],
    ) -> None:
        """Run one token-weight action without moving the visible scroll position."""


class PromptExactWeightProjectionHost(Protocol):
    """Expose projection-owned exact edit and accent state to interactions."""

    def set_overlay_emphasis_accent_range(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Apply overlay-owned emphasis accent range to projection paint state."""

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start one projection-owned exact edit session."""

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update the active projection-owned exact edit buffer."""

    def clear_exact_weight_edit(self) -> None:
        """Clear the active projection-owned exact edit session."""

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning exact edit state."""

    def exact_weight_edit_active(self) -> bool:
        """Return whether exact edit mode is active."""

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the painted weight-text rect for one token."""


class PromptExactWeightController:
    """Own exact-weight overlay coordination while delegating visual state."""

    def __init__(
        self,
        host: PromptExactWeightHost,
        *,
        projection_host: PromptExactWeightProjectionHost | None,
    ) -> None:
        """Store collaborators for exact-weight command and projection coordination."""

        self._host = host
        self._projection_host = projection_host

    def apply_syntax_action(
        self,
        action: PromptSyntaxAction,
        *,
        emphasis_owner: PromptEmphasisAdjustmentOwner | None,
    ) -> None:
        """Apply one syntax action through the shared exact-weight route."""

        self._host.clear_autocomplete_for_exact_weight()
        if is_weight_syntax_action(action):
            self._apply_weight_action(action, emphasis_owner=emphasis_owner)
        self._host.set_focus_after_exact_weight_action()

    def apply_overlay_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Apply one overlay-owned syntax action through shared command owners."""

        self._host.clear_keyboard_emphasis_session_for_exact_weight()
        self.apply_syntax_action(
            action,
            emphasis_owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        )

    def apply_token_weight_step_intent(
        self,
        intent: PromptTokenWeightStepIntent,
    ) -> None:
        """Apply one overlay arrow-step intent through command owners."""

        delta = 0.05 if intent.control == "increase" else -0.05
        self._apply_overlay_token_weight_action(
            self._weight_adjust_action_for_token(intent.token, delta=delta)
        )

    def apply_token_weight_wheel_step_intent(
        self,
        intent: PromptTokenWeightWheelStepIntent,
    ) -> None:
        """Apply one wheel-step intent through command owners."""

        if intent.angle_delta_y == 0:
            return
        self._apply_overlay_token_weight_action(
            self._weight_adjust_action_for_token(
                intent.token,
                delta=0.05 if intent.angle_delta_y > 0 else -0.05,
            )
        )

    def handle_visible_token_range_changed(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Publish overlay-visible emphasis range to projection accent state."""

        if self._projection_host is None:
            return
        self._projection_host.set_overlay_emphasis_accent_range(outer_range)

    def handle_visible_token_content_range_changed(
        self,
        content_range: tuple[int, int] | None,
    ) -> None:
        """Clear overlay-owned emphasis state when overlay visibility changes."""

        session = self._host.emphasis_adjustment_session()
        if (
            session is None
            or session.owner is not PromptEmphasisAdjustmentOwner.OVERLAY
        ):
            return
        if (
            content_range is not None
            and session.content_start == content_range[0]
            and session.content_end == content_range[1]
        ):
            return
        transient_range = self._host.transient_neutral_emphasis_range()
        if (
            content_range is None
            and self.exact_weight_edit_active()
            and transient_range == (session.content_start, session.content_end)
            and self._host.transient_neutral_emphasis_owner()
            is PromptTransientNeutralEmphasisOwner.OVERLAY
        ):
            return
        self._host.clear_overlay_emphasis_session_for_exact_weight()

    def begin_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact edit mode for one editable weighted token."""

        if (
            token.value_text is None
            or token.content_start is None
            or token.content_end is None
        ):
            return
        self.start_exact_weight_edit(token)

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact edit mode through the projection-owned edit state."""

        if self._projection_host is None:
            return
        self._projection_host.start_exact_weight_edit(token)

    def cancel_exact_weight_edit(self) -> None:
        """Exit exact edit mode without mutating prompt text."""

        self.clear_exact_weight_edit()

    def finalize_exact_weight_edit(self) -> None:
        """Commit valid exact weight input or cancel invalid input."""

        token = self.exact_weight_edit_token()
        if token is None:
            return
        buffer_state = self._exact_edit_state_for_token(token)
        if buffer_state is None:
            self.cancel_exact_weight_edit()
            return
        buffer_text, _, _ = buffer_state
        weight = self._parsed_exact_weight(token, buffer_text)
        if weight is None:
            self.cancel_exact_weight_edit()
            return
        action = self._exact_weight_action_for_token(token, weight=weight)
        self.clear_exact_weight_edit()
        self._apply_exact_weight_commit_action(action)

    def update_exact_weight_caret(
        self,
        *,
        token: PromptProjectionToken,
        caret_index: int,
    ) -> None:
        """Move the active exact-weight caret for one token."""

        buffer_state = self._exact_edit_state_for_token(token)
        if buffer_state is None:
            return
        buffer_text, _, _ = buffer_state
        self.update_exact_weight_edit(
            buffer_text=buffer_text,
            caret_index=max(0, min(len(buffer_text), caret_index)),
            select_all=False,
        )

    def handle_exact_weight_key_press(self, event: QKeyEvent) -> bool:
        """Handle native exact-weight editing keys."""

        token = self.exact_weight_edit_token()
        if token is None:
            return False
        buffer_state = self._exact_edit_state_for_token(token)
        if buffer_state is None:
            return False
        buffer_text, caret_index, select_all = buffer_state
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.finalize_exact_weight_edit()
            return True
        if event.key() == Qt.Key.Key_Space and event.text() == " ":
            self.finalize_exact_weight_edit()
            return False
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_exact_weight_edit()
            return True
        if event.key() == Qt.Key.Key_Backspace:
            self._delete_from_exact_weight_buffer(
                buffer_text=buffer_text,
                caret_index=caret_index,
                select_all=select_all,
                backspace=True,
            )
            return True
        if event.key() == Qt.Key.Key_Delete:
            self._delete_from_exact_weight_buffer(
                buffer_text=buffer_text,
                caret_index=caret_index,
                select_all=select_all,
                backspace=False,
            )
            return True
        if event.key() == Qt.Key.Key_Left:
            self.update_exact_weight_edit(
                buffer_text=buffer_text,
                caret_index=max(0, caret_index - 1),
                select_all=False,
            )
            return True
        if event.key() == Qt.Key.Key_Right:
            self.update_exact_weight_edit(
                buffer_text=buffer_text,
                caret_index=min(len(buffer_text), caret_index + 1),
                select_all=False,
            )
            return True
        if event.key() == Qt.Key.Key_Home:
            self.update_exact_weight_edit(
                buffer_text=buffer_text,
                caret_index=0,
                select_all=False,
            )
            return True
        if event.key() == Qt.Key.Key_End:
            self.update_exact_weight_edit(
                buffer_text=buffer_text,
                caret_index=len(buffer_text),
                select_all=False,
            )
            return True
        if event.text() and event.text() in "-0123456789.":
            self._insert_exact_weight_text(
                text=event.text(),
                buffer_text=buffer_text,
                caret_index=caret_index,
                select_all=select_all,
            )
            return True
        return False

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update exact edit buffer state through the projection owner."""

        if self._projection_host is None:
            return
        self._projection_host.update_exact_weight_edit(
            buffer_text=buffer_text,
            caret_index=caret_index,
            select_all=select_all,
        )

    def clear_exact_weight_edit(self) -> None:
        """Cancel or finish exact edit mode through the projection owner."""

        if self._projection_host is None:
            return
        self._projection_host.clear_exact_weight_edit()

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the current projection-owned exact edit token."""

        if self._projection_host is None:
            return None
        return self._projection_host.exact_weight_edit_token()

    def exact_weight_edit_active(self) -> bool:
        """Return whether projection-owned exact edit mode is active."""

        return (
            self._projection_host is not None
            and self._projection_host.exact_weight_edit_active()
        )

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return projection-owned weight text geometry for exact edit caret math."""

        if self._projection_host is None:
            return None
        return self._projection_host.token_weight_text_rect(token)

    @staticmethod
    def _exact_edit_state_for_token(
        token: PromptProjectionToken,
    ) -> tuple[str, int, bool] | None:
        """Return projection-owned exact-edit buffer state for one token."""

        if token.editing_value_text is None:
            return None
        caret_index = (
            len(token.editing_value_text)
            if token.editing_caret_index is None
            else token.editing_caret_index
        )
        return (
            token.editing_value_text,
            caret_index,
            token.editing_select_all,
        )

    def _insert_exact_weight_text(
        self,
        *,
        text: str,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Insert one validated character into the active exact-weight buffer."""

        if select_all:
            next_buffer = text
            next_caret = len(text)
        else:
            next_buffer = buffer_text[:caret_index] + text + buffer_text[caret_index:]
            next_caret = caret_index + len(text)
        if not _EXACT_WEIGHT_EDIT_PATTERN.fullmatch(next_buffer):
            return
        self.update_exact_weight_edit(
            buffer_text=next_buffer,
            caret_index=next_caret,
            select_all=False,
        )

    def _delete_from_exact_weight_buffer(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
        backspace: bool,
    ) -> None:
        """Delete one character from the active exact-weight buffer."""

        if select_all:
            self.update_exact_weight_edit(
                buffer_text="",
                caret_index=0,
                select_all=False,
            )
            return
        if backspace:
            if caret_index == 0:
                return
            next_buffer = buffer_text[: caret_index - 1] + buffer_text[caret_index:]
            next_caret = caret_index - 1
        else:
            if caret_index >= len(buffer_text):
                return
            next_buffer = buffer_text[:caret_index] + buffer_text[caret_index + 1 :]
            next_caret = caret_index
        self.update_exact_weight_edit(
            buffer_text=next_buffer,
            caret_index=next_caret,
            select_all=False,
        )

    @staticmethod
    def _parsed_exact_weight(
        token: PromptProjectionToken,
        text: str,
    ) -> Decimal | None:
        """Parse and normalize one exact edit buffer into the committed weight."""

        if not text or text in {"-", ".", "-."}:
            return None
        try:
            weight = Decimal(text)
        except InvalidOperation:
            return None
        if (
            token.kind is not PromptProjectionTokenKind.LORA
            and weight < _MINIMUM_EXACT_WEIGHT
        ):
            weight = _MINIMUM_EXACT_WEIGHT
        return weight.quantize(Decimal("0.00"))

    @staticmethod
    def _exact_weight_action_for_token(
        token: PromptProjectionToken,
        *,
        weight: Decimal,
    ) -> PromptSyntaxWeightAction:
        """Return the exact-weight syntax action matching one edit token."""

        if token.synthetic:
            assert token.content_start is not None
            assert token.content_end is not None
            return PromptSetEmphasisWeightContentAction(
                content_start=token.content_start,
                content_end=token.content_end,
                weight=weight,
            )
        if token.kind is PromptProjectionTokenKind.LORA:
            return PromptSetLoraWeightAction(
                outer_start=token.source_start,
                outer_end=token.source_end,
                weight=weight,
            )
        return PromptSetEmphasisWeightAction(
            outer_start=token.source_start,
            outer_end=token.source_end,
            weight=weight,
        )

    @staticmethod
    def _weight_adjust_action_for_token(
        token: PromptProjectionToken,
        *,
        delta: float,
    ) -> PromptSyntaxWeightAction:
        """Return the correct weight-step action for one weighted token."""

        if token.kind is PromptProjectionTokenKind.WILDCARD:
            return PromptAdjustWildcardTagAction(
                outer_start=token.source_start,
                outer_end=token.source_end,
                current_display_tag=token.wildcard_display_tag or "",
                delta=1 if delta > 0 else -1,
            )
        if token.synthetic:
            assert token.content_start is not None
            assert token.content_end is not None
            return PromptAdjustEmphasisContentAction(
                content_start=token.content_start,
                content_end=token.content_end,
                delta=delta,
            )
        if token.kind is PromptProjectionTokenKind.LORA:
            return PromptAdjustLoraWeightAction(
                outer_start=token.source_start,
                outer_end=token.source_end,
                delta=delta,
            )
        return PromptAdjustEmphasisAction(
            outer_start=token.source_start,
            outer_end=token.source_end,
            delta=delta,
        )

    def _apply_overlay_token_weight_action(
        self,
        action: PromptSyntaxWeightAction,
    ) -> None:
        """Apply one overlay token-weight action while preserving surface scroll."""

        self._host.preserve_surface_scroll_position_for_exact_weight(
            lambda: self.apply_overlay_syntax_action(action)
        )

    def _apply_weight_action(
        self,
        action: PromptSyntaxWeightAction,
        *,
        emphasis_owner: PromptEmphasisAdjustmentOwner | None,
    ) -> None:
        """Execute one weight-shaped syntax action through its feature owner."""

        if is_emphasis_weight_action(action):
            self._host.apply_emphasis_weight_action_from_exact(
                action,
                owner=emphasis_owner,
                clear_autocomplete=False,
                restore_focus=False,
                cursor_policy="preserve_cursor",
            )
            return
        result = self._host.execute_exact_weight_action(
            action,
            cursor_policy="mutation_selection",
        )
        self._host.apply_exact_weight_result(result)

    def _apply_exact_weight_commit_action(
        self,
        action: PromptSyntaxWeightAction,
    ) -> None:
        """Commit one exact-weight edit with the caret after the edited token."""

        self._host.preserve_surface_scroll_position_for_exact_weight(
            lambda: self._apply_weight_action_after_mutation(action)
        )

    def _apply_weight_action_after_mutation(
        self,
        action: PromptSyntaxWeightAction,
    ) -> None:
        """Execute a finalized exact edit and place the caret after its token."""

        if is_emphasis_weight_action(action):
            self._host.apply_emphasis_weight_action_from_exact(
                action,
                owner=PromptEmphasisAdjustmentOwner.OVERLAY,
                clear_autocomplete=False,
                restore_focus=False,
                cursor_policy="after_mutation",
            )
            return
        result = self._host.execute_exact_weight_action(
            action,
            cursor_policy="after_mutation",
        )
        self._host.apply_exact_weight_result(result)


__all__ = [
    "PromptExactWeightController",
    "PromptExactWeightHost",
    "PromptExactWeightProjectionHost",
    "is_weight_syntax_action",
]
