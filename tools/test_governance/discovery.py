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

"""Orchestrate objective test-pattern discovery across focused rule owners."""

from __future__ import annotations

import ast
from pathlib import Path

from .ast_analysis import import_aliases
from .execution_patterns import execution_pattern_candidates, reads_environment_name
from .model import TestCandidate, TestPolicy
from .network_resource_patterns import closed_ephemeral_port_candidates
from .node_process_patterns import node_process_pattern_candidates
from .ownership_patterns import ownership_pattern_candidates
from .process_lifecycle_patterns import process_lifecycle_pattern_candidates
from .process_state_patterns import process_state_pattern_candidates
from .semantic_patterns import semantic_pattern_candidates

LAYOUT_RULE = "LAYOUT001"
STUB_RULE = "STUB001"
XDIST_RULE = "XDIST001"
SERIAL_RULE = "SERIAL001"
ISOLATED_RULE = "ISOLATED001"
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
    for support_root in policy.semantic_support_roots:
        for path in sorted((root / support_root).rglob("*.py")):
            if "__pycache__" in path.parts or path.is_relative_to(test_root):
                continue
            candidates.extend(_semantic_support_source_candidates(root, path))
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
    """Delegate one Python test source to its pattern owners."""

    relative_path = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = import_aliases(tree)
    candidates: list[TestCandidate] = []
    xdist_reference = next(
        (
            node
            for node in ast.walk(tree)
            if reads_environment_name(
                node,
                policy.xdist_environment_name,
                aliases,
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
    candidates.extend(
        execution_pattern_candidates(
            path=relative_path,
            tree=tree,
            wait_calls=policy.wait_calls,
            wall_clock_calls=policy.wall_clock_calls,
            aliases=aliases,
        )
    )
    candidates.extend(
        ownership_pattern_candidates(
            root=root,
            test_root=root / policy.test_root,
            source_path=path,
            relative_path=relative_path,
            tree=tree,
            aliases=aliases,
        )
    )
    candidates.extend(
        semantic_pattern_candidates(
            relative_path=relative_path,
            tree=tree,
            aliases=aliases,
        )
    )
    candidates.extend(closed_ephemeral_port_candidates(path=relative_path, tree=tree))
    candidates.extend(
        process_state_pattern_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        )
    )
    candidates.extend(
        process_lifecycle_pattern_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        )
    )
    candidates.extend(
        node_process_pattern_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        )
    )
    return candidates


def _semantic_support_source_candidates(root: Path, path: Path) -> list[TestCandidate]:
    """Discover semantic reliability risks in test-owned support tooling."""

    relative_path = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = import_aliases(tree)
    return [
        *semantic_pattern_candidates(
            relative_path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *process_lifecycle_pattern_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *node_process_pattern_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *closed_ephemeral_port_candidates(path=relative_path, tree=tree),
    ]


__all__ = [
    "ISOLATED_RULE",
    "LAYOUT_RULE",
    "SCRATCH_RULE",
    "SERIAL_RULE",
    "STUB_RULE",
    "XDIST_RULE",
    "discover_test_candidates",
]
