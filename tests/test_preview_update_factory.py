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

"""Tests for Comfy preview update DTO construction."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.cube_output_event import SubstituteVisualIdentity
from substitute.infrastructure.comfy.preview_update_factory import (
    build_preview_image_update,
)

_FACTORY_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "preview_update_factory.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_preview_update_factory_imports_no_ui_or_listener_boundaries() -> None:
    """Preview update construction must stay independent of UI and listener code."""

    source = _FACTORY_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_build_preview_image_update_preserves_visual_identity_fields() -> None:
    """Preview update construction should preserve all existing listener fields."""

    image = object()
    update = build_preview_image_update(
        visual_identity=SubstituteVisualIdentity(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
            source_key="wf-1:N2",
            source_label="Preview Cube",
            scene_run_id="scene-run-1",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=1,
            scene_count=3,
        ),
        image=image,
        prompt_id="prompt-1",
        node_id="N2",
        metadata_node_id="N2.raw",
        display_node_id="N2.display",
        parent_node_id="N2.parent",
        real_node_id="N2.real",
    )

    assert update.workflow_id == "wf-1"
    assert update.generation_run_id == "run-1"
    assert update.client_id == "client-1"
    assert update.source_key == "wf-1:N2"
    assert update.source_label == "Preview Cube"
    assert update.scene_run_id == "scene-run-1"
    assert update.scene_key == "portrait"
    assert update.scene_title == "Portrait"
    assert update.scene_order == 1
    assert update.scene_count == 3
    assert update.image is image
    assert update.prompt_id == "prompt-1"
    assert update.node_id == "N2"
    assert update.metadata_node_id == "N2.raw"
    assert update.display_node_id == "N2.display"
    assert update.parent_node_id == "N2.parent"
    assert update.real_node_id == "N2.real"
