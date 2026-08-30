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

"""Own immutable prompt-editor source and import inventory per test worker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

from tests.crosscutting.architecture.import_graph import (
    internal_import_graph,
    python_module_paths,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROMPT_DOMAIN_ROOT = PROJECT_ROOT / "substitute" / "domain" / "prompt"
PROMPT_APPLICATION_ROOT = PROJECT_ROOT / "substitute" / "application" / "prompt_editor"
PROMPT_PRESENTATION_ROOT = (
    PROJECT_ROOT / "substitute" / "presentation" / "editor" / "prompt_editor"
)
EDITOR_PANEL_ROOT = PROJECT_ROOT / "substitute" / "presentation" / "editor" / "panel"
PROMPT_ARCHITECTURE_ROOTS = (
    PROMPT_DOMAIN_ROOT,
    PROMPT_APPLICATION_ROOT,
    PROMPT_PRESENTATION_ROOT,
    EDITOR_PANEL_ROOT,
)
PANEL_MODULE_PREFIX = "substitute.presentation.editor.panel"
_TARGET_DOMAIN_PACKAGES = frozenset(
    {
        "document",
        "emphasis",
        "features",
        "preferences",
        "regions",
        "reorder",
        "scenes",
        "wildcards",
    }
)
_TARGET_APPLICATION_PACKAGES = frozenset(
    {
        "autocomplete",
        "conditioning",
        "diagnostics",
        "document",
        "editing",
        "features",
        "lora",
        "projection",
        "reorder",
        "scenes",
    }
)
_EXPECTED_PROMPT_TO_PANEL_IMPORTS: dict[str, frozenset[str]] = {}
_EXPECTED_IMPORT_CYCLES: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class PromptEditorArchitectureInventory:
    """Expose one immutable prompt-editor import inventory within a worker."""

    module_paths: Mapping[str, Path]
    graph: Mapping[str, frozenset[str]]


@cache
def prompt_editor_architecture_inventory() -> PromptEditorArchitectureInventory:
    """Build and retain the immutable source graph for this test worker."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    return PromptEditorArchitectureInventory(
        module_paths=MappingProxyType(module_paths),
        graph=MappingProxyType(graph),
    )
