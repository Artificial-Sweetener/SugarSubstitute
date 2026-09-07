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

"""Enforce one lifecycle owner for every presentation menu button."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .metrics import governed_source_paths
from .model import ArchitecturePolicy, Diagnostic

_ADAPTER_PATH = "substitute/presentation/widgets/menu_buttons.py"
_CONTROLLER_PATH = "substitute/presentation/widgets/menu_button_controller.py"
_RAW_MENU_BUTTON_TYPES = frozenset(
    {
        "DropDownPushButton",
        "DropDownToolButton",
        "PrimarySplitPushButton",
        "SplitToolButton",
        "TransparentDropDownToolButton",
    }
)
_BUTTON_ACTIVATION_SIGNALS = frozenset({"clicked", "pressed", "released"})
_RAW_ATTACH_METHODS = frozenset({"setFlyout", "setMenu"})
_RAW_OPEN_METHODS = frozenset({"_showMenu", "showFlyout"})


@dataclass(frozen=True, slots=True, order=True)
class MenuButtonViolation:
    """Identify one menu-button lifecycle bypass by source location."""

    path: str
    line: int
    rule: str
    message: str


def validate_menu_button_policy(
    root: Path,
    policy: ArchitecturePolicy,
) -> list[Diagnostic]:
    """Reject presentation menu buttons outside the shared lifecycle owner."""

    paths = tuple(
        path
        for path in governed_source_paths(root, policy)
        if path.suffix in {".py", ".pyi"}
        and path.relative_to(root).as_posix().startswith("substitute/presentation/")
    )
    return [
        Diagnostic(
            violation.rule,
            violation.path,
            f"line {violation.line}: {violation.message}",
        )
        for violation in discover_menu_button_violations(root, paths)
    ]


def discover_menu_button_violations(
    root: Path,
    paths: tuple[Path, ...],
) -> tuple[MenuButtonViolation, ...]:
    """Return deterministic menu-button lifecycle violations from Python source."""

    violations: list[MenuButtonViolation] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if relative in {_ADAPTER_PATH, _CONTROLLER_PATH}:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        visitor = _MenuButtonVisitor(relative)
        visitor.visit(tree)
        violations.extend(visitor.violations())
    return tuple(sorted(violations))


class _MenuButtonVisitor(ast.NodeVisitor):
    """Collect raw menu controls and button-connected menu open paths."""

    def __init__(self, path: str) -> None:
        """Prepare one source traversal and its local call graph."""

        self._path = path
        self._aliases: dict[str, str] = {}
        self._classes: list[str] = []
        self._functions: dict[
            str,
            ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
        ] = {}
        self._activation_handlers: list[tuple[str, int]] = []
        self._activation_expressions: list[tuple[ast.expr, int]] = []
        self._raw_sites: list[MenuButtonViolation] = []
        self._class_menu_attributes: set[tuple[str, str]] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Record imported module aliases."""

        for alias in node.names:
            self._aliases[alias.asname or alias.name.split(".")[0]] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record imports and reject raw QFluent menu-button types."""

        if node.module is None:
            return
        for alias in node.names:
            local_name = alias.asname or alias.name
            self._aliases[local_name] = f"{node.module}.{alias.name}"
            if node.module == "qfluentwidgets" and alias.name in _RAW_MENU_BUTTON_TYPES:
                self._raw_sites.append(
                    self._violation(
                        node.lineno,
                        "MENU001",
                        f"import {alias.name} through the shared menu-button adapters",
                    )
                )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class ownership and raw QFluent menu-button inheritance."""

        for base in node.bases:
            if self._resolved_name(base).rsplit(".", maxsplit=1)[-1] in (
                _RAW_MENU_BUTTON_TYPES
            ):
                self._raw_sites.append(
                    self._violation(
                        node.lineno,
                        "MENU001",
                        "derive menu buttons from a shared toggle-aware adapter",
                    )
                )
        self._classes.append(node.name)
        self.generic_visit(node)
        self._classes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Index one callable and inspect it within stable ownership."""

        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Index one asynchronous callable and inspect it within stable ownership."""

        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Reject raw attachment and record button activation handlers."""

        if (
            isinstance(node.func, ast.Attribute)
            and self._resolved_name(node.func).startswith("qfluentwidgets.")
            and node.func.attr in _RAW_MENU_BUTTON_TYPES
        ):
            self._raw_sites.append(
                self._violation(
                    node.lineno,
                    "MENU001",
                    f"construct {node.func.attr} through the shared menu-button adapters",
                )
            )
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in _RAW_ATTACH_METHODS:
                self._raw_sites.append(
                    self._violation(
                        node.lineno,
                        "MENU002",
                        f"attach popups through the shared adapter instead of {node.func.attr}()",
                    )
                )
            if (
                node.func.attr == "connect"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr in _BUTTON_ACTIVATION_SIGNALS
                and node.args
            ):
                self._activation_expressions.append((node.args[0], node.lineno))
                handler = self._callable_key(node.args[0])
                if handler is not None:
                    self._activation_handlers.append((handler, node.lineno))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Record class attributes that receive rendered or constructed menus."""

        if self._is_menu_factory_call(node.value):
            for target in node.targets:
                attribute = self._self_attribute(target)
                if attribute is not None and self._classes:
                    self._class_menu_attributes.add((self._classes[-1], attribute))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Record annotated attributes that receive constructed menus."""

        if node.value is not None and self._is_menu_factory_call(node.value):
            attribute = self._self_attribute(node.target)
            if attribute is not None and self._classes:
                self._class_menu_attributes.add((self._classes[-1], attribute))
        self.generic_visit(node)

    def violations(self) -> tuple[MenuButtonViolation, ...]:
        """Return raw sites plus activation handlers that can open menus."""

        violations = list(self._raw_sites)
        violations.extend(
            self._violation(
                line,
                "MENU003",
                "bind menu-opening button activation through MenuButtonController",
            )
            for expression, line in self._activation_expressions
            if self._expression_directly_opens_menu(expression)
        )
        for handler, line in self._activation_handlers:
            if self._call_path_opens_menu(handler, set()):
                violations.append(
                    self._violation(
                        line,
                        "MENU003",
                        "bind menu-opening button activation through MenuButtonController",
                    )
                )
        return tuple(sorted(set(violations)))

    def _expression_directly_opens_menu(self, expression: ast.AST | None) -> bool:
        """Return whether inline activation invokes an evident menu primitive."""

        if expression is None:
            return False
        for child in ast.walk(expression):
            candidate = child.func if isinstance(child, ast.Call) else child
            if not isinstance(candidate, ast.Attribute):
                continue
            if candidate.attr in _RAW_OPEN_METHODS:
                return True
            if candidate.attr == "exec" and any(
                token in self._resolved_name(candidate.value).lower()
                for token in ("menu", "popup", "flyout")
            ):
                return True
        return False

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        """Index and visit one function without losing class ownership."""

        key = ".".join((*self._classes, node.name))
        self._functions[key] = node
        self.generic_visit(node)

    def _call_path_opens_menu(self, key: str, visited: set[str]) -> bool:
        """Return whether one local callable transitively opens a known menu."""

        if key in visited:
            return False
        node = self._functions.get(key)
        if node is None:
            return False
        visited.add(key)
        local_menus = {
            target.id
            for child in ast.walk(node)
            if isinstance(child, (ast.Assign, ast.AnnAssign))
            and child.value is not None
            and self._is_menu_factory_call(child.value)
            for target in (
                child.targets if isinstance(child, ast.Assign) else [child.target]
            )
            if isinstance(target, ast.Name)
        }
        class_name = key.split(".", maxsplit=1)[0] if "." in key else ""
        for call in (child for child in ast.walk(node) if isinstance(child, ast.Call)):
            if isinstance(call.func, ast.Attribute):
                if call.func.attr in _RAW_OPEN_METHODS:
                    return True
                if call.func.attr == "exec" and (
                    isinstance(call.func.value, ast.Name)
                    and call.func.value.id in local_menus
                    or self._self_attribute(call.func.value) is not None
                    and (
                        class_name,
                        self._self_attribute(call.func.value) or "",
                    )
                    in self._class_menu_attributes
                ):
                    return True
            called = self._callable_key(call.func, class_name=class_name)
            if called is not None and self._call_path_opens_menu(called, visited):
                return True
        return False

    def _callable_key(
        self,
        expression: ast.expr,
        *,
        class_name: str | None = None,
    ) -> str | None:
        """Resolve a local function or same-class method reference."""

        if isinstance(expression, ast.Name):
            return expression.id
        if (
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.value.id == "self"
        ):
            owner = class_name or (self._classes[-1] if self._classes else None)
            return None if owner is None else f"{owner}.{expression.attr}"
        if isinstance(expression, ast.Lambda):
            synthetic_key = f"<lambda@{expression.lineno}>"
            self._functions[synthetic_key] = expression
            return synthetic_key
        return None

    def _is_menu_factory_call(self, expression: ast.expr) -> bool:
        """Return whether an expression constructs or renders a QFluent menu."""

        if not isinstance(expression, ast.Call):
            return False
        resolved = self._resolved_name(expression.func)
        if resolved.rsplit(".", maxsplit=1)[-1] in {"CheckableMenu", "RoundMenu"}:
            return True
        return (
            isinstance(expression.func, ast.Attribute)
            and expression.func.attr == "render"
            and isinstance(expression.func.value, ast.Call)
            and self._resolved_name(expression.func.value.func).rsplit(".", maxsplit=1)[
                -1
            ]
            == "QFluentMenuRenderer"
        )

    @staticmethod
    def _self_attribute(expression: ast.expr) -> str | None:
        """Return an attribute name from a direct ``self`` reference."""

        if (
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.value.id == "self"
        ):
            return expression.attr
        return None

    def _resolved_name(self, expression: ast.expr) -> str:
        """Resolve a direct import alias or attribute-qualified expression."""

        if isinstance(expression, ast.Name):
            return self._aliases.get(expression.id, expression.id)
        if isinstance(expression, ast.Attribute):
            owner = self._resolved_name(expression.value)
            return f"{owner}.{expression.attr}" if owner else expression.attr
        return ""

    def _violation(self, line: int, rule: str, message: str) -> MenuButtonViolation:
        """Create one source-local policy result."""

        return MenuButtonViolation(self._path, line, rule, message)


__all__ = [
    "MenuButtonViolation",
    "discover_menu_button_violations",
    "validate_menu_button_policy",
]
