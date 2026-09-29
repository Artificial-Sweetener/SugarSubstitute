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

"""Require deferred Qt callbacks to declare their QObject lifetime context."""

from __future__ import annotations

import ast
from pathlib import Path

from .metrics import governed_source_paths
from .model import ArchitecturePolicy, Diagnostic


_RUNTIME_ROOTS = ("launcher/", "substitute/", "sugarsubstitute_shared/")


def validate_qt_lifetime_policy(
    root: Path,
    policy: ArchitecturePolicy,
) -> list[Diagnostic]:
    """Reject context-free single-shot timers in authored runtime code."""

    diagnostics: list[Diagnostic] = []
    for path in governed_source_paths(root, policy):
        relative = path.relative_to(root).as_posix()
        if path.suffix != ".py" or not relative.startswith(_RUNTIME_ROOTS):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, SyntaxError, UnicodeError):
            continue
        visitor = _QtLifetimeVisitor(relative)
        visitor.visit(tree)
        diagnostics.extend(visitor.diagnostics)
    return diagnostics


class _QtLifetimeVisitor(ast.NodeVisitor):
    """Find QTimer single shots whose callback has no Qt lifetime owner."""

    def __init__(self, relative_path: str) -> None:
        """Initialize import aliases and diagnostics for one source file."""

        self._relative_path = relative_path
        self._timer_names: set[str] = {"QTimer"}
        self._qt_core_names: set[str] = {"QtCore"}
        self._direct_call_references: set[int] = set()
        self.diagnostics: list[Diagnostic] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Record imported QtCore module aliases."""

        for alias in node.names:
            if alias.name == "PySide6.QtCore":
                self._qt_core_names.add(alias.asname or "PySide6.QtCore")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record imported QTimer aliases."""

        if node.module == "PySide6":
            for alias in node.names:
                if alias.name == "QtCore":
                    self._qt_core_names.add(alias.asname or alias.name)
        if node.module == "PySide6.QtCore":
            for alias in node.names:
                if alias.name == "QTimer":
                    self._timer_names.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Require the QObject-context overload for every runtime single shot."""

        if self._is_qtimer_single_shot(node.func):
            self._direct_call_references.add(id(node.func))
        if self._is_single_shot(node.func) and len(node.args) < 3:
            self.diagnostics.append(
                Diagnostic(
                    "QT_LIFETIME001",
                    self._relative_path,
                    "context-free QTimer.singleShot at line "
                    f"{node.lineno}; pass the callback's QObject lifetime owner "
                    "as the second positional argument",
                )
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Reject exporting the raw Qt timer method as an unsafe scheduler."""

        if (
            self._is_qtimer_single_shot(node)
            and id(node) not in self._direct_call_references
        ):
            self.diagnostics.append(
                Diagnostic(
                    "QT_LIFETIME002",
                    self._relative_path,
                    "raw QTimer.singleShot reference at line "
                    f"{node.lineno}; wrap it in a scheduler that supplies the "
                    "callback's QObject lifetime owner",
                )
            )
        self.generic_visit(node)

    @staticmethod
    def _is_single_shot(expression: ast.expr) -> bool:
        """Return whether an expression calls a single-shot timer API."""

        return isinstance(expression, ast.Attribute) and expression.attr == "singleShot"

    def _is_qtimer_single_shot(self, expression: ast.expr) -> bool:
        """Return whether an expression resolves to QTimer.singleShot."""

        if not isinstance(expression, ast.Attribute) or expression.attr != "singleShot":
            return False
        owner = expression.value
        if isinstance(owner, ast.Name):
            return owner.id in self._timer_names
        return (
            isinstance(owner, ast.Attribute)
            and owner.attr == "QTimer"
            and isinstance(owner.value, ast.Name)
            and owner.value.id in self._qt_core_names
        )


__all__ = ["validate_qt_lifetime_policy"]
