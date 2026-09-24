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

"""Expose the prompt editor's public emphasis projection API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptWeightControlIdentity,
)

from .projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)

if TYPE_CHECKING:
    from .runtime_mount import PromptEditorRuntimeMount


class PromptEditorEmphasisFacade:
    """Adapt the stable editor host contract to projection emphasis ownership."""

    _runtime: PromptEditorRuntimeMount

    def pulse_emphasis_feedback(
        self,
        *,
        outer_start: int,
        outer_end: int,
    ) -> None:
        """Publish one bounded emphasis-decoration feedback pulse."""

        self._runtime.projection.surface.emphasis.pulse_feedback(
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
        """Store one active emphasis-adjustment session."""

        self._runtime.projection.surface.emphasis.set_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear the active emphasis-adjustment session."""

        self._runtime.projection.surface.emphasis.clear_adjustment_session()

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session."""

        return self._runtime.projection.surface.emphasis.adjustment_session()

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range."""

        return self._runtime.projection.surface.emphasis.adjustment_session_range()

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active emphasis-adjustment session owns one range."""

        return (
            self._runtime.projection.surface.emphasis.adjustment_session_matches_range(
                content_start=content_start,
                content_end=content_end,
            )
        )

    def prompt_weight_wheel_identity(
        self,
        token: PromptProjectionToken,
    ) -> PromptWeightControlIdentity:
        """Return stable wheel ownership identity for one prompt weight token."""

        return self._runtime.projection.surface.emphasis.wheel_identity(token)

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Project a temporary neutral emphasis shell over plain content."""

        self._runtime.projection.surface.emphasis.show_transient_neutral(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear the temporary neutral emphasis shell."""

        self._runtime.projection.surface.emphasis.clear_transient_neutral()

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Clear transient neutral emphasis only when overlay interaction owns it."""

        self._runtime.projection.surface.emphasis.clear_overlay_owned_transient_neutral()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the range owned by the temporary neutral emphasis shell."""

        return self._runtime.projection.surface.emphasis.transient_neutral_range()

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the temporary neutral emphasis shell."""

        return self._runtime.projection.surface.emphasis.transient_neutral_owner()

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at one projected emphasis-content boundary."""

        return self._runtime.projection.surface.emphasis.set_caret_to_content_boundary(
            content_start=content_start,
            content_end=content_end,
            prefer_end=prefer_end,
        )


__all__ = ["PromptEditorEmphasisFacade"]
