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

"""Discover child-process lifetime ownership risks in tests."""

from __future__ import annotations

import ast

from .ast_analysis import call_name
from .model import TestCandidate

CHILD_PROCESS_RULE = "PROCESS001"


def process_lifecycle_pattern_candidates(
    *,
    path: str,
    tree: ast.Module,
    aliases: dict[str, str],
) -> list[TestCandidate]:
    """Find child processes whose lifetime is not owned by a context manager."""

    parent_by_node = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    candidates: list[TestCandidate] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and call_name(node.func, aliases) == "subprocess.Popen"
        ):
            continue
        parent = parent_by_node.get(node)
        context_managed = (
            isinstance(parent, ast.withitem) and parent.context_expr is node
        )
        if context_managed:
            continue
        candidates.append(
            TestCandidate(
                rule=CHILD_PROCESS_RULE,
                path=path,
                locator=f"<module>:unscoped-child-process:{len(candidates) + 1}",
                evidence=(
                    "starts a child process without a context-managed lifetime; "
                    "termination and bounded cleanup require source review"
                ),
                line=node.lineno,
            )
        )
    return candidates


__all__ = ["CHILD_PROCESS_RULE", "process_lifecycle_pattern_candidates"]
