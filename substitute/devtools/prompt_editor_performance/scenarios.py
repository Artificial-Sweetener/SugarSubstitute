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

"""Prompt editor performance scenario models and deterministic corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from substitute.domain.prompt.features import PromptEditorFeature


ScenarioOperation = Literal[
    "type",
    "backspace",
    "delete",
    "enter",
    "autocomplete",
    "ghost_text",
    "cursor_move",
    "selection_change",
    "paste",
    "paste_import",
    "projection_paint_cache",
    "diagnostic_cache",
    "fill_band_cache",
    "scroll",
    "resize",
    "hover",
    "focus",
    "context_menu",
    "reorder_drag",
    "reorder_alt_drag",
    "reorder_alt_arrow",
]
AutocompleteGatewayKind = Literal["empty", "static"]
WildcardGatewayKind = Literal["empty", "static"]
LoraCatalogKind = Literal["empty", "static"]
ReorderDragMode = Literal["same_target", "target_change"]
ReorderArrowKey = Literal["left", "right", "up", "down"]

ALL_PROMPT_EDITOR_FEATURES: tuple[PromptEditorFeature, ...] = tuple(PromptEditorFeature)
DANBOORU_IMPORT_URL = "https://danbooru.donmai.us/posts/123456"


@dataclass(frozen=True, slots=True)
class Scenario:
    """Describe one prompt editor performance scenario independent from Qt."""

    name: str
    initial_text: str
    typed_text: str = ""
    autocomplete_gateway: AutocompleteGatewayKind = "empty"
    wildcard_gateway: WildcardGatewayKind = "empty"
    lora_catalog: LoraCatalogKind = "empty"
    spellcheck_enabled: bool = False
    danbooru_import_enabled: bool = False
    danbooru_wiki_enabled: bool = False
    segment_presets_enabled: bool = False
    scheduled_lora_context_enabled: bool = False
    operation: ScenarioOperation = "type"
    cursor_position: int | None = None
    selection_range: tuple[int, int] | None = None
    operation_count: int | None = None
    clipboard_text: str = ""
    reorder_drag_mode: ReorderDragMode = "target_change"
    reorder_keys: tuple[ReorderArrowKey, ...] = ()
    editor_size: tuple[int, int] = (720, 180)


def scenarios(typed_text: str) -> tuple[Scenario, ...]:
    """Return the standard prompt editor performance scenarios."""

    comma_prompt = "masterpiece, best quality, detailed face, soft light, "
    long_prompt = (
        "masterpiece, best quality, detailed face, soft light, background, cinematic, "
    )
    mid_prompt_prefix = comma_prompt * 20 + "1girl blue "
    mid_prompt_prefix_5k = long_prompt * 70 + "1girl blue "
    mid_prompt_prefix_10k = long_prompt * 140 + "1girl blue "
    edit_prompt = comma_prompt * 20 + "blue hair"
    edit_prompt_5k = long_prompt * 70 + "blue hair"
    cursor_prompt = comma_prompt * 20 + "alpha beta gamma delta"
    cursor_prompt_5k = long_prompt * 70 + "alpha beta gamma delta"
    rich_paste_text = (
        "blue \\(butterfly\\) bow, red (gem:1.10), <lora:detail_booster:0.8>"
    )
    newline_prompt = comma_prompt * 20 + "alpha\nbeta"
    newline_prompt_5k = long_prompt * 70 + "alpha\nbeta"
    newline_offset = len(comma_prompt * 20 + "alpha")
    newline_offset_5k = len(long_prompt * 70 + "alpha")
    reorder_prompt = "alpha, beta, gamma, delta, epsilon"
    reorder_wrapped_prompt = (
        "alpha detail token, beta long descriptive token, gamma textured token, "
        "delta cinematic token, epsilon final token"
    )
    reorder_linebreak_prompt = "alpha,\n\nbeta,\n\ngamma, delta"
    reorder_linebreak_cursor = reorder_linebreak_prompt.index("gamma") + 1
    wildcard_prefix = "{li"
    lora_prefix = "<lora:det"
    projection_middle_prompt = "(cat:1.05), alpha beta gamma"
    projection_middle_offset = projection_middle_prompt.index(" beta")
    return (
        Scenario("plain-prompt-type", "", typed_text),
        Scenario("250-prompt-type", comma_prompt * 5, typed_text),
        Scenario("1k-prompt-type", comma_prompt * 20, typed_text),
        Scenario("5k-large-prompt-type", long_prompt * 70, typed_text),
        Scenario("10k-large-prompt-type", long_prompt * 140, typed_text),
        Scenario(
            "emphasis-heavy-type",
            "(masterpiece:1.2), (best quality:1.1), " * 40,
            typed_text,
        ),
        Scenario(
            "wildcard-heavy-type",
            "{artist/style}, {lighting/day}, " * 40,
            typed_text,
            wildcard_gateway="static",
        ),
        Scenario(
            "lora-heavy-type",
            "<lora:detail_booster:0.8>, portrait, " * 40,
            typed_text,
            lora_catalog="static",
        ),
        Scenario(
            "autocomplete-static-tags",
            comma_prompt * 20,
            "ha",
            autocomplete_gateway="static",
            operation="autocomplete",
        ),
        Scenario(
            "ghost-text-active",
            comma_prompt * 20,
            "ha",
            autocomplete_gateway="static",
            operation="ghost_text",
        ),
        Scenario(
            "wildcard-autocomplete",
            comma_prompt * 10 + wildcard_prefix,
            "g",
            wildcard_gateway="static",
            operation="autocomplete",
            cursor_position=len(comma_prompt * 10 + wildcard_prefix),
        ),
        Scenario(
            "lora-autocomplete",
            comma_prompt * 10 + lora_prefix,
            "ail",
            lora_catalog="static",
            operation="autocomplete",
            cursor_position=len(comma_prompt * 10 + lora_prefix),
        ),
        Scenario(
            "diagnostics-enabled",
            "mispelled prompt segment",
            operation="context_menu",
            spellcheck_enabled=True,
            cursor_position=2,
        ),
        Scenario(
            "context-menu-diagnostics-actions",
            "mispelled prompt segment",
            operation="context_menu",
            spellcheck_enabled=True,
            cursor_position=2,
        ),
        Scenario(
            "context-menu-lora-actions",
            "<lora:detail_booster:0.8>, portrait",
            operation="context_menu",
            lora_catalog="static",
            scheduled_lora_context_enabled=True,
            cursor_position=2,
        ),
        Scenario(
            "context-menu-wildcard-actions",
            "{missing}, portrait",
            operation="context_menu",
            wildcard_gateway="static",
            cursor_position=2,
        ),
        Scenario(
            "context-menu-danbooru-actions",
            "blue_hair, portrait",
            operation="context_menu",
            danbooru_wiki_enabled=True,
            selection_range=(0, len("blue_hair")),
        ),
        Scenario(
            "context-menu-segment-presets",
            "blue hair, portrait",
            operation="context_menu",
            segment_presets_enabled=True,
            selection_range=(0, len("blue hair")),
        ),
        Scenario(
            "context-menu-open",
            "mispelled prompt segment, <lora:detail_booster:0.8>",
            operation="context_menu",
            spellcheck_enabled=True,
            lora_catalog="static",
            cursor_position=2,
        ),
        Scenario(
            "scroll-large-prompt",
            "\n".join(f"line {index}, detailed prompt segment" for index in range(90)),
            operation="scroll",
            operation_count=12,
        ),
        Scenario(
            "resize-large-prompt",
            long_prompt * 70,
            operation="resize",
            operation_count=8,
        ),
        Scenario(
            "hover-large-prompt",
            "\n".join(
                f"line {index}, <lora:detail_booster:0.8>" for index in range(70)
            ),
            operation="hover",
            operation_count=10,
            lora_catalog="static",
            scheduled_lora_context_enabled=True,
        ),
        Scenario(
            "focus-cycle",
            "<lora:detail_booster:0.8>, blue hair, portrait",
            operation="focus",
            operation_count=4,
            lora_catalog="static",
            scheduled_lora_context_enabled=True,
        ),
        Scenario(
            "reorder-drag-active",
            reorder_prompt,
            operation="reorder_drag",
            operation_count=8,
        ),
        Scenario(
            "alt-drag-same-target",
            reorder_prompt,
            operation="reorder_alt_drag",
            operation_count=8,
            reorder_drag_mode="same_target",
        ),
        Scenario(
            "alt-drag-target-change",
            reorder_prompt,
            operation="reorder_alt_drag",
            operation_count=8,
            reorder_drag_mode="target_change",
        ),
        Scenario(
            "alt-drag-wrapped-target-change",
            reorder_wrapped_prompt,
            operation="reorder_alt_drag",
            operation_count=8,
            reorder_drag_mode="target_change",
            editor_size=(360, 240),
        ),
        Scenario(
            "alt-drag-linebreak-target-change",
            reorder_linebreak_prompt,
            operation="reorder_alt_drag",
            operation_count=6,
            reorder_drag_mode="target_change",
            editor_size=(430, 280),
        ),
        Scenario(
            "alt-arrow-horizontal",
            reorder_prompt,
            operation="reorder_alt_arrow",
            cursor_position=reorder_prompt.index("gamma") + 1,
            reorder_keys=("left", "right", "left", "right"),
        ),
        Scenario(
            "alt-arrow-wrapped",
            reorder_wrapped_prompt,
            operation="reorder_alt_arrow",
            cursor_position=reorder_wrapped_prompt.index("gamma") + 1,
            reorder_keys=("left", "right", "left", "right"),
            editor_size=(360, 240),
        ),
        Scenario(
            "alt-arrow-linebreak-up",
            reorder_linebreak_prompt,
            operation="reorder_alt_arrow",
            cursor_position=reorder_linebreak_cursor,
            reorder_keys=("up", "down", "up", "down"),
            editor_size=(430, 280),
        ),
        Scenario(
            "1k-cursor-move",
            cursor_prompt,
            operation="cursor_move",
            cursor_position=len(cursor_prompt) - 6,
            operation_count=12,
        ),
        Scenario(
            "5k-cursor-move",
            cursor_prompt_5k,
            operation="cursor_move",
            cursor_position=len(cursor_prompt_5k) - 6,
            operation_count=12,
        ),
        Scenario(
            "1k-selection-change",
            cursor_prompt,
            operation="selection_change",
            cursor_position=len(cursor_prompt) - 12,
            operation_count=12,
        ),
        Scenario(
            "5k-selection-change",
            cursor_prompt_5k,
            operation="selection_change",
            cursor_position=len(cursor_prompt_5k) - 12,
            operation_count=12,
        ),
        Scenario(
            "plain-paste",
            comma_prompt * 5,
            operation="paste",
            clipboard_text=" pasted segment",
        ),
        Scenario(
            "rich-paste",
            comma_prompt * 20,
            operation="paste",
            clipboard_text=rich_paste_text,
            lora_catalog="static",
        ),
        Scenario(
            "danbooru-paste-import",
            comma_prompt * 5,
            operation="paste_import",
            clipboard_text=DANBOORU_IMPORT_URL,
            danbooru_import_enabled=True,
        ),
        Scenario(
            "1k-midprompt-no-comma",
            mid_prompt_prefix + " solo",
            "ha",
            cursor_position=len(mid_prompt_prefix),
        ),
        Scenario(
            "5k-midprompt-no-comma",
            mid_prompt_prefix_5k + " solo",
            "ha",
            cursor_position=len(mid_prompt_prefix_5k),
        ),
        Scenario(
            "10k-local-input",
            mid_prompt_prefix_10k,
            "ha",
            cursor_position=len(mid_prompt_prefix_10k),
        ),
        Scenario(
            "1k-backspace",
            edit_prompt,
            operation="backspace",
            operation_count=8,
        ),
        Scenario(
            "5k-backspace",
            edit_prompt_5k,
            operation="backspace",
            operation_count=8,
        ),
        Scenario(
            "1k-delete",
            edit_prompt,
            operation="delete",
            cursor_position=len(comma_prompt * 20),
            operation_count=8,
        ),
        Scenario(
            "5k-delete",
            edit_prompt_5k,
            operation="delete",
            cursor_position=len(long_prompt * 70),
            operation_count=8,
        ),
        Scenario(
            "1k-enter",
            edit_prompt,
            operation="enter",
            operation_count=3,
        ),
        Scenario(
            "5k-enter",
            edit_prompt_5k,
            operation="enter",
            operation_count=3,
        ),
        Scenario(
            "1k-backspace-newline",
            newline_prompt,
            operation="backspace",
            cursor_position=newline_offset + 1,
            operation_count=1,
        ),
        Scenario(
            "5k-backspace-newline",
            newline_prompt_5k,
            operation="backspace",
            cursor_position=newline_offset_5k + 1,
            operation_count=1,
        ),
        Scenario(
            "1k-delete-newline",
            newline_prompt,
            operation="delete",
            cursor_position=newline_offset,
            operation_count=1,
        ),
        Scenario(
            "5k-delete-newline",
            newline_prompt_5k,
            operation="delete",
            cursor_position=newline_offset_5k,
            operation_count=1,
        ),
        Scenario(
            "projection-coalesced-typing",
            "(cat:1.05), ",
            "xy",
        ),
        Scenario(
            "projection-middle-edit",
            projection_middle_prompt,
            "x",
            cursor_position=projection_middle_offset,
        ),
        Scenario(
            "projection-trailing-enter",
            "alpha",
            operation="enter",
            operation_count=1,
        ),
        Scenario(
            "projection-trailing-newline-backspace",
            "alpha\n",
            operation="backspace",
            operation_count=1,
        ),
        Scenario(
            "projection-syntax-rebuild",
            "alpha",
            "(",
        ),
        Scenario(
            "projection-paint-cache",
            "alpha beta gamma, detailed prompt",
            operation="projection_paint_cache",
            operation_count=2,
        ),
        Scenario(
            "projection-diagnostic-cache",
            "mispelled prompt segment",
            operation="diagnostic_cache",
            operation_count=2,
        ),
        Scenario(
            "projection-fill-band-cache",
            "quality\n**one\nwide shot\n**two\nclose shot",
            operation="fill_band_cache",
            operation_count=2,
        ),
    )
