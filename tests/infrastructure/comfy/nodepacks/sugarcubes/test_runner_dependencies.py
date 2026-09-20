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

"""SugarCubes maintenance dependency contracts."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path

import pytest

from substitute.infrastructure.comfy import sugarcubes_maintenance_runner
from tests.infrastructure.comfy.nodepacks.sugarcubes.support import (
    _write_maintenance_fixture,
)


def test_exit_two_without_actionable_dependencies_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Incomplete readiness without a repair plan must remain observable."""

    _write_maintenance_fixture(tmp_path)

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Return a missing dependency without an actionable plan."""

        _ = command, cwd, on_line, env, timeout_seconds
        return (
            2,
            (
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "dependencyReadiness": {
                            "ready": False,
                            "missingCustomNodes": ["unavailable-pack"],
                            "installPlan": [],
                            "dependencyVersionPlan": [],
                        },
                    }
                ),
            ),
        )

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    with pytest.raises(RuntimeError, match="Missing nodepacks: unavailable-pack"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)


def test_exit_two_repairs_arbitrary_missing_and_outdated_packs_together(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Submit every actionable cube dependency to SugarCubes in one repair."""

    python_path = _write_maintenance_fixture(tmp_path)
    commands: list[list[str]] = []
    initial_readiness = {
        "ready": False,
        "missingCustomNodes": ["arbitrary-missing-pack"],
        "installPlan": [
            {
                "nodeId": "arbitrary-missing-pack",
                "installable": True,
                "installed": False,
            },
            {
                "nodeId": "arbitrary-outdated-pack",
                "installable": True,
                "installed": True,
            },
        ],
        "dependencyVersionPlan": [
            {
                "nodeId": "arbitrary-missing-pack",
                "status": "missing",
                "repairable": True,
            },
            {
                "nodeId": "arbitrary-outdated-pack",
                "status": "installed_version_too_old",
                "repairable": True,
            },
            {
                "nodeId": "newer-than-required-pack",
                "status": "satisfied",
                "repairable": False,
            },
        ],
    }
    ready = {
        "ready": True,
        "missingCustomNodes": [],
        "installPlan": [],
        "dependencyVersionPlan": [],
    }

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Model preflight, authoritative repair, and verification."""

        _ = cwd, on_line, env, timeout_seconds
        commands.append(command)
        if len(commands) == 1:
            return 2, (json.dumps({"dependencyReadiness": initial_readiness}),)
        if "repair" in command:
            return 0, (json.dumps({"readinessAfter": ready}),)
        return 0, (json.dumps({"dependencyReadiness": ready}),)

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    result = sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)

    preflight = [
        str(python_path),
        "-m",
        "sugarcubes.maintenance",
        "cube-deps",
        "sync-and-check",
        "--workspace",
        str(tmp_path),
    ]
    assert commands == [
        preflight,
        [
            str(python_path),
            "-m",
            "sugarcubes.maintenance",
            "cube-deps",
            "repair",
            "--workspace",
            str(tmp_path),
            "--approve",
            "arbitrary-missing-pack",
            "--approve",
            "arbitrary-outdated-pack",
        ],
        preflight,
    ]
    assert result.exit_code == 0
