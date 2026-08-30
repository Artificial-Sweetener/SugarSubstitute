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

"""Contract tests for durable Output canvas state ownership."""

from __future__ import annotations

import ast
from pathlib import Path


def test_output_canvas_state_service_has_no_widget_or_display_dependencies() -> None:
    """Keep durable Output registration cohesive and below the structural ceiling."""

    module_path = (
        Path(__file__).resolve().parents[4]
        / "substitute"
        / "application"
        / "workflows"
        / "output_canvas_state_service.py"
    )
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    forbidden_imports = {
        name
        for name in imported_modules
        if name.startswith(
            (
                "PySide6",
                "qfluentwidgets",
                "qpane",
                "substitute.presentation",
                "substitute.infrastructure.comfy",
            )
        )
    }
    forbidden_tokens = {
        token
        for token in (
            "QWidget",
            "QImage",
            "QPane",
            "canvas_host",
            "currentRouteKey",
            "setCurrentImageID",
            "addImage",
            "removeImageByID",
            "OutputCanvasView",
            "CanvasProjectionScheduler",
            "ProjectionReason",
            "websocket",
            "begin_output_generation",
            "apply_output_source_timing",
            "commit_generated_output",
            "build_output_canvas_projection",
        )
        if token in source
    }
    nonblank_noncomment_lines = sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in source.splitlines()
    )

    assert forbidden_imports == set()
    assert forbidden_tokens == set()
    assert nonblank_noncomment_lines <= 350


def test_output_canvas_owners_respect_structural_soft_ceiling() -> None:
    """Keep each extracted Output owner below the reviewed QPane soft ceiling."""

    workflows_path = (
        Path(__file__).resolve().parents[4] / "substitute" / "application" / "workflows"
    )
    owner_modules = (
        "output_canvas_projection.py",
        "output_canvas_route_projection.py",
        "output_canvas_focus_service.py",
        "output_generated_result_service.py",
        "output_navigation_session_service.py",
        "output_canvas_timing_service.py",
        "output_canvas_state_service.py",
    )

    oversized_modules = {
        module_name: nonblank_noncomment_lines
        for module_name in owner_modules
        if (
            nonblank_noncomment_lines := sum(
                bool(line.strip()) and not line.lstrip().startswith("#")
                for line in (workflows_path / module_name)
                .read_text(encoding="utf-8")
                .splitlines()
            )
        )
        > 350
    }

    assert oversized_modules == {}
