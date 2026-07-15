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

"""Contract tests for domain workflow policy behavior and purity."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.domain.workflow import StackManager


def test_stack_manager_set_state_copies_collections() -> None:
    """Protect stack state from caller-side mutation after set_state."""
    manager = StackManager()
    aliases = {"AliasA": "CubeA"}
    loaded: dict[str, dict[str, object]] = {"AliasA": {"nodes": {}}}
    order = ["AliasA"]

    manager.set_state(aliases, loaded, order)

    aliases["AliasB"] = "CubeB"
    loaded["AliasA"] = {"changed": True}
    order.append("AliasB")

    assert manager.cube_aliases == {"AliasA": "CubeA"}
    assert manager.loaded_cubes == {"AliasA": {"nodes": {}}}
    assert manager.stack_order == ["AliasA"]


def test_stack_manager_from_dict_defaults_when_keys_missing() -> None:
    """Deserialize missing fields to empty defaults for robustness."""
    manager = StackManager.from_dict({})

    assert manager.cube_aliases == {}
    assert manager.loaded_cubes == {}
    assert manager.stack_order == []


def test_domain_workflow_modules_do_not_import_qt_dependencies() -> None:
    """Keep domain workflow modules framework-free and deterministic."""
    repo_root = Path(__file__).resolve().parents[1]
    modules = [
        repo_root / "substitute" / "domain" / "workflow" / "models.py",
        repo_root / "substitute" / "domain" / "workflow" / "policies.py",
    ]
    disallowed_prefixes = ("PySide6", "qfluentwidgets", "qpane", "photoshop")
    violations: list[str] = []

    for module_path in modules:
        parsed = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(disallowed_prefixes):
                        violations.append(
                            f"{module_path.name}:{node.lineno}:{alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if module_name.startswith(disallowed_prefixes):
                    violations.append(f"{module_path.name}:{node.lineno}:{module_name}")

    assert not violations, (
        "Domain workflow modules imported UI/framework deps:\n" + "\n".join(violations)
    )
