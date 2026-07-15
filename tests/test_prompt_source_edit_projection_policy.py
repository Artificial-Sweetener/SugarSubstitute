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

"""Tests for source-edit projection deferral policy."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_policy import (
    PromptSourceEditProjectionPolicy,
)


@pytest.mark.parametrize(
    ("replacement_text", "reason"),
    (
        ("", "deletion_requires_immediate_projection"),
        (" ", "whitespace_requires_immediate_projection"),
        ("\n", "whitespace_requires_immediate_projection"),
    ),
)
def test_source_edit_projection_policy_forces_immediate_boundaries(
    replacement_text: str,
    reason: str,
) -> None:
    """Deletion and whitespace edits are immediate projection boundaries."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text=replacement_text,
        autocomplete_preview_active=False,
        insertion_overlay_can_defer=True,
    )

    assert not decision.can_defer_projection
    assert decision.deferral_reason == reason


def test_source_edit_projection_policy_forces_preview_active_edits_immediate() -> None:
    """Edits cannot defer while autocomplete preview is active."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text="x",
        autocomplete_preview_active=True,
        insertion_overlay_can_defer=True,
    )

    assert not decision.can_defer_projection
    assert decision.deferral_reason == "autocomplete_preview_active"


def test_source_edit_projection_policy_rejects_missing_insertion_overlay() -> None:
    """Text insertions that cannot paint as overlays require full layout."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text="x",
        autocomplete_preview_active=False,
        insertion_overlay_can_defer=False,
    )

    assert not decision.can_defer_projection
    assert decision.deferral_reason == "safe_typing_requires_layout"


def test_source_edit_projection_policy_allows_safe_plain_insert() -> None:
    """Plain non-whitespace insertions can defer when overlays can represent them."""

    decision = PromptSourceEditProjectionPolicy().decide(
        can_defer_projection=True,
        deferral_reason="safe_typing",
        replacement_text="x",
        autocomplete_preview_active=False,
        insertion_overlay_can_defer=True,
    )

    assert decision.can_defer_projection
    assert decision.deferral_reason == "safe_typing"
