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

"""Tests for infrastructure package facades used during startup."""

from __future__ import annotations

import ast
from pathlib import Path

import substitute.infrastructure.comfy as comfy_facade
import substitute.infrastructure.persistence as persistence_facade

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMFY_FACADE_SOURCE = (
    PROJECT_ROOT / "substitute" / "infrastructure" / "comfy" / "__init__.py"
)
PERSISTENCE_FACADE_SOURCE = (
    PROJECT_ROOT / "substitute" / "infrastructure" / "persistence" / "__init__.py"
)


def test_comfy_facade_uses_lazy_runtime_exports() -> None:
    """The package facade should not import HTTP-heavy adapters at module load."""

    top_level_imports = _top_level_imported_module_names(COMFY_FACADE_SOURCE)

    assert "substitute.infrastructure.comfy.prompt_gateway" not in top_level_imports
    assert "substitute.infrastructure.comfy.asset_stagers" not in top_level_imports
    assert "substitute.infrastructure.comfy.gateway_adapter" not in top_level_imports


def test_comfy_facade_resolves_public_adapter_exports() -> None:
    """Existing package-level adapter imports should continue to resolve."""

    assert (
        getattr(comfy_facade.LocalComfyAssetStager, "__name__")
        == "LocalComfyAssetStager"
    )


def test_persistence_facade_uses_lazy_runtime_exports() -> None:
    """The persistence facade should not import HTTP/Qt-heavy adapters at module load."""

    top_level_imports = _top_level_imported_module_names(PERSISTENCE_FACADE_SOURCE)

    assert (
        "substitute.infrastructure.persistence.model_thumbnail_store"
        not in top_level_imports
    )
    assert "substitute.infrastructure.persistence.image_store" not in top_level_imports


def test_persistence_facade_resolves_public_adapter_exports() -> None:
    """Existing package-level persistence imports should continue to resolve."""

    assert (
        getattr(persistence_facade.FilePromptEditorPreferenceRepository, "__name__")
        == "FilePromptEditorPreferenceRepository"
    )


def _top_level_imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported at module load time by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
