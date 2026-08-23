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

"""Verify pure transient-overlay diagnostic geometry."""

from __future__ import annotations

from dataclasses import dataclass

from tests.support.prompt_editor.real_shell.invariants.transient_overlay import (
    deletion_overerase_violations,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorVisibleTextFragment,
)


@dataclass(frozen=True, slots=True)
class _DeletionOverlaySnapshot:
    """Supply only the geometry required by the deletion-overerase invariant."""

    transient_deletion_overlay_source_range: tuple[int, int] | None
    transient_deletion_overlay_valid: bool
    transient_deletion_overlay_erase_rects: tuple[
        tuple[float, float, float, float], ...
    ]
    visible_text_fragments: tuple[PromptEditorVisibleTextFragment, ...]


def test_deletion_overerase_reports_left_and_neighbor_damage() -> None:
    """Report a deletion erase band that overlaps unrelated visible text."""

    snapshot = _DeletionOverlaySnapshot(
        transient_deletion_overlay_source_range=(5, 6),
        transient_deletion_overlay_valid=True,
        transient_deletion_overlay_erase_rects=((0.0, 0.0, 50.0, 16.0),),
        visible_text_fragments=(
            _fragment(0, 0, 5, "alpha", (0.0, 0.0, 38.0, 16.0)),
            _fragment(1, 5, 6, "b", (40.0, 0.0, 8.0, 16.0)),
        ),
    )

    violations = deletion_overerase_violations(snapshot)

    assert any(
        violation.startswith("transient_deletion_overerase_left")
        for violation in violations
    )
    assert "transient_deletion_overerase_neighbor:0" in violations


def _fragment(
    fragment_index: int,
    source_start: int,
    source_end: int,
    text: str,
    rect: tuple[float, float, float, float],
) -> PromptEditorVisibleTextFragment:
    """Build one visible text fragment for a serialized geometry contract."""

    return PromptEditorVisibleTextFragment(
        fragment_index=fragment_index,
        source_start=source_start,
        source_end=source_end,
        document_rect=rect,
        viewport_rect=rect,
        document_baseline=12.0,
        viewport_baseline=12.0,
        text=text,
    )
