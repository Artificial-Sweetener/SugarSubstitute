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

"""Tests for one-time implicit-parenthesis education presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.interactions.parenthesis_education_controller import (
    PromptParenthesisEducationController,
)
from tests.prompt_projection_test_helpers import ensure_qapp


@dataclass
class _EducationState:
    """Store one in-memory education preference for controller tests."""

    seen: bool = False
    mark_count: int = 0

    def has_seen_nested_parenthesis_tip(self) -> bool:
        """Return current seen state."""

        return self.seen

    def mark_nested_parenthesis_tip_seen(self) -> None:
        """Record and persist the seen transition."""

        self.seen = True
        self.mark_count += 1


def test_nested_parenthesis_tip_is_persisted_and_shown_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Teach explicit weighting once and include the exact nesting equivalent."""

    ensure_qapp()
    state = _EducationState()
    parent = QWidget()
    calls: list[dict[str, Any]] = []

    def record_tip(**kwargs: Any) -> object:
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(
        "substitute.presentation.editor.prompt_editor.interactions."
        "parenthesis_education_controller.TeachingTip.create",
        record_tip,
    )
    controller = PromptParenthesisEducationController(
        state=state,
        target=parent,
        parent=parent,
    )

    controller.handle_authored_nested_parentheses(3)
    controller.handle_authored_nested_parentheses(3)

    assert state.mark_count == 1
    assert len(calls) == 1
    assert ":1.331" in calls[0]["content"]
    parent.deleteLater()
