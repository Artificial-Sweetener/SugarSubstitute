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

"""Parse inline LoRA prompt tokens for recipe metadata handling."""

from __future__ import annotations

from dataclasses import dataclass

_LORA_TOKEN_START = "<lora:"


@dataclass(frozen=True, slots=True)
class InlineLoraSpan:
    """Describe one inline LoRA prompt token and its name offsets."""

    outer_start: int
    outer_end: int
    name_start: int
    name_end: int
    prompt_name: str


def inline_lora_spans(prompt_text: str) -> tuple[InlineLoraSpan, ...]:
    """Return inline LoRA token spans from one prompt string."""

    spans: list[InlineLoraSpan] = []
    folded_text = prompt_text.casefold()
    search_start = 0
    while True:
        token_start = folded_text.find(_LORA_TOKEN_START, search_start)
        if token_start < 0:
            break
        name_start = token_start + len(_LORA_TOKEN_START)
        token_end = prompt_text.find(">", name_start)
        if token_end < 0:
            break
        name_end = prompt_text.find(":", name_start, token_end)
        if name_end < 0:
            search_start = token_end + 1
            continue
        prompt_name = prompt_text[name_start:name_end]
        if prompt_name.strip():
            spans.append(
                InlineLoraSpan(
                    outer_start=token_start,
                    outer_end=token_end + 1,
                    name_start=name_start,
                    name_end=name_end,
                    prompt_name=prompt_name,
                )
            )
        search_start = token_end + 1
    return tuple(spans)


__all__ = ["InlineLoraSpan", "inline_lora_spans"]
