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

"""Resolve authoritative mounted owners for prompt-editor test observation."""

from __future__ import annotations

from typing import Any, cast


def prompt_runtime(editor: object) -> Any:
    """Return the mounted runtime or reject an invalid test target."""

    runtime = getattr(editor, "_runtime", None)
    if runtime is None:
        raise RuntimeError("Prompt editor test target has no mounted runtime.")
    return runtime


def autocomplete_panel(editor: object) -> Any | None:
    """Return the autocomplete owner's current panel."""

    return prompt_runtime(editor).core.autocomplete.autocomplete.panel


def segment_overlay(editor: object) -> Any | None:
    """Return the interaction owner's current reorder overlay."""

    return prompt_runtime(editor).core.syntax.interaction_controller.segment_overlay


def token_weight_controls(editor: object) -> Any:
    """Return the syntax runtime's mounted token-weight controls."""

    return prompt_runtime(editor).core.syntax.token_weight_controls


def lora_picker_presenter(editor: object) -> Any:
    """Return the host menu runtime's LoRA picker presenter."""

    return prompt_runtime(editor).host.menu.lora_picker


def projection_surface(editor: object) -> Any:
    """Return the mounted source-projection surface."""

    return cast(Any, prompt_runtime(editor).projection.surface)


def apply_reorder_autoscroll_step(owner: object) -> None:
    """Deliver one deterministic timer tick to the autoscroll owner."""

    cast(Any, owner)._apply_step()  # noqa: SLF001


def set_context_menu_insert_state(
    editor: object,
    *,
    insert_position: int | None,
    should_replace_selection: bool | None = None,
) -> None:
    """Prepare context-menu insertion state through its authoritative shell owner."""

    prompt_runtime(editor).host.menu.shell.set_context_insert_state(
        insert_position=insert_position,
        should_replace_selection=should_replace_selection,
    )


def set_context_menu_selection_state(
    editor: object,
    *,
    had_selection: bool | None,
    selection_snapshot: tuple[int, int, str] | None,
) -> None:
    """Prepare captured menu selection state through its mounted owners."""

    runtime = prompt_runtime(editor)
    selected_text = selection_snapshot[2] if selection_snapshot is not None else ""
    runtime.host.menu.prompt_requests.prepare_prompt_menu_selection(
        selected_text=selected_text,
        selection_snapshot=selection_snapshot if had_selection else None,
        reason="test_context_menu_selection_state",
    )
    runtime.host.menu.shell.set_selection_press_state(
        had_selection=had_selection,
        selection_snapshot=selection_snapshot,
    )


__all__ = [
    "apply_reorder_autoscroll_step",
    "autocomplete_panel",
    "lora_picker_presenter",
    "projection_surface",
    "prompt_runtime",
    "segment_overlay",
    "set_context_menu_insert_state",
    "set_context_menu_selection_state",
    "token_weight_controls",
]
