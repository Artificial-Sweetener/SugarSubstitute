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

"""Discover objective test patterns that require human disposition."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from .model import TestCandidate, TestPolicy

LAYOUT_RULE = "LAYOUT001"
STUB_RULE = "STUB001"
XDIST_RULE = "XDIST001"
SERIAL_RULE = "SERIAL001"
ISOLATED_RULE = "ISOLATED001"
WAIT_RULE = "WAIT001"
CLOCK_RULE = "CLOCK001"
POLL_RULE = "POLL001"
ENVIRONMENT_RULE = "ENV001"
RESOURCE_RULE = "RESOURCE001"
SCRATCH_RULE = "SCRATCH001"


def discover_test_candidates(
    root: Path, policy: TestPolicy
) -> tuple[TestCandidate, ...]:
    """Return every exact current test-governance review candidate."""

    test_root = root / policy.test_root
    candidates = [
        *_root_layout_candidates(root, test_root, policy),
        *_stub_candidates(root, test_root),
        *_execution_inventory_candidates(
            root,
            policy,
            variable_name="ISOLATED_TEST_MODULES",
            rule=ISOLATED_RULE,
            locator="isolated-module",
            evidence="module is assigned to the bounded fresh-process runner",
        ),
        *_execution_inventory_candidates(
            root,
            policy,
            variable_name="SERIAL_TEST_MODULES",
            rule=SERIAL_RULE,
            locator="serial-module",
            evidence="module is assigned to the globally sequential serial runner",
        ),
    ]
    for path in sorted(test_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        candidates.extend(_python_source_candidates(root, path, policy))
    return tuple(
        sorted(candidates, key=lambda item: (item.path, item.rule, item.locator))
    )


def _root_layout_candidates(
    root: Path,
    test_root: Path,
    policy: TestPolicy,
) -> list[TestCandidate]:
    """Find authored test sources still stored at the test-package root."""

    candidates: list[TestCandidate] = []
    for path in sorted(test_root.iterdir()):
        relative_path = path.relative_to(root).as_posix()
        if (
            not path.is_file()
            or path.suffix not in policy.root_source_extensions
            or relative_path in policy.allowed_root_source_paths
        ):
            continue
        candidates.append(
            TestCandidate(
                rule=LAYOUT_RULE,
                path=relative_path,
                locator="root-source",
                evidence="authored source is stored directly under tests/",
                line=1,
            )
        )
    return candidates


def _stub_candidates(root: Path, test_root: Path) -> list[TestCandidate]:
    """Find test stubs that can shadow executable test modules or typing state."""

    return [
        TestCandidate(
            rule=STUB_RULE,
            path=path.relative_to(root).as_posix(),
            locator="test-stub",
            evidence=(
                "stub shadows a Python module"
                if path.with_suffix(".py").is_file()
                else "standalone test stub bypasses executable strict typing"
            ),
            line=1,
        )
        for path in sorted(test_root.rglob("*.pyi"))
        if "__pycache__" not in path.parts
    ]


def _execution_inventory_candidates(
    root: Path,
    policy: TestPolicy,
    *,
    variable_name: str,
    rule: str,
    locator: str,
    evidence: str,
) -> list[TestCandidate]:
    """Find every module assigned to one constrained execution inventory."""

    policy_path = root / policy.serial_policy
    tree = ast.parse(policy_path.read_text(encoding="utf-8"), filename=str(policy_path))
    module_paths: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == variable_name
            for target in targets
        ):
            continue
        value = node.value
        if value is None:
            continue
        module_paths.update(
            constant.value
            for constant in ast.walk(value)
            if isinstance(constant, ast.Constant)
            and isinstance(constant.value, str)
            and constant.value.startswith("tests/")
        )
    return [
        TestCandidate(
            rule=rule,
            path=module_path,
            locator=locator,
            evidence=evidence,
            line=1,
        )
        for module_path in sorted(module_paths)
    ]


def _python_source_candidates(
    root: Path,
    path: Path,
    policy: TestPolicy,
) -> list[TestCandidate]:
    """Discover execution patterns in one Python test source."""

    relative_path = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    import_aliases = _import_aliases(tree)
    candidates: list[TestCandidate] = []
    xdist_reference = next(
        (
            node
            for node in ast.walk(tree)
            if _reads_environment_name(
                node,
                policy.xdist_environment_name,
                import_aliases,
            )
        ),
        None,
    )
    if xdist_reference is not None:
        candidates.append(
            TestCandidate(
                rule=XDIST_RULE,
                path=relative_path,
                locator="module-xdist-branch",
                evidence=f"source references {policy.xdist_environment_name}",
                line=getattr(xdist_reference, "lineno", 1),
            )
        )
    scratch_reference = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and len(node.value) < 256
            and policy.repository_scratch_name in node.value
        ),
        None,
    )
    if scratch_reference is not None:
        candidates.append(
            TestCandidate(
                rule=SCRATCH_RULE,
                path=relative_path,
                locator="repository-scratch-reference",
                evidence=f"source references {policy.repository_scratch_name}",
                line=scratch_reference.lineno,
            )
        )
    visitor = _ExecutionPatternVisitor(
        path=relative_path,
        wait_calls=policy.wait_calls,
        wall_clock_calls=policy.wall_clock_calls,
        import_aliases=import_aliases,
    )
    visitor.visit(tree)
    candidates.extend(visitor.candidates)
    candidates.extend(visitor.wall_clock_candidates())
    return candidates


class _ExecutionPatternVisitor(ast.NodeVisitor):
    """Collect stable scoped locators for time and resource patterns."""

    def __init__(
        self,
        *,
        path: str,
        wait_calls: frozenset[str],
        wall_clock_calls: frozenset[str],
        import_aliases: dict[str, str],
    ) -> None:
        """Initialize one source visitor with exact configured call names."""

        self._path = path
        self._wait_calls = wait_calls
        self._wall_clock_calls = wall_clock_calls
        self._import_aliases = import_aliases
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

        call_name = _call_name(node.func, self._import_aliases)
        wait_name = _configured_call_name(call_name, self._wait_calls)
        scope = self._scope_name
        if _configured_call_name(call_name, self._wall_clock_calls) is not None:
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
        if call_name.endswith(".bind") and _has_fixed_bind_port(node):
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
        if call_name in {
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
            and _configured_call_name(
                _call_name(item.func, self._import_aliases),
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
                self._import_aliases,
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
            and _call_name(node.value, self._import_aliases) == "os.environ"
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


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """Return local import names mapped to their canonical dotted owners."""

    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for imported in node.names:
                local_name = imported.asname or imported.name.split(".", maxsplit=1)[0]
                aliases[local_name] = imported.name
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for imported in node.names:
                if imported.name == "*":
                    continue
                local_name = imported.asname or imported.name
                aliases[local_name] = f"{node.module}.{imported.name}"
    return aliases


def _call_name(node: ast.expr, import_aliases: dict[str, str]) -> str:
    """Return one dotted call name without evaluating source."""

    if isinstance(node, ast.Name):
        return import_aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value, import_aliases)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def _configured_call_name(
    call_name: str,
    configured_calls: frozenset[str],
) -> str | None:
    """Return the most specific configured name matching one canonical call."""

    matches = tuple(
        configured
        for configured in configured_calls
        if call_name == configured or call_name.endswith(f".{configured}")
    )
    return max(matches, key=len, default=None)


def _reads_environment_name(
    node: ast.AST,
    environment_name: str,
    import_aliases: dict[str, str],
) -> bool:
    """Return whether one expression reads an exact environment variable."""

    if isinstance(node, ast.Call) and _call_name(node.func, import_aliases) in {
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
        and _call_name(node.value, import_aliases) == "os.environ"
    ):
        return (
            isinstance(node.slice, ast.Constant)
            and node.slice.value == environment_name
        )
    return False


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
    import_aliases: dict[str, str],
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
        and _configured_call_name(
            _call_name(node.func, import_aliases),
            wall_clock_calls,
        )
        is not None
        for expression in expressions
        for node in ast.walk(expression)
    )
    return has_number and (timing_name or reads_clock)
