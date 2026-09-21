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

"""Own projected emphasis interaction state, feedback, and caret placement."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptWeightControlIdentity,
)

from .emphasis_feedback_owner import PromptProjectionEmphasisFeedbackOwner
from .session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptProjectionSession,
    PromptTransientNeutralEmphasisOwner,
)


class PromptProjectionEmphasisOwner(QObject):
    """Coordinate every projection effect of emphasis interaction state."""

    def __init__(
        self,
        *,
        session: PromptProjectionSession,
        is_projected: Callable[[], bool],
        tokens: Callable[[], Sequence[PromptProjectionToken]],
        apply_session_paint_state: Callable[[], bool],
        apply_accent_paint_state: Callable[[], None],
        rebuild_projection: Callable[[], None],
        publish_caret: Callable[
            [PromptProjectionCaretState, PromptProjectionCaretState], None
        ],
        parent: QObject,
    ) -> None:
        """Bind emphasis state to projection publication and caret ownership."""

        super().__init__(parent)
        self._session = session
        self._is_projected = is_projected
        self._tokens = tokens
        self._apply_session_paint_state = apply_session_paint_state
        self._rebuild_projection = rebuild_projection
        self._publish_caret = publish_caret
        self._feedback = PromptProjectionEmphasisFeedbackOwner(
            is_projected=is_projected,
            apply_paint_state=apply_accent_paint_state,
            parent=self,
        )

    def set_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Store the active emphasis adjustment session."""

        self._session.set_emphasis_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_adjustment_session(self) -> None:
        """Clear the active emphasis adjustment session."""

        self._session.clear_emphasis_adjustment_session()

    def adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis adjustment session."""

        return self._session.emphasis_adjustment_session()

    def adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis adjustment content range."""

        return self._session.emphasis_adjustment_session_range()

    def adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active adjustment session owns one range."""

        return self._session.emphasis_adjustment_session_matches_range(
            content_start=content_start,
            content_end=content_end,
        )

    def wheel_identity(
        self,
        token: PromptProjectionToken,
    ) -> PromptWeightControlIdentity:
        """Return stable wheel ownership identity for one emphasis token."""

        return self._session.prompt_weight_wheel_identity(token)

    def set_overlay_accent_range(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Publish the accent range owned by visible weight controls."""

        self._feedback.set_overlay_range(outer_range)

    def set_wheel_intent_accent_range(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Publish the accent range owned by wheel-intent dwell."""

        self._feedback.set_wheel_intent_range(outer_range)

    def pulse_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Accent one emphasis shell for the bounded feedback interval."""

        self._feedback.pulse((outer_start, outer_end))

    def accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return unique accent ranges in interaction-priority order."""

        return self._feedback.accent_ranges()

    def show_transient_neutral(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Project a temporary neutral emphasis shell over plain source content."""

        self._session.set_transient_neutral_emphasis(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )
        if self._is_projected() and not self._apply_session_paint_state():
            self._rebuild_projection()

    def clear_transient_neutral(self) -> None:
        """Remove the temporary neutral emphasis shell from projection state."""

        if self._session.transient_neutral_emphasis is None:
            return
        self._session.clear_transient_neutral_emphasis()
        self._rebuild_if_projected()

    def clear_overlay_owned_transient_neutral(self) -> None:
        """Remove the temporary neutral shell only when overlay interaction owns it."""

        if (
            self._session.transient_neutral_emphasis_owner()
            is not PromptTransientNeutralEmphasisOwner.OVERLAY
        ):
            return
        self._session.clear_overlay_owned_transient_neutral_emphasis()
        self._rebuild_if_projected()

    def transient_neutral_range(self) -> tuple[int, int] | None:
        """Return the content range owned by the temporary neutral shell."""

        return self._session.transient_neutral_emphasis_range()

    def transient_neutral_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the temporary neutral shell."""

        return self._session.transient_neutral_emphasis_owner()

    def set_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at one projected emphasis-content boundary."""

        token = next(
            (
                candidate
                for candidate in self._tokens()
                if candidate.kind is PromptProjectionTokenKind.EMPHASIS
                and candidate.supports_text_content_navigation
                and candidate.content_range == (content_start, content_end)
            ),
            None,
        )
        if token is None:
            return False
        source_position = content_end if prefer_end else content_start
        boundary_state = PromptProjectionCaretState(
            source_position=source_position,
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
            token_id=token.token_id,
            token_slot=content_end - content_start if prefer_end else 0,
        )
        self._publish_caret(boundary_state, boundary_state)
        return True

    def _rebuild_if_projected(self) -> None:
        """Rebuild the projection when decorated rendering is active."""

        if self._is_projected():
            self._rebuild_projection()


__all__ = ["PromptProjectionEmphasisOwner"]
