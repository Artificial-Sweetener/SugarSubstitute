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

"""Resolve editor node-card variants without constructing Qt widgets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from substitute.presentation.editor.panel.widgets.field_row import EDITOR_ROW_HEIGHT


class NodeCardVariant(Enum):
    """Name the visual/composition variants supported by the shared card lifecycle."""

    STANDARD = "standard"
    PROMPT_EDITOR = "prompt_editor"
    DETAILER = "detailer"
    COMPACT = "compact"
    RUNTIME_ISSUE = "runtime_issue"


@dataclass(frozen=True, slots=True)
class NodeCardVariantStyle:
    """Describe visual tokens for one node-card variant."""

    body_top_padding: int
    body_bottom_padding: int
    row_spacing: int
    title_height: int | None
    prompt_editor: bool


STANDARD_NODE_CARD_STYLE = NodeCardVariantStyle(
    body_top_padding=0,
    body_bottom_padding=0,
    row_spacing=0,
    title_height=EDITOR_ROW_HEIGHT,
    prompt_editor=False,
)
PROMPT_EDITOR_NODE_CARD_STYLE = NodeCardVariantStyle(
    body_top_padding=0,
    body_bottom_padding=0,
    row_spacing=0,
    title_height=None,
    prompt_editor=True,
)


def resolve_node_card_variant(resolved_behavior: Any) -> NodeCardVariant:
    """Return the card variant implied by resolved behavior metadata."""

    card = getattr(resolved_behavior, "card", None)
    card_mode = getattr(card, "card_mode", None)
    if getattr(card_mode, "value", None) == "prompt":
        return NodeCardVariant.PROMPT_EDITOR
    return NodeCardVariant.STANDARD


def style_for_node_card_variant(variant: NodeCardVariant) -> NodeCardVariantStyle:
    """Return visual tokens for one node-card variant."""

    if variant is NodeCardVariant.PROMPT_EDITOR:
        return PROMPT_EDITOR_NODE_CARD_STYLE
    return STANDARD_NODE_CARD_STYLE


def column_span_for_node_card_variant(variant: NodeCardVariant) -> int:
    """Return the cube masonry column span for one node-card variant."""

    if variant is NodeCardVariant.PROMPT_EDITOR:
        return 2
    return 1
