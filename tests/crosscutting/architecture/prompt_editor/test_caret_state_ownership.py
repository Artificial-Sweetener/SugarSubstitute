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

"""Enforce single ownership of mutable projected-caret state."""

from __future__ import annotations

import ast

from .inventory import PROMPT_PRESENTATION_ROOT


def _assigned_self_attributes(source: str) -> set[str]:
    """Return attribute names assigned directly on ``self`` in one module."""
    assigned: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        targets: tuple[ast.expr, ...]
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        elif isinstance(node, ast.AugAssign):
            targets = (node.target,)
        else:
            continue
        assigned.update(
            target.attr
            for target in targets
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        )
    return assigned


def test_caret_collaborators_mutate_only_the_focused_state_owner() -> None:
    """Keep cursor, anchor, affinity, column, and edit-origin state together."""
    owner_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "caret_state_owner.py"
    ).read_text(encoding="utf-8")
    collaborator_paths = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "caret_movement_controller.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "edit_publication.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "source_commit_ports.py",
        PROMPT_PRESENTATION_ROOT
        / "projection"
        / "source_history_commit_application.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "source_projection_application.py",
        PROMPT_PRESENTATION_ROOT / "interactions" / "mouse_selection_controller.py",
    )

    owned_attributes = {
        "_cursor_state",
        "_anchor_state",
        "_preferred_x",
        "_caret_rect_override",
        "_skip_next_same_source_soft_wrap_move",
    }
    assert owned_attributes <= _assigned_self_attributes(owner_source)
    for path in collaborator_paths:
        assert not (
            owned_attributes
            & _assigned_self_attributes(path.read_text(encoding="utf-8"))
        )
    foundation_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_foundation.py"
    ).read_text(encoding="utf-8")
    assert "PromptProjectionCaretStateOwner(" in foundation_source
    assert "PromptProjectionCaretStateOwner(" not in collaborator_paths[0].read_text(
        encoding="utf-8"
    )
