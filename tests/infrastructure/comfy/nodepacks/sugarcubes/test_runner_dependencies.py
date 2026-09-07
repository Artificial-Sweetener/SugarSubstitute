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

from substitute.infrastructure.comfy import sugarcubes_dependency_installer
from substitute.infrastructure.comfy import sugarcubes_maintenance_runner
from tests.support.version_control.repository_service_support import (
    RecordingRepositoryService,
)
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


def test_run_sugarcubes_baseline_maintenance_exit_two_runs_once_without_raw_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SugarCubes maintenance should not use retry passes or stream JSON blobs."""

    _write_maintenance_fixture(tmp_path)
    commands: list[list[str]] = []
    emitted: list[str] = []

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Return a restart-required readiness payload."""

        _ = cwd, env, timeout_seconds
        commands.append(command)
        assert on_line is None
        return (
            2,
            (
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "dependencyReadiness": {
                            "ready": False,
                            "restartRequired": True,
                            "installedCustomNodes": ["comfyui-vectorscope-cc"],
                            "missingCustomNodes": ["SimpleSyrup"],
                        },
                        "repairResult": {
                            "installedNodes": [{"nodeId": "comfyui-vectorscope-cc"}],
                            "failedNodes": [],
                        },
                        "restartRequired": True,
                    }
                ),
            ),
        )

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )

    with pytest.raises(RuntimeError, match="Missing nodepacks: SimpleSyrup"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(
            tmp_path, on_log=emitted.append
        )

    assert len(commands) == 1
    assert not any(line.startswith("{") for line in emitted)
    assert not any("another pass" in line for line in emitted)


def test_run_sugarcubes_baseline_maintenance_installs_reported_nodepacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Setup should install nodepacks from SugarCubes' readiness plan and verify once."""

    _write_maintenance_fixture(tmp_path)
    commands: list[list[str]] = []
    installed: list[str] = []

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Require one dependency-install pass before reporting readiness."""

        _ = cwd, on_line, env, timeout_seconds
        commands.append(command)
        if len(commands) == 1:
            return (
                2,
                (
                    json.dumps(
                        {
                            "schemaVersion": 1,
                            "dependencyReadiness": {
                                "ready": False,
                                "missingCustomNodes": [
                                    "comfyui-vectorscope-cc",
                                    "seedvr2_videoupscaler",
                                    "SimpleSyrup",
                                ],
                                "installPlan": [
                                    {
                                        "nodeId": "comfyui-vectorscope-cc",
                                        "installable": True,
                                        "installed": False,
                                    },
                                    {
                                        "nodeId": "seedvr2_videoupscaler",
                                        "installable": True,
                                        "installed": False,
                                    },
                                    {
                                        "nodeId": "SimpleSyrup",
                                        "installable": True,
                                        "installed": False,
                                    },
                                ],
                            },
                            "repairResult": {"failedNodes": [], "skippedNodes": []},
                        }
                    ),
                ),
            )
        return 0, ('{"schemaVersion": 1, "dependencyReadiness": {"ready": true}}',)

    def materialize(repository_url: str, target_path: Path) -> None:
        """Record and materialize one trusted repository clone."""

        installed.append(repository_url)
        target_path.mkdir(parents=True)

    repositories = RecordingRepositoryService(clone_callback=materialize)

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )
    monkeypatch.setattr(
        sugarcubes_dependency_installer,
        "install_nodepack_requirements",
        lambda **kwargs: None,
    )

    result = sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(
        tmp_path,
        repositories=repositories,
    )

    assert result.exit_code == 0
    assert len(commands) == 2
    assert installed == [
        "https://github.com/pamparamm/ComfyUI-vectorscope-cc.git",
        "https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git",
        "https://github.com/Artificial-Sweetener/SimpleSyrup.git",
        "https://github.com/asagi4/comfyui-prompt-control.git",
    ]
    assert (tmp_path / "custom_nodes" / "seedvr2_videoupscaler").is_dir()
    assert not (tmp_path / "custom_nodes" / "ComfyUI-SeedVR2_VideoUpscaler").exists()


def test_failed_nodepack_dependencies_remove_only_the_new_app_owned_clone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed dependency transaction should leave a retryable missing nodepack."""

    _write_maintenance_fixture(tmp_path)

    def fake_stream(
        command: list[str],
        *,
        cwd: Path,
        on_line: object | None,
        env: Mapping[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[int, tuple[str, ...]]:
        """Report one trusted nodepack as missing."""

        _ = command, cwd, on_line, env, timeout_seconds
        return (
            2,
            (
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "dependencyReadiness": {
                            "ready": False,
                            "missingCustomNodes": ["seedvr2_videoupscaler"],
                            "installPlan": [
                                {
                                    "nodeId": "seedvr2_videoupscaler",
                                    "installable": True,
                                    "installed": False,
                                }
                            ],
                        },
                        "repairResult": {"failedNodes": [], "skippedNodes": []},
                    }
                ),
            ),
        )

    def materialize(_repository_url: str, target_path: Path) -> None:
        """Materialize the application-owned clone boundary."""

        target_path.mkdir(parents=True)
        (target_path / "requirements.txt").write_text("fixture", encoding="utf-8")

    def fail_requirements(**_kwargs: object) -> None:
        """Simulate a failed pip transaction after cloning succeeds."""

        raise RuntimeError("pip failed")

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "_stream_command_collecting_output",
        fake_stream,
    )
    monkeypatch.setattr(
        sugarcubes_dependency_installer,
        "install_nodepack_requirements",
        fail_requirements,
    )

    target = tmp_path / "custom_nodes" / "seedvr2_videoupscaler"
    with pytest.raises(RuntimeError, match="pip failed"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(
            tmp_path,
            repositories=RecordingRepositoryService(clone_callback=materialize),
        )

    assert not target.exists()
