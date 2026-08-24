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

"""Discover semantic proof, ownership, lifecycle, and boundary risks in tests."""

from __future__ import annotations

import ast

from .ast_analysis import call_name, configured_call_name
from .model import TestCandidate

DRAIN_RULE = "DRAIN001"
OPTIONAL_PROOF_RULE = "OPTIONAL001"
UNBOUNDED_WAIT_RULE = "BOUND001"
SUPPRESSED_FAILURE_RULE = "SUPPRESS001"
RANDOMNESS_RULE = "RANDOM001"
NETWORK_RULE = "NETWORK001"

_QUEUED_TURN_CALLS = frozenset({"wait_for_queued_qt_turn"})
_OPTIONAL_PROOF_CALLS = frozenset(
    {
        "pytest.importorskip",
        "pytest.skip",
        "pytest.xfail",
    }
)
_OPTIONAL_PROOF_MARKERS = frozenset(
    {
        "pytest.mark.dependency",
        "pytest.mark.flaky",
        "pytest.mark.order",
        "pytest.mark.run",
        "pytest.mark.skip",
        "pytest.mark.skipif",
        "pytest.mark.xfail",
    }
)
_EXTERNAL_CALLS_REQUIRING_TIMEOUT = frozenset(
    {
        "requests.delete",
        "requests.get",
        "requests.patch",
        "requests.post",
        "requests.put",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.run",
    }
)
_WAIT_METHODS_REQUIRING_BOUND = frozenset({"communicate", "join", "wait"})
_GLOBAL_RANDOM_CALLS = frozenset(
    {
        "random.choice",
        "random.choices",
        "random.getrandbits",
        "random.randint",
        "random.random",
        "random.randrange",
        "random.sample",
        "random.shuffle",
        "random.uniform",
    }
)
_REAL_NETWORK_CALLS = frozenset(
    {
        "httpx.delete",
        "httpx.get",
        "httpx.patch",
        "httpx.post",
        "httpx.put",
        "httpx.request",
        "requests.delete",
        "requests.get",
        "requests.patch",
        "requests.post",
        "requests.put",
        "requests.request",
        "urllib.request.urlopen",
    }
)


def semantic_pattern_candidates(
    *,
    relative_path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Return every semantic-risk candidate discovered in one test source."""

    return [
        *_count_shaped_queued_turn_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *_optional_proof_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *_unbounded_external_wait_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *_suppressed_failure_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *_uncontrolled_randomness_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
        *_real_network_candidates(
            path=relative_path,
            tree=tree,
            aliases=aliases,
        ),
    ]


def _real_network_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find direct network access outside an explicit qualification owner."""

    if path.startswith("tests/qualification/"):
        return []
    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        identity = call_name(node.func, aliases)
        if identity not in _REAL_NETWORK_CALLS:
            continue
        ordinal += 1
        candidates.append(
            TestCandidate(
                rule=NETWORK_RULE,
                path=path,
                locator=f"<module>:real-network:{ordinal}",
                evidence=f"calls {identity} outside a qualification owner",
                line=node.lineno,
            )
        )
    return candidates


def _suppressed_failure_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find broad exceptions converted directly into silent control flow."""

    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        broad_suppress = (
            isinstance(node, ast.Call)
            and call_name(node.func, aliases) == "contextlib.suppress"
            and any(_exception_name(argument) for argument in node.args)
        )
        silent_handler = (
            isinstance(node, ast.ExceptHandler)
            and _exception_name(node.type)
            and all(
                isinstance(statement, (ast.Pass, ast.Return, ast.Continue))
                for statement in node.body
            )
        )
        if not broad_suppress and not silent_handler:
            continue
        ordinal += 1
        line = node.lineno if isinstance(node, (ast.Call, ast.ExceptHandler)) else 1
        candidates.append(
            TestCandidate(
                rule=SUPPRESSED_FAILURE_RULE,
                path=path,
                locator=f"<module>:suppressed-failure:{ordinal}",
                evidence="broad exception can complete without observable failure",
                line=line,
            )
        )
    return candidates


def _exception_name(node: ast.expr | None) -> bool:
    """Return whether one expression names Exception or BaseException."""

    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_exception_name(element) for element in node.elts)
    return False


def _uncontrolled_randomness_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find random behavior whose seed cannot be replayed from test evidence."""

    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        identity = call_name(node.func, aliases)
        unseeded_instance = (
            identity == "random.Random" and not node.args and not node.keywords
        )
        if identity not in _GLOBAL_RANDOM_CALLS and not unseeded_instance:
            continue
        ordinal += 1
        candidates.append(
            TestCandidate(
                rule=RANDOMNESS_RULE,
                path=path,
                locator=f"<module>:uncontrolled-randomness:{ordinal}",
                evidence=f"calls {identity} without a replayable local seed",
                line=node.lineno,
            )
        )
    return candidates


def _unbounded_external_wait_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find external operations whose failure path has no explicit time bound."""

    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        identity = call_name(node.func, aliases)
        external_call = identity in _EXTERNAL_CALLS_REQUIRING_TIMEOUT
        wait_method = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _WAIT_METHODS_REQUIRING_BOUND
        )
        if not external_call and not wait_method:
            continue
        has_timeout_keyword = any(keyword.arg == "timeout" for keyword in node.keywords)
        if external_call and has_timeout_keyword:
            continue
        if wait_method and (node.args or has_timeout_keyword):
            continue
        ordinal += 1
        candidates.append(
            TestCandidate(
                rule=UNBOUNDED_WAIT_RULE,
                path=path,
                locator=f"<module>:unbounded-external-wait:{ordinal}",
                evidence=f"calls {identity} without an explicit failure bound",
                line=node.lineno,
            )
        )
    return candidates


def _optional_proof_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find skips, expected failures, retries, and order-dependent proof."""

    parent_by_node = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    candidates: list[TestCandidate] = []
    ordinal = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            identity = call_name(node.func, aliases)
            if identity not in _OPTIONAL_PROOF_CALLS | _OPTIONAL_PROOF_MARKERS:
                continue
            name = identity
        elif isinstance(node, ast.Attribute):
            name = call_name(node, aliases)
            if name not in _OPTIONAL_PROOF_MARKERS:
                continue
            parent = parent_by_node.get(node)
            if isinstance(parent, ast.Call) and parent.func is node:
                continue
        else:
            continue
        ordinal += 1
        candidates.append(
            TestCandidate(
                rule=OPTIONAL_PROOF_RULE,
                path=path,
                locator=f"<module>:optional-proof:{ordinal}",
                evidence=f"uses {name}, which can suppress, retry, or reorder proof",
                line=node.lineno,
            )
        )
    return candidates


def _count_shaped_queued_turn_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find numeric settling parameters that cannot control queued-turn delivery."""

    candidates: list[TestCandidate] = []
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        if not any(
            isinstance(node, ast.Call)
            and configured_call_name(
                call_name(node.func, aliases),
                _QUEUED_TURN_CALLS,
            )
            is not None
            for node in ast.walk(function)
        ):
            continue
        parent_by_node = {
            child: parent
            for parent in ast.walk(function)
            for child in ast.iter_child_nodes(parent)
        }
        for parameter in _integer_parameters(function):
            references = [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == parameter.arg
            ]
            if any(
                not _is_ignored_or_boolean_guard(reference, parent_by_node)
                for reference in references
            ):
                continue
            candidates.append(
                TestCandidate(
                    rule=DRAIN_RULE,
                    path=path,
                    locator=f"{function.name}:count-shaped-queued-turn:{parameter.arg}",
                    evidence=(
                        "numeric settling parameter does not control repetition "
                        "around one queued-turn barrier"
                    ),
                    line=function.lineno,
                )
            )
    return candidates


def _integer_parameters(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ast.arg, ...]:
    """Return parameters whose annotation declares an integer contract."""

    parameters = (
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    )
    return tuple(
        parameter
        for parameter in parameters
        if parameter.annotation is not None
        and any(
            isinstance(node, ast.Name) and node.id == "int"
            for node in ast.walk(parameter.annotation)
        )
    )


def _is_ignored_or_boolean_guard(
    reference: ast.Name,
    parent_by_node: dict[ast.AST, ast.AST],
) -> bool:
    """Return whether one parameter reference only discards or gates one barrier."""

    node: ast.AST = reference
    while node in parent_by_node:
        parent = parent_by_node[node]
        if isinstance(parent, ast.Assign):
            return any(
                isinstance(target, ast.Name) and target.id == "_"
                for target in parent.targets
            )
        if isinstance(parent, (ast.If, ast.IfExp)):
            return node is parent.test
        if isinstance(
            parent, (ast.BoolOp, ast.Compare, ast.UnaryOp, ast.Tuple, ast.List)
        ):
            node = parent
            continue
        return False
    return False


__all__ = [
    "DRAIN_RULE",
    "NETWORK_RULE",
    "OPTIONAL_PROOF_RULE",
    "RANDOMNESS_RULE",
    "SUPPRESSED_FAILURE_RULE",
    "UNBOUNDED_WAIT_RULE",
    "semantic_pattern_candidates",
]
