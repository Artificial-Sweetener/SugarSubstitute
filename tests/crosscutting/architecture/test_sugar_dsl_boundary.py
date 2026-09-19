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

"""Enforce SugarScript ownership at persistence and import/export boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


def test_frontend_runtime_package_does_not_import_sugar_dsl() -> None:
    """Keep the external Sugar-DSL implementation out of frontend runtime code."""
    runtime_root = Path(__file__).resolve().parents[3] / "substitute"
    offenders: list[str] = []

    for path in runtime_root.rglob("*.py"):
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                if any(
                    alias.name == "sugar" or alias.name.startswith("sugar.")
                    for alias in node.names
                ):
                    offenders.append(str(path.relative_to(runtime_root.parent)))
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if module_name == "sugar" or module_name.startswith("sugar."):
                    offenders.append(str(path.relative_to(runtime_root.parent)))

    assert offenders == []


def test_native_graph_execution_modules_do_not_depend_on_recipe_language() -> None:
    """Keep SugarScript parsing and serialization outside graph execution owners."""

    repository_root = Path(__file__).resolve().parents[3]
    execution_modules = (
        "substitute/application/cubes/graph_backed_cube_stack_service.py",
        "substitute/application/generation/cube_convenience_materializer.py",
        "substitute/application/generation/graph_backed_cube_workflow_builder.py",
        "substitute/application/generation/native_cube_workflow_builder.py",
        "substitute/application/generation/output_seed_resolver.py",
        "substitute/application/prompt_editor/lora/effective_provider.py",
        "substitute/domain/comfy_workflow/cube_analysis.py",
        "substitute/domain/comfy_workflow/cube_projection.py",
        "substitute/infrastructure/comfy/native_cube_execution_client.py",
    )
    forbidden_symbols = {
        "compile_workflow_payload",
        "parse_recipe_script",
        "parse_sugar_script_document",
        "serialize_workflow_to_sugar_script",
    }
    offenders: list[str] = []

    for relative_path in execution_modules:
        path = repository_root / relative_path
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "substitute.domain.recipes"
            ):
                offenders.append(f"{relative_path}:{node.lineno}:recipe-import")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_symbols:
                offenders.append(f"{relative_path}:{node.lineno}:{node.attr}")
            elif isinstance(node, ast.Name) and node.id in forbidden_symbols:
                offenders.append(f"{relative_path}:{node.lineno}:{node.id}")

    assert offenders == []
