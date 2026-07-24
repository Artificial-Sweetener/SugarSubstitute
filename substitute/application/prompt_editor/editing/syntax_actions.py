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

"""Define typed source-coordinate actions emitted by prompt syntax features."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PromptSyntaxAction:
    """Describe one typed syntax-aware editor request emitted by a renderer."""


@dataclass(frozen=True, slots=True)
class PromptConsumeSyntaxAction(PromptSyntaxAction):
    """Consume one syntax-owned interaction without mutating prompt text."""

    syntax_kind: str


@dataclass(frozen=True, slots=True)
class PromptAdjustEmphasisAction(PromptSyntaxAction):
    """Adjust one emphasis shell identified by its exact outer source range."""

    outer_start: int
    outer_end: int
    delta: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptAdjustEmphasisContentAction(PromptSyntaxAction):
    """Adjust emphasis over one visible content range without a shell."""

    content_start: int
    content_end: int
    delta: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptSetEmphasisWeightAction(PromptSyntaxAction):
    """Set one emphasis shell to an exact weight by its outer source range."""

    outer_start: int
    outer_end: int
    weight: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptSetEmphasisWeightContentAction(PromptSyntaxAction):
    """Set emphasis to one exact weight over a visible content range."""

    content_start: int
    content_end: int
    weight: float | Decimal
    syntax_kind: str = "emphasis"


@dataclass(frozen=True, slots=True)
class PromptAdjustLoraWeightAction(PromptSyntaxAction):
    """Adjust one LoRA token identified by its exact outer source range."""

    outer_start: int
    outer_end: int
    delta: float | Decimal
    syntax_kind: str = "lora"


@dataclass(frozen=True, slots=True)
class PromptSetLoraWeightAction(PromptSyntaxAction):
    """Set one LoRA token to an exact first-weight value."""

    outer_start: int
    outer_end: int
    weight: float | Decimal
    syntax_kind: str = "lora"


@dataclass(frozen=True, slots=True)
class PromptSetWildcardTagAction(PromptSyntaxAction):
    """Set one wildcard placeholder to an exact free-text group tag."""

    outer_start: int
    outer_end: int
    tag: str
    syntax_kind: str = "wildcard"


@dataclass(frozen=True, slots=True)
class PromptAdjustWildcardTagAction(PromptSyntaxAction):
    """Adjust one wildcard placeholder's numeric display group tag."""

    outer_start: int
    outer_end: int
    current_display_tag: str
    delta: int
    syntax_kind: str = "wildcard"


__all__ = [
    "PromptAdjustEmphasisAction",
    "PromptAdjustEmphasisContentAction",
    "PromptAdjustLoraWeightAction",
    "PromptAdjustWildcardTagAction",
    "PromptConsumeSyntaxAction",
    "PromptSetEmphasisWeightAction",
    "PromptSetEmphasisWeightContentAction",
    "PromptSetLoraWeightAction",
    "PromptSetWildcardTagAction",
    "PromptSyntaxAction",
]
