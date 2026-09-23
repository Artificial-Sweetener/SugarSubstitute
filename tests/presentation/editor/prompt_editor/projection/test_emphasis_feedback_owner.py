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

"""Test projection emphasis feedback ownership."""

from __future__ import annotations

from PySide6.QtCore import QObject

from substitute.presentation.editor.prompt_editor.projection.emphasis_feedback_owner import (
    PromptProjectionEmphasisFeedbackOwner,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


def test_emphasis_feedback_owner_deduplicates_ranges_and_clears_pulse() -> None:
    """Interaction accents should stay ordered and pulses should expire independently."""

    ensure_qapp()
    parent = QObject()
    publications: list[None] = []
    owner = PromptProjectionEmphasisFeedbackOwner(
        is_projected=lambda: True,
        apply_paint_state=lambda: publications.append(None),
        parent=parent,
    )

    owner.set_overlay_range((1, 5))
    owner.set_wheel_intent_range((1, 5))
    owner.pulse((8, 12))

    assert owner.accent_ranges() == ((1, 5), (8, 12))
    assert len(publications) == 3

    owner.clear_pulse()

    assert owner.accent_ranges() == ((1, 5),)
    assert len(publications) == 4


def test_emphasis_feedback_owner_defers_publication_outside_projected_mode() -> None:
    """Raw-mode state changes should remain passive until projection is visible."""

    ensure_qapp()
    parent = QObject()
    publications: list[None] = []
    owner = PromptProjectionEmphasisFeedbackOwner(
        is_projected=lambda: False,
        apply_paint_state=lambda: publications.append(None),
        parent=parent,
    )

    owner.set_overlay_range((2, 6))
    owner.pulse((7, 9))
    owner.clear_pulse()

    assert owner.accent_ranges() == ((2, 6),)
    assert publications == []
