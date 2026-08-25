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

"""Prove process-global state mutation discovery for test governance."""

from __future__ import annotations

from pathlib import Path

from tools.test_governance.discovery import discover_test_candidates
from tools.test_governance.execution_patterns import ENVIRONMENT_RULE
from tools.test_governance.loading import load_test_policy
from tools.test_governance.process_state_patterns import (
    MODULE_REGISTRY_RULE,
    QT_GLOBAL_RULE,
)
from .support import write as _write
from .support import write_fixture as _write_fixture


def test_discovery_reports_direct_process_environment_mutation(tmp_path: Path) -> None:
    """Require exact review for writes to the process environment."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_environment.py",
        """import os as environment

environment.environ.setdefault("MODE", "test")
environment.environ["OWNER"] = "capability"
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = discover_test_candidates(tmp_path, policy)

    assert [candidate.rule for candidate in candidates] == [
        ENVIRONMENT_RULE,
        ENVIRONMENT_RULE,
    ]


def test_discovery_rejects_direct_process_module_registry_mutation(
    tmp_path: Path,
) -> None:
    """Reject renamed destructive module writes while allowing scoped monkeypatching."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_module_registry.py",
        """import sys as runtime

def destructive(monkeypatch: object) -> None:
    runtime.modules.pop("package", None)
    runtime.modules["package"] = object()
    del runtime.modules["package"]
    monkeypatch.setitem(runtime.modules, "scoped", object())

def observe() -> bool:
    return "package" in runtime.modules
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == MODULE_REGISTRY_RULE
    ]

    assert [candidate.line for candidate in candidates] == [4, 5, 6]


def test_discovery_rejects_qfluent_mutation_outside_its_state_owner(
    tmp_path: Path,
) -> None:
    """Require QFluent theme and accent changes to use the restoration owner."""

    _write_fixture(tmp_path)
    source = """from qfluentwidgets import setTheme as switch_theme
import qfluentwidgets as fluent

switch_theme(theme())
fluent.setThemeColor(color())
"""
    _write(tmp_path / "tests/capability/test_theme.py", source)
    _write(tmp_path / "tests/presentation/theme/support.py", source)

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == QT_GLOBAL_RULE
    ]

    assert len(candidates) == 2
    assert all(
        candidate.path == "tests/capability/test_theme.py" for candidate in candidates
    )
