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

"""Reject system-Git dependencies and unprotected ComfyCLI commands."""

from __future__ import annotations

import ast
from pathlib import Path

from .model import Diagnostic

_COMMAND_OWNER = "substitute/infrastructure/comfy/comfy_manager_runtime.py"
_ENVIRONMENT_OWNER = "substitute/infrastructure/comfy/manager_environment.py"
_COMFY_CLI_MODULES = frozenset(
    {"comfy_cli", "cm_cli", "comfyui_manager.prestartup_script"}
)


def validate_system_git_policy(root: Path) -> list[Diagnostic]:
    """Return violations from authored runtime Python sources."""

    diagnostics: list[Diagnostic] = []
    for source_root_name in ("substitute", "launcher"):
        source_root = root / source_root_name
        if not source_root.is_dir():
            continue
        for path in sorted(source_root.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeError, SyntaxError):
                continue
            diagnostics.extend(_source_diagnostics(tree, relative))
    return diagnostics


def _source_diagnostics(tree: ast.AST, relative_path: str) -> list[Diagnostic]:
    """Inspect one parsed source tree for forbidden process contracts."""

    diagnostics: list[Diagnostic] = []
    reported_rules: set[str] = set()
    for node in ast.walk(tree):
        if _is_system_git_command(node) or _is_system_git_discovery(node):
            _report_once(
                diagnostics,
                reported_rules,
                "GIT001",
                relative_path,
                "System Git is forbidden in SugarSubstitute runtime code; use the "
                "repository pygit2 owner instead.",
            )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _COMFY_CLI_MODULES and relative_path != _COMMAND_OWNER:
                _report_once(
                    diagnostics,
                    reported_rules,
                    "GIT002",
                    relative_path,
                    "ComfyCLI commands must run through the protected Comfy Manager "
                    "command owner so external GitPython imports cannot require system Git.",
                )
            if node.value == "GIT_PYTHON_GIT_EXECUTABLE":
                _report_once(
                    diagnostics,
                    reported_rules,
                    "GIT003",
                    relative_path,
                    "SugarSubstitute must not discover or configure a system Git executable.",
                )
            if (
                node.value == "GIT_PYTHON_REFRESH"
                and relative_path != _ENVIRONMENT_OWNER
            ):
                _report_once(
                    diagnostics,
                    reported_rules,
                    "GIT004",
                    relative_path,
                    "GitPython import protection belongs only to the authoritative "
                    "Comfy Manager environment owner.",
                )
    return diagnostics


def _is_system_git_command(node: ast.AST) -> bool:
    """Return whether a literal argv begins with a Git executable."""

    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        values = tuple(_string_constant(element) for element in node.elts[:2])
        if _is_git_executable(values[0]):
            return True
        return (
            values[0] is not None
            and _executable_name(values[0]) in {"where", "where.exe"}
            and len(values) > 1
            and _is_git_executable(values[1])
        )
    if not isinstance(node, ast.Call) or not node.args:
        return False
    function_name = (
        node.func.attr
        if isinstance(node.func, ast.Attribute)
        else node.func.id
        if isinstance(node.func, ast.Name)
        else ""
    )
    command = _string_constant(node.args[0])
    return (
        function_name in {"Popen", "call", "check_call", "check_output", "run"}
        and command is not None
        and _is_git_executable(command.split(maxsplit=1)[0])
    )


def _is_system_git_discovery(node: ast.AST) -> bool:
    """Return whether code explicitly searches for a Git executable."""

    if not isinstance(node, ast.Call) or not node.args:
        return False
    function = node.func
    is_which = (
        isinstance(function, ast.Attribute)
        and function.attr == "which"
        or isinstance(function, ast.Name)
        and function.id == "which"
    )
    if not is_which:
        return False
    argument = node.args[0]
    return (
        isinstance(argument, ast.Constant)
        and isinstance(argument.value, str)
        and _is_git_executable(argument.value)
    )


def _string_constant(node: ast.AST) -> str | None:
    """Return one literal string without evaluating authored code."""

    return (
        node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        else None
    )


def _is_git_executable(value: str | None) -> bool:
    """Recognize portable and Windows system-Git executable names."""

    return value is not None and _executable_name(value) in {
        "git",
        "git.bat",
        "git.cmd",
        "git.exe",
    }


def _executable_name(value: str) -> str:
    """Extract an executable name independent of the checker host platform."""

    return value.replace("\\", "/").rsplit("/", maxsplit=1)[-1].casefold()


def _report_once(
    diagnostics: list[Diagnostic],
    reported_rules: set[str],
    rule: str,
    path: str,
    message: str,
) -> None:
    """Append one file-level diagnostic per policy rule."""

    if rule in reported_rules:
        return
    reported_rules.add(rule)
    diagnostics.append(Diagnostic(rule, path, message))


__all__ = ["validate_system_git_policy"]
