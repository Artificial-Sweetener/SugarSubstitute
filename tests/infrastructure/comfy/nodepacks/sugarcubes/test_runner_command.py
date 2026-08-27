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

"""SugarCubes maintenance command contracts."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from substitute.infrastructure.comfy import nodepack_reconciliation
from substitute.infrastructure.comfy import sugarcubes_maintenance_runner
from tests.infrastructure.comfy.nodepacks.sugarcubes.support import (
    _imported_module_names,
    _write_maintenance_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
RUNNER_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "sugarcubes_maintenance_runner.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "urllib",
    "zipfile",
    "shutil",
)


def test_sugarcubes_maintenance_runner_imports_no_ui_or_raw_process_modules() -> None:
    """SugarCubes orchestration should stay independent from UI and raw process APIs."""

    imported_modules = _imported_module_names(
        ast.parse(RUNNER_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_run_sugarcubes_baseline_maintenance_builds_sync_check_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Baseline maintenance should invoke the shared SugarCubes sync/check action."""

    python_path = _write_maintenance_fixture(tmp_path)
    commands: list[list[str]] = []

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Record the maintenance command and report readiness."""

        _ = cwd, on_line, env, timeout_seconds
        commands.append(command)
        return 0, ('{"schemaVersion": 1, "dependencyReadiness": {"ready": true}}',)

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    result = sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)

    assert commands == [
        [
            str(python_path),
            "-m",
            "sugarcubes.maintenance",
            "cube-deps",
            "preflight",
            "--workspace",
            str(tmp_path),
            "--baseline-only",
        ]
    ]
    assert result.exit_code == 0
    assert result.diagnostics == ()


def test_nodepack_reconciliation_facade_exports_sugarcubes_maintenance() -> None:
    """The public reconciliation facade should expose the runner entry point."""

    assert (
        nodepack_reconciliation.run_sugarcubes_baseline_maintenance
        is sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance
    )


def test_run_sugarcubes_baseline_maintenance_uses_preserved_local_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An existing development checkout must remain usable after sync refusal."""

    _write_maintenance_fixture(tmp_path)
    emitted: list[str] = []

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Return a structured required dependency diagnostic."""

        _ = command, cwd, env, timeout_seconds
        if callable(on_line):
            on_line("{")
        return (
            2,
            (
                "{",
                '  "schemaVersion": 1,',
                '  "diagnostics": [',
                "    {",
                '      "code": "base_cubes_sync_failed",',
                '      "severity": "warning",',
                '      "title": "Base-Cubes sync failed",',
                '      "message": "SugarCubes could not update Base-Cubes and is using the local checkout.",',
                '      "details": {"repoRef": "Artificial-Sweetener/Base-Cubes", "reason": "ahead"}',
                "    }",
                "  ]",
                "}",
            ),
        )

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    result = sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(
        tmp_path, on_log=emitted.append
    )

    assert result.exit_code == 2
    assert any(
        line.startswith("WARNING: SugarCubes[base_cubes_sync_failed]")
        for line in emitted
    )
