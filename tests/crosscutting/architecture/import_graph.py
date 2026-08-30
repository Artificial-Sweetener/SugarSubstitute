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

"""Build deterministic internal Python import graphs for architecture tests."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from importlib.util import resolve_name
from pathlib import Path

type ModulePaths = dict[str, Path]
type ImportGraph = dict[str, frozenset[str]]


def python_module_paths(
    project_root: Path,
    source_roots: tuple[Path, ...],
) -> ModulePaths:
    """Return importable module names and paths below the supplied roots."""

    modules: ModulePaths = {}
    for source_root in source_roots:
        for source_path in source_root.rglob("*.py"):
            if "__pycache__" in source_path.parts:
                continue
            modules[_module_name(project_root, source_path)] = source_path
    return modules


def internal_import_graph(module_paths: ModulePaths) -> ImportGraph:
    """Return exact internal imports between the supplied Python modules."""

    module_names = frozenset(module_paths)
    return {
        module_name: frozenset(
            imported_module
            for imported_name in _imported_names(source_path, module_name)
            if (
                imported_module := _owned_module_name(
                    imported_name,
                    module_names,
                )
            )
            is not None
        )
        for module_name, source_path in module_paths.items()
    }


def strongly_connected_components(
    graph: Mapping[str, frozenset[str]],
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic cyclic components from one directed import graph."""

    next_index = 0
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(module_name: str) -> None:
        """Visit one module using Tarjan's strongly connected component walk."""

        nonlocal next_index
        indices[module_name] = next_index
        low_links[module_name] = next_index
        next_index += 1
        stack.append(module_name)
        on_stack.add(module_name)

        for imported_module in sorted(graph[module_name]):
            if imported_module not in indices:
                visit(imported_module)
                low_links[module_name] = min(
                    low_links[module_name],
                    low_links[imported_module],
                )
            elif imported_module in on_stack:
                low_links[module_name] = min(
                    low_links[module_name],
                    indices[imported_module],
                )

        if low_links[module_name] != indices[module_name]:
            return
        component: list[str] = []
        while stack:
            stacked_module = stack.pop()
            on_stack.remove(stacked_module)
            component.append(stacked_module)
            if stacked_module == module_name:
                break
        if len(component) > 1 or module_name in graph[module_name]:
            components.append(tuple(sorted(component)))

    for module_name in sorted(graph):
        if module_name not in indices:
            visit(module_name)
    return tuple(sorted(components))


def _module_name(project_root: Path, source_path: Path) -> str:
    """Return the import name represented by one repository Python path."""

    relative_path = source_path.relative_to(project_root).with_suffix("")
    parts = relative_path.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_names(source_path: Path, module_name: str) -> frozenset[str]:
    """Return absolute import names referenced by one Python source module."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    package_name = (
        module_name
        if source_path.name == "__init__.py"
        else module_name.rpartition(".")[0]
    )
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            relative_name = "." * node.level + (node.module or "")
            imported_names.add(resolve_name(relative_name, package_name))
        elif node.module is not None:
            imported_names.add(node.module)
    return frozenset(imported_names)


def _owned_module_name(
    imported_name: str,
    module_names: frozenset[str],
) -> str | None:
    """Return the most specific supplied module owning one imported name."""

    matches = tuple(
        module_name
        for module_name in module_names
        if imported_name == module_name or imported_name.startswith(f"{module_name}.")
    )
    return max(matches, key=len, default=None)


__all__ = [
    "ImportGraph",
    "ModulePaths",
    "internal_import_graph",
    "python_module_paths",
    "strongly_connected_components",
]
