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

"""Verify pure stable-space geometry transition diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from tests.support.prompt_editor.real_shell.invariants.geometry import (
    transition_geometry_violations,
)
from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot


@dataclass(frozen=True, slots=True)
class _GeometryTransitionSnapshot:
    """Supply only the immutable facts required by geometry transitions."""

    source_text: str
    projection_has_stale_geometry: bool
    layout_line_count: int
    layout_content_width: float
    layout_content_height: float
    geometries: dict[str, tuple[int, int, int, int] | None]
    visible_layout_rows: tuple[object, ...] = ()
    visible_text_fragments: tuple[object, ...] = ()
    scroll_values: dict[str, int] | None = None


def test_stable_space_geometry_shift_is_reported() -> None:
    """Detect chrome movement when a stable space edit preserves layout."""

    before = _GeometryTransitionSnapshot(
        source_text="alphabeta",
        projection_has_stale_geometry=False,
        layout_line_count=2,
        layout_content_width=240.0,
        layout_content_height=32.0,
        geometries={
            "editor": (10, 8, 360, 120),
            "viewport": (0, 0, 347, 114),
        },
    )
    stable_after = replace(before, source_text="alpha beta")
    shifted_after = replace(
        stable_after,
        geometries={
            **before.geometries,
            "editor": (10, 8, 360, 122),
            "viewport": (0, 0, 347, 116),
        },
    )

    stable_violations = transition_geometry_violations(
        action_name="space",
        before=cast(PromptEditorStateSnapshot, before),
        after=cast(PromptEditorStateSnapshot, stable_after),
    )
    shifted_violations = transition_geometry_violations(
        action_name="space",
        before=cast(PromptEditorStateSnapshot, before),
        after=cast(PromptEditorStateSnapshot, shifted_after),
    )

    assert not any(
        violation.startswith("stable_single_character_geometry_shift")
        for violation in stable_violations
    )
    assert any(
        violation.startswith("stable_single_character_geometry_shift")
        for violation in shifted_violations
    )
