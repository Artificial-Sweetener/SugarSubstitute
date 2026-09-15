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

"""Provide isolated-process support for bootstrap import-boundary tests."""

from __future__ import annotations

import ast
from collections.abc import Iterable
import importlib.util
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
COMPOSITION_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "composition.py"
)
_IMPORT_PROBE_TIMEOUT_SECONDS = 30


def run_isolated_import_probe(code: str) -> subprocess.CompletedProcess[str]:
    """Run one import probe from the repository with bounded diagnostics."""

    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=_IMPORT_PROBE_TIMEOUT_SECONDS,
    )


def top_level_imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported at top level by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def eager_project_import_closure(module_name: str) -> set[str]:
    """Return the conservative transitive import closure without executing code."""

    pending = [module_name]
    visited: set[str] = set()
    imported: set[str] = set()
    while pending:
        current_name = pending.pop()
        if current_name in visited:
            continue
        visited.add(current_name)
        source_path = _project_module_source(current_name)
        if source_path is None:
            continue
        package_name = (
            current_name
            if source_path.name == "__init__.py"
            else current_name.rpartition(".")[0]
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for imported_name in _eager_import_names(tree.body, package_name=package_name):
            imported.add(imported_name)
            pending.extend(_local_import_chain(imported_name))
    return imported


def _eager_import_names(
    statements: Iterable[ast.stmt],
    *,
    package_name: str,
) -> Iterable[str]:
    """Yield imports executable at module load while ignoring deferred bodies."""

    for statement in statements:
        if isinstance(statement, ast.Import):
            yield from (alias.name for alias in statement.names)
            continue
        if isinstance(statement, ast.ImportFrom):
            imported_module = _resolve_import_from(statement, package_name=package_name)
            if imported_module:
                yield imported_module
                for alias in statement.names:
                    candidate = f"{imported_module}.{alias.name}"
                    if _project_module_source(candidate) is not None:
                        yield candidate
            continue
        if isinstance(statement, ast.If) and _is_type_checking_guard(statement.test):
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.stmt):
                yield from _eager_import_names((child,), package_name=package_name)


def _resolve_import_from(statement: ast.ImportFrom, *, package_name: str) -> str:
    """Resolve one absolute or package-relative import name."""

    if statement.level == 0:
        return statement.module or ""
    relative_name = "." * statement.level + (statement.module or "")
    try:
        return importlib.util.resolve_name(relative_name, package_name)
    except (ImportError, ValueError):
        return ""


def _project_module_source(module_name: str) -> Path | None:
    """Return a repository Python source path for one importable module."""

    relative = Path(*module_name.split("."))
    module_path = PROJECT_ROOT / relative.with_suffix(".py")
    if module_path.is_file():
        return module_path
    package_path = PROJECT_ROOT / relative / "__init__.py"
    if package_path.is_file():
        return package_path
    return None


def _local_import_chain(module_name: str) -> tuple[str, ...]:
    """Return every locally backed package prefix loaded by one import."""

    parts = module_name.split(".")
    return tuple(
        candidate
        for index in range(1, len(parts) + 1)
        if _project_module_source(candidate := ".".join(parts[:index])) is not None
    )


def _is_type_checking_guard(expression: ast.expr) -> bool:
    """Return whether one conditional exists only for static type imports."""

    return isinstance(expression, ast.Name) and expression.id == "TYPE_CHECKING"
