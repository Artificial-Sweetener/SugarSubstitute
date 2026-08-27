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

"""Verify atomic publication by the focused prompt-layout state owner."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.presentation.editor.prompt_editor.layout.contracts import (
    PromptLayoutDamage,
    PromptLayoutOutcome,
    PromptLayoutOutput,
    PromptLayoutReason,
)
from substitute.presentation.editor.prompt_editor.layout.state import PromptLayoutState


def _output_reference() -> PromptLayoutOutput:
    """Return an opaque typed reference for state-publication tests."""

    return cast(PromptLayoutOutput, object())


def _damage() -> PromptLayoutDamage:
    """Return one complete bounded damage value."""

    return PromptLayoutDamage(
        content_height_changed=False,
        content_height_delta=0.0,
        first_reflowed_line_index=0,
        reflowed_line_count=1,
        upstream_line_count=0,
    )


def test_layout_state_atomically_publishes_complete_engine_output() -> None:
    """Adopt the output and damage from one complete applied outcome."""

    initial = _output_reference()
    published = _output_reference()
    damage = _damage()
    state = PromptLayoutState(initial)

    returned_damage = state.publish(
        PromptLayoutOutcome.applied(
            reason=PromptLayoutReason.SAME_LINE_EDIT,
            output=published,
            damage=damage,
        )
    )

    assert state.current is published
    assert returned_damage is damage


def test_layout_state_rejects_incomplete_publication_without_mutation() -> None:
    """Keep the current output unchanged when an engine did not apply."""

    initial = _output_reference()
    state = PromptLayoutState(initial)

    with pytest.raises(ValueError, match="complete applied outcomes"):
        state.publish(
            PromptLayoutOutcome.deferred(PromptLayoutReason.WORD_WRAP_BOUNDARY)
        )

    assert state.current is initial
