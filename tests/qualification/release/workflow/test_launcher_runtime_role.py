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

"""Keep the installed supervisor packaging role separate from standalone setup."""

from __future__ import annotations

import ast
import runpy
import sys

import pytest

from tests.qualification.release.workflow.support import PROJECT_ROOT


def test_only_installed_supervisor_receives_runtime_role_hook() -> None:
    """Bind the role hook to the installed supervisor, never setup or UI builds."""
    launcher_root = PROJECT_ROOT / "launcher"
    hook_name = "installed_launcher_role_hook.py"
    expected_hook = ast.parse(f'[str(launcher_root / "{hook_name}")]', mode="eval").body
    hooked_analyses: list[tuple[str, str]] = []
    for spec in launcher_root.glob("*.spec"):
        tree = ast.parse(spec.read_text(encoding="utf-8"))
        for statement in tree.body:
            if not isinstance(statement, ast.Assign):
                continue
            call = statement.value
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id != "Analysis"
            ):
                continue
            hooks = next(
                value.value for value in call.keywords if value.arg == "runtime_hooks"
            )
            if any(
                isinstance(node, ast.Constant) and node.value == hook_name
                for node in ast.walk(hooks)
            ):
                assert ast.dump(hooks) == ast.dump(expected_hook)
                assert len(statement.targets) == 1
                target = statement.targets[0]
                assert isinstance(target, ast.Name)
                hooked_analyses.append((spec.name, target.id))
    assert hooked_analyses == [("SugarSubstitute-Windows-x64.spec", "a")]


def test_installed_runtime_hook_publishes_the_packaged_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publish the process-local role before launcher UI selection runs."""
    monkeypatch.setattr(
        sys, "_sugarsubstitute_installed_launcher", False, raising=False
    )
    runpy.run_path(str(PROJECT_ROOT / "launcher" / "installed_launcher_role_hook.py"))
    assert getattr(sys, "_sugarsubstitute_installed_launcher") is True
