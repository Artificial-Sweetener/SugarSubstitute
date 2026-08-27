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

"""Discover unowned mutation of interpreter and Qt process-global state."""

from __future__ import annotations

import ast

from .ast_analysis import call_name
from .model import TestCandidate

MODULE_REGISTRY_RULE = "MODULES001"
QT_GLOBAL_RULE = "QTGLOBAL001"
CURRENT_DIRECTORY_RULE = "CWD001"

_QFLUENT_STATE_OWNER = "tests/presentation/theme/support.py"
_QFLUENT_MUTATIONS = frozenset(
    {
        "qfluentwidgets.setTheme",
        "qfluentwidgets.setThemeColor",
    }
)


def process_state_pattern_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Return process-global state mutation candidates for one test source."""

    return [
        *_module_registry_mutation_candidates(path=path, tree=tree, aliases=aliases),
        *_qfluent_global_mutation_candidates(path=path, tree=tree, aliases=aliases),
        *_current_directory_mutation_candidates(path=path, tree=tree, aliases=aliases),
    ]


def _current_directory_mutation_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find direct mutation of the process-global working directory."""

    mutations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and call_name(node.func, aliases) == "os.chdir"
    ]
    return [
        TestCandidate(
            rule=CURRENT_DIRECTORY_RULE,
            path=path,
            locator=f"<module>:current-directory-mutation:{ordinal}",
            evidence="mutates the process-global current directory directly",
            line=node.lineno,
        )
        for ordinal, node in enumerate(
            sorted(mutations, key=lambda item: item.lineno),
            1,
        )
    ]


def _module_registry_mutation_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find unscoped mutation of Python's process-global module registry."""

    mutations: list[ast.stmt | ast.Call] = []
    destructive_calls = {
        "sys.modules.clear",
        "sys.modules.pop",
        "sys.modules.popitem",
        "sys.modules.setdefault",
        "sys.modules.update",
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and call_name(node.func, aliases) in destructive_calls
        ):
            mutations.append(node)
            continue
        targets: tuple[ast.expr, ...]
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = (node.target,)
        elif isinstance(node, ast.Delete):
            targets = tuple(node.targets)
        else:
            continue
        if any(_is_module_registry_target(target, aliases) for target in targets):
            mutations.append(node)
    return [
        TestCandidate(
            rule=MODULE_REGISTRY_RULE,
            path=path,
            locator=f"<module>:module-registry-mutation:{ordinal}",
            evidence="mutates process-global sys.modules state directly",
            line=node.lineno,
        )
        for ordinal, node in enumerate(
            sorted(mutations, key=lambda item: item.lineno),
            1,
        )
    ]


def _is_module_registry_target(
    node: ast.expr,
    aliases: dict[str, str],
) -> bool:
    """Return whether one assignment or deletion target belongs to sys.modules."""

    return (
        isinstance(node, ast.Subscript)
        and call_name(node.value, aliases) == "sys.modules"
    )


def _qfluent_global_mutation_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find direct QFluent appearance mutation outside its restoration owner."""

    if path == _QFLUENT_STATE_OWNER:
        return []
    mutations = [
        (node, identity)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (identity := call_name(node.func, aliases)) in _QFLUENT_MUTATIONS
    ]
    return [
        TestCandidate(
            rule=QT_GLOBAL_RULE,
            path=path,
            locator=f"<module>:qfluent-global-mutation:{ordinal}",
            evidence=f"calls {identity} outside the QFluent state owner",
            line=node.lineno,
        )
        for ordinal, (node, identity) in enumerate(
            sorted(mutations, key=lambda item: item[0].lineno),
            1,
        )
    ]


__all__ = [
    "CURRENT_DIRECTORY_RULE",
    "MODULE_REGISTRY_RULE",
    "QT_GLOBAL_RULE",
    "process_state_pattern_candidates",
]
