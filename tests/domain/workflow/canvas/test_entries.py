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

"""Verify inseparable workflow-node and Input-document layer identities."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from substitute.domain.workflow import (
    InputCanvasImageEntry,
    InputCanvasMaskEntry,
    WorkflowCanvasState,
)


def test_image_entry_replacement_retains_node_and_layer_identity() -> None:
    """Changing image pixels must not replace the document entry identity."""

    image_id = uuid4()
    canvas = WorkflowCanvasState()
    entry = canvas.bind_image("Cube:load_image", image_id)

    assert entry == InputCanvasImageEntry("Cube:load_image", image_id)
    assert canvas.bind_image("Cube:load_image", image_id) is entry
    assert canvas.image_entry("Cube:load_image") is entry


def test_empty_mask_entry_is_complete_without_pixel_or_path_state() -> None:
    """An empty mask remains a complete node-owned document-layer entry."""

    image_id = uuid4()
    mask_id = uuid4()
    canvas = WorkflowCanvasState()
    canvas.bind_image("Cube:load_image", image_id)

    entry = canvas.bind_mask(("Cube", "load_mask"), mask_id, image_id)

    assert entry == InputCanvasMaskEntry(
        ("Cube", "load_mask"),
        mask_id,
        image_id,
    )
    assert canvas.mask_entry(("Cube", "load_mask")) is entry
    assert canvas.mask_entry_for_id(mask_id) is entry


def test_entry_identity_changes_require_explicit_replacement() -> None:
    """Accidental rebinding must fail loudly instead of splitting ownership."""

    image_id = uuid4()
    mask_id = uuid4()
    canvas = WorkflowCanvasState()
    canvas.bind_image("Cube:load_image", image_id)
    canvas.bind_mask(("Cube", "load_mask"), mask_id, image_id)

    with pytest.raises(ValueError, match="replace_image_entry"):
        canvas.bind_image("Cube:load_image", uuid4())
    with pytest.raises(ValueError, match="replace_mask_entry"):
        canvas.bind_mask(("Cube", "load_mask"), uuid4(), image_id)


def test_production_code_cannot_reintroduce_parallel_canvas_identity_maps() -> None:
    """Reject access to the deleted split image/mask ownership structures."""

    forbidden = {"input_key_map", "mask_associations", "mask_to_image_map"}
    violations: list[str] = []
    source_root = Path(__file__).parents[1] / "substitute"
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"), source_path.as_posix()
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(
                    f"{source_path.relative_to(source_root)}:{node.lineno}:{node.attr}"
                )

    assert violations == []
