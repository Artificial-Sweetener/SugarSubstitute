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

"""Present one-time education for authored implicit parenthesis nesting."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from qfluentwidgets import TeachingTip, TeachingTipTailPosition  # type: ignore[import-untyped]

from substitute.application.ports.prompt_parenthesis_education_state import (
    PromptParenthesisEducationState,
)
from substitute.domain.prompt.emphasis_semantics import (
    format_generated_emphasis_weight,
    implicit_emphasis_weight,
)


class PromptParenthesisEducationController(QObject):
    """Own the persisted, non-modal nested-parenthesis teaching response."""

    def __init__(
        self,
        *,
        state: PromptParenthesisEducationState,
        target: QWidget,
        parent: QWidget,
    ) -> None:
        """Bind education persistence and its visual anchor."""

        super().__init__(parent)
        self._state = state
        self._target = target
        self._parent = parent
        self._tip: TeachingTip | None = None

    def handle_authored_nested_parentheses(self, nesting_depth: int) -> None:
        """Show the teaching tip once for authored nested implicit emphasis."""

        if nesting_depth < 2 or self._state.has_seen_nested_parenthesis_tip():
            return
        self._state.mark_nested_parenthesis_tip_seen()
        explicit_weight = format_generated_emphasis_weight(
            implicit_emphasis_weight(nesting_depth)
        )
        self._tip = TeachingTip.create(
            target=self._target,
            title="Use explicit prompt emphasis",
            content=(
                f"Nested parentheses were converted to :{explicit_weight}. "
                "Explicit weights are stable across diffusion models."
            ),
            isClosable=True,
            duration=8000,
            tailPosition=TeachingTipTailPosition.TOP,
            parent=self._parent,
            isDeleteOnClose=False,
        )


__all__ = ["PromptParenthesisEducationController"]
