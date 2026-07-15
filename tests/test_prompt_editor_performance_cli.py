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

"""Tests for prompt editor performance CLI entrypoint and boundaries."""

from __future__ import annotations

import ast
import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from pytest import MonkeyPatch

from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    ScenarioResult,
)
from substitute.devtools.prompt_editor_performance.scenarios import Scenario


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_SCRIPT = PROJECT_ROOT / "tools" / "measure_prompt_editor_performance.py"
SUBSTITUTE_ROOT = PROJECT_ROOT / "substitute"
ALLOWED_DEVTOOLS_IMPORTERS = (SUBSTITUTE_ROOT / "devtools",)
FORBIDDEN_CLI_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "tests",
)


def test_prompt_editor_performance_cli_imports_only_entrypoint_dependencies() -> None:
    """CLI script should stay free of direct Qt, presentation, and test imports."""

    imported_modules = _imported_module_names(
        ast.parse(CLI_SCRIPT.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_CLI_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_production_modules_do_not_import_prompt_performance_devtools() -> None:
    """Production package modules must not depend on benchmark devtools code."""

    offenders: list[str] = []
    for source_path in SUBSTITUTE_ROOT.rglob("*.py"):
        if _is_under_any(source_path, ALLOWED_DEVTOOLS_IMPORTERS):
            continue
        imported_modules = _imported_module_names(
            ast.parse(source_path.read_text(encoding="utf-8"))
        )
        if any(
            imported_module == "substitute.devtools"
            or imported_module.startswith("substitute.devtools.")
            or imported_module == "tools.measure_prompt_editor_performance"
            for imported_module in imported_modules
        ):
            offenders.append(str(source_path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_prompt_editor_performance_cli_delegates_to_runner(
    monkeypatch: MonkeyPatch,
) -> None:
    """CLI should parse typed text, run scenarios, print results, and return zero."""

    module = _load_cli_module()
    calls: dict[str, Any] = {}
    scenario = Scenario("cli", "initial")
    result = ScenarioResult(
        name="cli",
        characters=7,
        operations=0,
        average_ms=0.0,
        p95_ms=0.0,
        max_ms=0.0,
        instrumentation=Instrumentation.create(),
    )

    monkeypatch.setattr(module, "prompt_performance_application", lambda: "app")

    def fake_scenarios(typed_text: str) -> tuple[Scenario, ...]:
        """Record parsed typed text and return deterministic scenarios."""

        calls["typed_text"] = typed_text
        return (scenario,)

    monkeypatch.setattr(module, "_scenarios", fake_scenarios)

    def fake_run_scenarios(
        app: object, scenarios: tuple[Scenario, ...]
    ) -> list[ScenarioResult]:
        """Record runner inputs and return deterministic results."""

        calls["app"] = app
        calls["scenarios"] = scenarios
        return [result]

    def fake_print_results(results: list[ScenarioResult]) -> None:
        """Record printed results without writing benchmark output."""

        calls["results"] = results

    monkeypatch.setattr(module, "_run_scenarios", fake_run_scenarios)
    monkeypatch.setattr(module, "_print_results", fake_print_results)

    exit_code = cast(int, module.main(["--typed-text", "secret prompt"]))

    assert exit_code == 0
    assert calls == {
        "typed_text": "secret prompt",
        "app": "app",
        "scenarios": (scenario,),
        "results": [result],
    }


def test_prompt_editor_performance_cli_can_disable_logging(
    monkeypatch: MonkeyPatch,
) -> None:
    """Logging disable flag should suppress runtime logging before measurement."""

    module = _load_cli_module()
    disable_calls: list[int] = []
    monkeypatch.setattr(module, "prompt_performance_application", lambda: "app")
    monkeypatch.setattr(module, "_scenarios", lambda typed_text: ())
    monkeypatch.setattr(module, "_run_scenarios", lambda app, scenarios: [])
    monkeypatch.setattr(module, "_print_results", lambda results: None)
    monkeypatch.setattr(logging, "disable", disable_calls.append)

    exit_code = cast(int, module.main(["--disable-logging"]))

    assert exit_code == 0
    assert disable_calls == [logging.CRITICAL]


def _load_cli_module() -> ModuleType:
    """Load the CLI script as an isolated module for direct ``main`` tests."""

    spec = importlib.util.spec_from_file_location(
        "measure_prompt_editor_performance_under_test",
        CLI_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load prompt performance CLI module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _is_under_any(path: Path, parents: tuple[Path, ...]) -> bool:
    """Return whether ``path`` is inside any supplied parent directory."""

    return any(path.is_relative_to(parent) for parent in parents)
