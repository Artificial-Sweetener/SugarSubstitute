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

"""Inspect one Python source for execution-boundary policy evidence."""

from __future__ import annotations

import ast
from collections.abc import Collection, Mapping
from functools import cached_property
from pathlib import Path


class ExecutionSourceScanner:
    """Reuse one immutable source snapshot across execution-policy checks."""

    def __init__(self, source_path: Path) -> None:
        """Prepare a scanner for one repository source file."""

        self._source_path = source_path

    @cached_property
    def text(self) -> str:
        """Return the source text captured by this scanner."""

        return self._source_path.read_text(encoding="utf-8")

    @cached_property
    def tree(self) -> ast.Module:
        """Return the parsed source tree captured by this scanner."""

        return ast.parse(self.text)

    def raw_execution_findings(
        self,
        raw_execution_imports: Mapping[str, str],
    ) -> tuple[str, ...]:
        """Return raw execution primitives used in the source."""

        aliases = self._raw_execution_aliases(raw_execution_imports)
        findings: set[str] = set()
        qevent_loop_names = self._qevent_loop_variable_names(
            aliases=aliases,
            raw_execution_imports=raw_execution_imports,
        )
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                call_name = self._resolved_name(self._call_name(node.func), aliases)
                raw_call_name = raw_execution_imports.get(call_name, call_name)
                if raw_call_name == "ThreadPoolExecutor":
                    findings.add("ThreadPoolExecutor")
                if raw_call_name == "threading.Thread":
                    findings.add("threading.Thread")
                if raw_call_name == "QThreadPool":
                    findings.add("QThreadPool")
                if call_name.endswith("QThreadPool.globalInstance.start"):
                    findings.add("QThreadPool.globalInstance().start")
                if raw_call_name == "QEventLoop":
                    findings.add("QEventLoop")
                if self._is_qevent_loop_exec(
                    node,
                    qevent_loop_names=qevent_loop_names,
                ):
                    findings.add("QEventLoop.exec")
                if raw_call_name in {
                    "threading.Condition",
                    "threading.Event",
                    "threading.Lock",
                    "threading.RLock",
                }:
                    findings.add(raw_call_name)
            elif isinstance(node, ast.ClassDef):
                if any(
                    raw_execution_imports.get(
                        self._resolved_name(self._base_name(base), aliases),
                        self._resolved_name(self._base_name(base), aliases),
                    )
                    == "QRunnable"
                    for base in node.bases
                ):
                    findings.add("QRunnable")
            elif isinstance(node, ast.keyword) and node.arg == "default_factory":
                factory_name = self._resolved_name(
                    self._call_name(node.value),
                    aliases,
                )
                raw_factory_name = raw_execution_imports.get(
                    factory_name,
                    factory_name,
                )
                if raw_factory_name in {
                    "threading.Condition",
                    "threading.Event",
                    "threading.Lock",
                    "threading.RLock",
                }:
                    findings.add(raw_factory_name)
        return tuple(sorted(findings))

    def never_cancelled_findings(self) -> tuple[int, ...]:
        """Return lines that construct a never-cancelled token."""

        aliases = self._never_cancelled_aliases()
        line_numbers: list[int] = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = self._resolved_name(self._call_name(node.func), aliases)
            if call_name.endswith("NeverCancelled"):
                line_numbers.append(node.lineno)
        return tuple(sorted(line_numbers))

    def production_wait_for_idle_findings(self) -> tuple[int, ...]:
        """Return wait helpers that pump events or sleep."""

        line_numbers: list[int] = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "wait_for_idle":
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                call_name = self._call_name(child.func)
                if call_name.endswith("processEvents") or call_name in {
                    "sleep",
                    "time.sleep",
                }:
                    line_numbers.append(node.lineno)
                    break
        return tuple(line_numbers)

    def module_level_executor_findings(self) -> tuple[int, ...]:
        """Return lines that construct a module-level thread-pool executor."""

        line_numbers: list[int] = []
        for statement in self.tree.body:
            for node in ast.walk(statement):
                if not isinstance(node, ast.Call):
                    continue
                if self._call_name(node.func).endswith("ThreadPoolExecutor"):
                    line_numbers.append(node.lineno)
        return tuple(line_numbers)

    def execution_lane_constructor_findings(
        self,
        constructors: Collection[str],
    ) -> tuple[tuple[int, str], ...]:
        """Return lines that construct concrete execution lanes."""

        findings: list[tuple[int, str]] = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = self._call_name(node.func)
            if any(
                call_name == constructor or call_name.endswith(f".{constructor}")
                for constructor in constructors
            ):
                findings.append((node.lineno, call_name))
        return tuple(findings)

    def long_lived_handle_constructor_findings(self) -> tuple[tuple[int, str], ...]:
        """Return lines that construct long-lived task handles."""

        findings: list[tuple[int, str]] = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = self._call_name(node.func)
            if call_name == "LongLivedTaskHandle" or call_name.endswith(
                ".LongLivedTaskHandle"
            ):
                findings.append((node.lineno, call_name))
        return tuple(findings)

    def terminology_findings(
        self,
        terms: Collection[str],
    ) -> tuple[tuple[int, str], ...]:
        """Return source lines containing governed execution terminology."""

        findings: list[tuple[int, str]] = []
        for line_number, line in enumerate(self.text.splitlines(), start=1):
            findings.extend((line_number, term) for term in terms if term in line)
        return tuple(findings)

    def imported_module_names(self) -> frozenset[str]:
        """Return module names imported by the source."""

        modules: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.add(node.module)
        return frozenset(modules)

    def _raw_execution_aliases(
        self,
        raw_execution_imports: Mapping[str, str],
    ) -> dict[str, str]:
        """Return aliases that can hide raw execution primitives."""

        aliases: dict[str, str] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"threading", "concurrent.futures"}:
                        aliases[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                for alias in node.names:
                    imported_name = f"{node.module}.{alias.name}"
                    if imported_name in raw_execution_imports:
                        aliases[alias.asname or alias.name] = imported_name
        return aliases

    def _never_cancelled_aliases(self) -> dict[str, str]:
        """Return aliases that can hide NeverCancelled construction."""

        aliases: dict[str, str] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                for alias in node.names:
                    if alias.name == "NeverCancelled":
                        aliases[alias.asname or alias.name] = (
                            f"{node.module}.{alias.name}"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("substitute.application.execution"):
                        aliases[alias.asname or alias.name] = alias.name
        return aliases

    def _qevent_loop_variable_names(
        self,
        *,
        aliases: Mapping[str, str],
        raw_execution_imports: Mapping[str, str],
    ) -> set[str]:
        """Return local names assigned from QEventLoop construction."""

        names: set[str] = set()
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Assign) or not isinstance(
                node.value,
                ast.Call,
            ):
                continue
            call_name = self._resolved_name(self._call_name(node.value.func), aliases)
            if raw_execution_imports.get(call_name, call_name) != "QEventLoop":
                continue
            names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        return names

    @classmethod
    def _is_qevent_loop_exec(
        cls,
        node: ast.Call,
        *,
        qevent_loop_names: set[str],
    ) -> bool:
        """Return whether a call is exec() on a known QEventLoop instance."""

        if not isinstance(node.func, ast.Attribute) or node.func.attr != "exec":
            return False
        value = node.func.value
        if isinstance(value, ast.Name):
            return value.id in qevent_loop_names
        if isinstance(value, ast.Call):
            return cls._call_name(value.func).endswith("QEventLoop")
        return False

    @classmethod
    def _call_name(cls, node: ast.AST) -> str:
        """Return a dotted call name from an AST call target."""

        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = cls._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        if isinstance(node, ast.Call):
            return cls._call_name(node.func)
        return ""

    @classmethod
    def _base_name(cls, node: ast.AST) -> str:
        """Return a dotted class base name."""

        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = cls._base_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""

    @staticmethod
    def _resolved_name(name: str, aliases: Mapping[str, str]) -> str:
        """Expand the leading import alias in a dotted name."""

        head, separator, tail = name.partition(".")
        resolved_head = aliases.get(head, head)
        return f"{resolved_head}.{tail}" if separator else resolved_head
