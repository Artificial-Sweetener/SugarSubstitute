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

"""Build the canonical node-behavior patch for one prompt field."""

from __future__ import annotations

from .models import (
    CardBehaviorPatch,
    CardMode,
    CollapseMode,
    FieldBehaviorPatch,
    FieldPresentation,
    LabelMode,
    NodeBehaviorPatch,
    PromptFieldBehaviorPatch,
    PromptRole,
    RowMode,
    TitleControl,
)

_PROMPT_SYNTAX_STYLE = {"prompt_syntaxes": ["emphasis", "wildcard", "lora"]}


def prompt_node_behavior_patch(
    *,
    field_key: str,
    role: PromptRole,
    linkable: bool = True,
) -> NodeBehaviorPatch:
    """Return the shared card and field behavior for an editable prompt."""

    return NodeBehaviorPatch(
        card=CardBehaviorPatch(
            card_mode=CardMode.PROMPT,
            collapse_mode=CollapseMode.EXEMPT,
            icon_name="eraser" if role is PromptRole.NEGATIVE else "edit",
            title_controls=(TitleControl.NODE_LINK_SELECTOR,),
        ),
        field_patches={
            field_key: FieldBehaviorPatch(
                presentation=FieldPresentation.PROMPT_BOX,
                row_mode=RowMode.FULL_WIDTH,
                label_mode=LabelMode.PROMPT,
                style=_PROMPT_SYNTAX_STYLE,
                prompt=PromptFieldBehaviorPatch(role=role, linkable=linkable),
            )
        },
    )


__all__ = ["prompt_node_behavior_patch"]
