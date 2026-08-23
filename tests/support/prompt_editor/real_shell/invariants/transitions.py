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

"""Validate observable real-shell prompt-editor state transitions."""

from __future__ import annotations

from collections.abc import Callable

from tests.support.prompt_editor.real_shell.invariants.autocomplete import (
    dismissal_owner_violations,
)
from tests.support.prompt_editor.real_shell.invariants.geometry import (
    action_should_leave_caret_visible,
    transition_geometry_violations,
)
from tests.support.prompt_editor.real_shell.invariants.projection import (
    autocomplete_state_is_owned_or_visible,
)
from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot


def transition_violations(
    *,
    action_name: str,
    before: PromptEditorStateSnapshot,
    after: PromptEditorStateSnapshot,
    snapshot_violations: Callable[[PromptEditorStateSnapshot], tuple[str, ...]],
) -> tuple[str, ...]:
    """Return code-level invariant violations for one editor transition."""

    violations = list(snapshot_violations(after))
    if "\t" in after.source_text:
        violations.append("literal_tab_in_source")
    if _has_disallowed_control_character(after.source_text):
        violations.append("control_character_in_source")
    if action_should_leave_caret_visible(
        action_name,
        before=before,
        after=after,
    ) and not (
        after.projection_has_pending_update and after.projection_has_stale_geometry
    ):
        if not after.caret_rect_intersects_viewport:
            violations.append("caret_rect_outside_viewport_after_settle")
    violations.extend(
        transition_geometry_violations(
            action_name=action_name,
            before=before,
            after=after,
        )
    )
    if action_name == "space" and after.source_text == f"{before.source_text} ":
        if (
            after.projection_has_stale_geometry
            or after.projection_document_source_text != after.source_text
            or after.active_projection_source_text != after.source_text
        ):
            violations.append("space_left_stale_projection_after_source_insert")
    if action_name in {
        "escape",
        "click_away",
        "caret",
        "selection",
        "canvas",
        "workflow",
    }:
        if autocomplete_state_is_owned_or_visible(after):
            violations.append(f"{action_name}_left_autocomplete_active")
        if before.autocomplete_preview_active and not after.autocomplete_preview_active:
            violations.extend(
                dismissal_owner_violations(
                    before=before,
                    after=after,
                    action_name=action_name,
                )
            )
    if action_name == "tab" and after.source_text == f"{before.source_text}\t":
        violations.append("tab_inserted_literal_tab")
    if action_name in {"backspace", "delete"}:
        if after.projection_has_pending_update and after.projection_has_stale_geometry:
            violations.append(f"{action_name}_left_stale_pending_projection")
    return tuple(dict.fromkeys(violations))


def _has_disallowed_control_character(text: str) -> bool:
    """Return whether prompt source contains key-event control characters."""

    return any(ord(character) < 32 and character != "\n" for character in text)
