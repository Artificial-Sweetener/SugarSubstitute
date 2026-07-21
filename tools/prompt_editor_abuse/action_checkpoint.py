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

"""Validate operation-specific prompt-editor owner state after dispatch."""

from __future__ import annotations

from typing import Any, cast

from .models import PromptAbuseAction


def capture_action_checkpoint(
    editor: object,
    action: PromptAbuseAction,
) -> tuple[bool, str | None]:
    """Return whether the action reached its operation-specific owner state."""

    prompt_editor = cast(Any, editor)
    mismatches: list[str] = []
    if action.kind == "display_mode":
        actual = "rich" if prompt_editor.richPromptRenderingEnabled() else "raw"
        _append_mismatch(mismatches, "display_mode", actual, action.value)
    if action.kind == "search_highlights":
        session = prompt_editor._surface._session
        expected_ranges = action.source_ranges if action.value == "set" else ()
        expected_index = action.active_index if action.value == "set" else None
        actual_search_state = (
            tuple(session.search_match_ranges),
            session.active_search_match_index,
        )
        _append_mismatch(
            mismatches,
            "search_highlights",
            actual_search_state,
            (expected_ranges, expected_index),
        )
    if action.expected_scene_titles is not None:
        actual_scene_titles = tuple(
            token.display_text
            for token in prompt_editor._surface.projection_document().tokens
            if token.kind.value == "scene"
        )
        _append_mismatch(
            mismatches,
            "scene_titles",
            actual_scene_titles,
            action.expected_scene_titles,
        )
    if action.expected_diagnostics is not None:
        actual_diagnostics = tuple(
            (item.kind.value, item.source_start, item.source_end)
            for item in prompt_editor._diagnostics_feature_controller.snapshot.diagnostics
        )
        _append_mismatch(
            mismatches,
            "diagnostics",
            actual_diagnostics,
            action.expected_diagnostics,
        )
    if action.expected_token_kinds is not None:
        actual_token_kinds = tuple(
            token.kind.value
            for token in prompt_editor._surface.projection_document().tokens
        )
        _append_mismatch(
            mismatches,
            "token_kinds",
            actual_token_kinds,
            action.expected_token_kinds,
        )
    if action.expected_reorder_chip_texts is not None:
        overlay = prompt_editor._segment_overlay
        actual_chip_texts = (
            ()
            if overlay is None
            else tuple(
                overlay.pointer_region(segment_index).drag_proxy_text()
                for segment_index in sorted(overlay.pointer_region_rects())
            )
        )
        _append_mismatch(
            mismatches,
            "reorder_chip_texts",
            actual_chip_texts,
            action.expected_reorder_chip_texts,
        )
    return not mismatches, ";".join(mismatches) or None


def _match(name: str, actual: object, expected: object) -> tuple[bool, str | None]:
    """Return one compact exact-owner comparison result."""

    if actual == expected:
        return True, None
    return False, f"{name}:actual={actual!r}:expected={expected!r}"


def _append_mismatch(
    mismatches: list[str],
    name: str,
    actual: object,
    expected: object,
) -> None:
    """Append one compact mismatch when owner state differs."""

    exact, mismatch = _match(name, actual, expected)
    if not exact and mismatch is not None:
        mismatches.append(mismatch)


__all__ = ["capture_action_checkpoint"]
