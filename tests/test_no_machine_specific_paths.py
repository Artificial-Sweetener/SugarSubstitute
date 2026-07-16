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

"""Prevent developer-machine paths from becoming product behavior."""

from __future__ import annotations

import ast
from pathlib import Path
import re

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCANNED_ROOTS = ("substitute", "launcher", "tools")
_MACHINE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^/(?:Users|home|mnt)/)")


def test_python_runtime_and_tool_defaults_have_no_machine_specific_paths() -> None:
    """Source string literals must not bind behavior to a developer filesystem."""

    findings: list[str] = []
    for root_name in _SCANNED_ROOTS:
        for source_path in (_REPO_ROOT / root_name).rglob("*.py"):
            if source_path.name.endswith("_rc.py"):
                continue
            tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(
                    node.value, str
                ):
                    continue
                if _MACHINE_PATH.search(node.value.strip()):
                    relative_path = source_path.relative_to(_REPO_ROOT)
                    findings.append(f"{relative_path}:{node.lineno}: {node.value!r}")

    assert not findings, "Machine-specific paths found:\n" + "\n".join(findings)
