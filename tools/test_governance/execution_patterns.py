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

"""Discover timed, polled, environmental, and fixed-resource test patterns."""

from __future__ import annotations

import ast
from collections import Counter

from .ast_analysis import call_name, configured_call_name
from .model import TestCandidate

WAIT_RULE = "WAIT001"
CLOCK_RULE = "CLOCK001"
POLL_RULE = "POLL001"
ENVIRONMENT_RULE = "ENV001"
RESOURCE_RULE = "RESOURCE001"


def execution_pattern_candidates(
    *,
    path: str,
    tree: ast.Module,
    wait_calls: frozenset[str],
    wall_clock_calls: frozenset[str],
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Return time, polling, environment, and resource candidates."""

    visitor = _ExecutionPatternVisitor(
        path=path,
        wait_calls=wait_calls,
        wall_clock_calls=wall_clock_calls,
        aliases=aliases,
    )
    visitor.visit(tree)
    return [*visitor.candidates, *visitor.wall_clock_candidates()]


def reads_environment_name(
    node: ast.AST,
    environment_name: str,
    aliases: dict[str, str],
) -> bool:
    """Return whether one expression reads an exact environment variable."""

    if isinstance(node, ast.Call) and call_name(node.func, aliases) in {
        "os.environ.get",
        "os.getenv",
    }:
        return bool(
            node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == environment_name
        )
    if (
        isinstance(node, ast.Subscript)
        and call_name(node.value, aliases) == "os.environ"
    ):
        return (
            isinstance(node.slice, ast.Constant)
            and node.slice.value == environment_name
        )
    return False


class _ExecutionPatternVisitor(ast.NodeVisitor):
    """Collect stable scoped locators for time and resource patterns."""

    def __init__(
        self,
        *,
        path: str,
        wait_calls: frozenset[str],
        wall_clock_calls: frozenset[str],
        aliases: dict[str, str],
    ) -> None:
        """Initialize one source visitor with exact configured call names."""

        self._path = path
        self._wait_calls = wait_calls
        self._wall_clock_calls = wall_clock_calls
        self._aliases = aliases
        self._scope: list[str] = ["<module>"]
        self._counts: Counter[tuple[str, str]] = Counter()
        self._clock_scopes: set[str] = set()
        self._asserted_comparisons: list[tuple[str, ast.Compare]] = []
        self.candidates: list[TestCandidate] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class ownership while visiting its body."""

        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function ownership while visiting its body."""

        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async-function ownership while visiting its body."""

        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """Record configured waits, clock use, and fixed socket binds."""

        identity = call_name(node.func, self._aliases)
        wait_name = configured_call_name(identity, self._wait_calls)
        scope = self._scope_name
        if configured_call_name(identity, self._wall_clock_calls) is not None:
            self._clock_scopes.add(scope)
        if wait_name is not None:
            ordinal = self._next_ordinal(scope, f"wait-{wait_name}")
            self.candidates.append(
                TestCandidate(
                    rule=WAIT_RULE,
                    path=self._path,
                    locator=f"{scope}:wait:{wait_name}:{ordinal}",
                    evidence=f"calls {wait_name}",
                    line=node.lineno,
                )
            )
        if identity.endswith(".bind") and _has_fixed_bind_port(node):
            ordinal = self._next_ordinal(scope, "fixed-bind")
            self.candidates.append(
                TestCandidate(
                    rule=RESOURCE_RULE,
                    path=self._path,
                    locator=f"{scope}:fixed-bind:{ordinal}",
                    evidence="binds a socket to a fixed nonzero port",
                    line=node.lineno,
                )
            )
        if identity in {
            "os.environ.clear",
            "os.environ.pop",
            "os.environ.popitem",
            "os.environ.setdefault",
            "os.environ.update",
        }:
            self._record_environment_mutation(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Record direct writes to the process environment."""

        if any(self._is_environment_target(target) for target in node.targets):
            self._record_environment_mutation(node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Record annotated writes to the process environment."""

        if self._is_environment_target(node.target):
            self._record_environment_mutation(node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Record augmented writes to the process environment."""

        if self._is_environment_target(node.target):
            self._record_environment_mutation(node)
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        """Record direct deletion from the process environment."""

        if any(self._is_environment_target(target) for target in node.targets):
            self._record_environment_mutation(node)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Record loops whose completion or failure bound reads a real clock."""

        scope = self._scope_name
        direct_clock = any(
            isinstance(item, ast.Call)
            and configured_call_name(
                call_name(item.func, self._aliases),
                self._wall_clock_calls,
            )
            is not None
            for item in ast.walk(node)
        )
        elapsed_timer = scope in self._clock_scopes and any(
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr == "elapsed"
            for item in ast.walk(node)
        )
        if direct_clock or elapsed_timer:
            ordinal = self._next_ordinal(scope, "wall-clock-poll")
            self.candidates.append(
                TestCandidate(
                    rule=POLL_RULE,
                    path=self._path,
                    locator=f"{scope}:wall-clock-poll:{ordinal}",
                    evidence="bounds a polling loop with a real wall clock",
                    line=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        """Retain asserted comparisons for clock-scope analysis after traversal."""

        self._asserted_comparisons.extend(
            (self._scope_name, comparison)
            for comparison in ast.walk(node.test)
            if isinstance(comparison, ast.Compare)
        )
        self.generic_visit(node)

    def wall_clock_candidates(self) -> list[TestCandidate]:
        """Return numeric timing thresholds from scopes that read a real clock."""

        candidates: list[TestCandidate] = []
        for scope, comparison in self._asserted_comparisons:
            if scope not in self._clock_scopes or not _is_timing_threshold(
                comparison,
                self._wall_clock_calls,
                self._aliases,
            ):
                continue
            ordinal = self._next_ordinal(scope, "wall-clock-threshold")
            candidates.append(
                TestCandidate(
                    rule=CLOCK_RULE,
                    path=self._path,
                    locator=f"{scope}:wall-clock-threshold:{ordinal}",
                    evidence="compares real elapsed time with a numeric threshold",
                    line=comparison.lineno,
                )
            )
        return candidates

    @property
    def _scope_name(self) -> str:
        """Return the stable qualified scope currently being visited."""

        return ".".join(self._scope)

    def _next_ordinal(self, scope: str, pattern: str) -> int:
        """Return a stable one-based occurrence ordinal within one scope."""

        key = (scope, pattern)
        self._counts[key] += 1
        return self._counts[key]

    def _is_environment_target(self, node: ast.expr) -> bool:
        """Return whether one assignment target belongs to ``os.environ``."""

        return (
            isinstance(node, ast.Subscript)
            and call_name(node.value, self._aliases) == "os.environ"
        )

    def _record_environment_mutation(self, node: ast.AST) -> None:
        """Record one exact mutation of process-global environment state."""

        scope = self._scope_name
        ordinal = self._next_ordinal(scope, "environment-mutation")
        self.candidates.append(
            TestCandidate(
                rule=ENVIRONMENT_RULE,
                path=self._path,
                locator=f"{scope}:environment-mutation:{ordinal}",
                evidence="mutates process-global environment state directly",
                line=getattr(node, "lineno", 1),
            )
        )


def _has_fixed_bind_port(call: ast.Call) -> bool:
    """Return whether one socket bind call contains a fixed nonzero port."""

    if not call.args or not isinstance(call.args[0], (ast.Tuple, ast.List)):
        return False
    elements = call.args[0].elts
    return (
        len(elements) >= 2
        and isinstance(elements[1], ast.Constant)
        and isinstance(elements[1].value, int)
        and elements[1].value > 0
    )


def _is_timing_threshold(
    comparison: ast.Compare,
    wall_clock_calls: frozenset[str],
    aliases: dict[str, str],
) -> bool:
    """Return whether a comparison imposes a numeric real-time threshold."""

    if not any(
        isinstance(operator, (ast.Lt, ast.LtE, ast.Gt, ast.GtE))
        for operator in comparison.ops
    ):
        return False
    expressions = [comparison.left, *comparison.comparators]
    has_number = any(
        isinstance(expression, ast.Constant)
        and isinstance(expression.value, (int, float))
        and not isinstance(expression.value, bool)
        for expression in expressions
    )
    names = {
        node.id.casefold()
        for expression in expressions
        for node in ast.walk(expression)
        if isinstance(node, ast.Name)
    }
    timing_name = any(
        token in name or name.endswith(("_ms", "_seconds"))
        for name in names
        for token in ("elapsed", "duration", "latency", "timeout", "deadline")
    )
    reads_clock = any(
        isinstance(node, ast.Call)
        and configured_call_name(
            call_name(node.func, aliases),
            wall_clock_calls,
        )
        is not None
        for expression in expressions
        for node in ast.walk(expression)
    )
    return has_number and (timing_name or reads_clock)


__all__ = ["execution_pattern_candidates", "reads_environment_name"]
