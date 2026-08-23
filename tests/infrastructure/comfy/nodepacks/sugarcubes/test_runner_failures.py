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

"""SugarCubes maintenance failure contracts."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pytest

from substitute.infrastructure.comfy import sugarcubes_maintenance_runner
from tests.infrastructure.comfy.nodepacks.sugarcubes.support import (
    _write_maintenance_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def test_run_sugarcubes_baseline_maintenance_exit_two_with_readiness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Readiness-only SugarCubes output should produce a specific diagnostic."""

    _write_maintenance_fixture(tmp_path)

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Return readiness output without explicit diagnostics."""

        _ = command, cwd, on_line, env, timeout_seconds
        return (
            2,
            (
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "diagnostics": [],
                        "dependencyReadiness": {
                            "ready": False,
                            "restartRequired": True,
                            "missingCustomNodes": [
                                "unpublished-nodepack",
                                "unmapped-nodepack",
                            ],
                            "installPlan": [
                                {
                                    "nodeId": "unpublished-nodepack",
                                    "installable": True,
                                    "installed": False,
                                },
                                {
                                    "nodeId": "unmapped-nodepack",
                                    "installable": True,
                                    "installed": False,
                                },
                            ],
                        },
                        "repairResult": {"failedNodes": [], "skippedNodes": []},
                        "restartRequired": True,
                        "syncErrors": [],
                    }
                ),
            ),
        )

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    with pytest.raises(RuntimeError, match="unpublished-nodepack, unmapped-nodepack"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)


def test_run_sugarcubes_baseline_maintenance_exit_one_with_json_raises_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Structured SugarCubes maintenance errors should block setup."""

    _write_maintenance_fixture(tmp_path)

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Return a nonzero structured maintenance error."""

        _ = command, cwd, on_line, env, timeout_seconds
        return (
            1,
            (
                "warning before json",
                "{",
                '  "schemaVersion": 1,',
                '  "error": "SugarCubes maintenance crashed",',
                '  "details": {"exceptionType": "RuntimeError"}',
                "}",
                "warning after json",
            ),
        )

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    with pytest.raises(RuntimeError, match="could not prepare"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)


def test_run_sugarcubes_baseline_maintenance_malformed_nonzero_output_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Malformed maintenance output should still block setup."""

    _write_maintenance_fixture(tmp_path)

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Return malformed nonzero maintenance output."""

        _ = command, cwd, on_line, env, timeout_seconds
        return 1, ("not json", "{broken")

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    with pytest.raises(RuntimeError, match="could not prepare"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)
