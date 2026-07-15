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

"""Build scheduler-safe prompt text for LoRA catalog selections."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .prompt_lora_catalog_service import PromptLoraCatalogItem

DEFAULT_LORA_SCHEDULE_WEIGHT = "1.00"
_VALID_LORA_SCHEDULE_WEIGHT_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


@dataclass(frozen=True, slots=True)
class PromptLoraScheduleSelection:
    """Describe resolved schedule text for one LoRA catalog selection."""

    item: PromptLoraCatalogItem
    weight_text: str
    replacement_text: str


class PromptLoraScheduleService:
    """Build prompt-control LoRA schedule text from catalog selections."""

    def schedule_selection(
        self,
        item: PromptLoraCatalogItem,
        *,
        weight_text: str | None = None,
    ) -> PromptLoraScheduleSelection:
        """Return the resolved LoRA schedule selection for one catalog item."""

        resolved_weight = _resolved_weight_text(weight_text)
        return PromptLoraScheduleSelection(
            item=item,
            weight_text=resolved_weight,
            replacement_text=f"<lora:{item.prompt_name}:{resolved_weight}>",
        )

    def schedule_text(
        self,
        item: PromptLoraCatalogItem,
        *,
        weight_text: str | None = None,
    ) -> str:
        """Return prompt-control schedule text for one catalog item."""

        return self.schedule_selection(item, weight_text=weight_text).replacement_text


def _resolved_weight_text(weight_text: str | None) -> str:
    """Return numeric weight text or the LoRA scheduling default."""

    if weight_text is None:
        return DEFAULT_LORA_SCHEDULE_WEIGHT
    stripped = weight_text.strip()
    if not stripped:
        return DEFAULT_LORA_SCHEDULE_WEIGHT
    if _VALID_LORA_SCHEDULE_WEIGHT_RE.fullmatch(stripped) is None:
        return DEFAULT_LORA_SCHEDULE_WEIGHT
    return stripped


__all__ = [
    "DEFAULT_LORA_SCHEDULE_WEIGHT",
    "PromptLoraScheduleSelection",
    "PromptLoraScheduleService",
]
