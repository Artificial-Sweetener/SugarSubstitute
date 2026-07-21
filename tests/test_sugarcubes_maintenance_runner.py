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

"""Tests for SugarCubes maintenance runner orchestration."""

from __future__ import annotations

import ast
from collections.abc import Mapping
import json
import os
from pathlib import Path

import pytest

from substitute.infrastructure.comfy import nodepack_reconciliation
from substitute.infrastructure.comfy import sugarcubes_maintenance_runner
from tests.repository_service_test_double import RecordingRepositoryService


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


@pytest.fixture(autouse=True)
def _prepare_repositories_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep maintenance parser tests isolated from repository provisioning."""

    monkeypatch.setattr(
        sugarcubes_maintenance_runner,
        "prepare_sugarcubes_repositories",
        lambda *args, **kwargs: None,
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
            "backend.maintenance",
            "cube-deps",
            "preflight",
            "--workspace",
            str(tmp_path),
            "--baseline-only",
        ]
    ]
    assert result.exit_code == 0
    assert result.diagnostics == ()


def test_run_sugarcubes_baseline_maintenance_supports_packaged_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Maintenance should derive the current packaged module from its files."""

    python_path = _write_maintenance_fixture(tmp_path, packaged=True)
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

    sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)

    assert commands[0][:3] == [str(python_path), "-m", "sugarcubes.maintenance"]


def test_nodepack_reconciliation_facade_exports_sugarcubes_maintenance() -> None:
    """The public reconciliation facade should expose the runner entry point."""

    assert (
        nodepack_reconciliation.run_sugarcubes_baseline_maintenance
        is sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance
    )


def test_run_sugarcubes_baseline_maintenance_exit_two_raises_with_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Required SugarCubes dependency issues should block setup."""

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

    with pytest.raises(RuntimeError, match="required Base-Cubes dependencies"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(
            tmp_path, on_log=emitted.append
        )

    assert any(
        line.startswith("WARNING: SugarCubes[base_cubes_sync_failed]")
        for line in emitted
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
        sugarcubes_maintenance_runner,
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
        sugarcubes_maintenance_runner,
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


def test_sugarcubes_installable_missing_node_ids_filters_readiness_plan() -> None:
    """Install planning should only return missing, installable, uninstalled nodes."""

    assert sugarcubes_maintenance_runner._sugarcubes_installable_missing_node_ids(
        {
            "dependencyReadiness": {
                "ready": False,
                "missingCustomNodes": ["SimpleSyrup", "uninstallable"],
                "installPlan": [
                    {
                        "nodeId": "SimpleSyrup",
                        "installable": True,
                        "installed": False,
                    },
                    {
                        "nodeId": "already-installed",
                        "installable": True,
                        "installed": True,
                    },
                    {
                        "nodeId": "uninstallable",
                        "installable": False,
                        "installed": False,
                    },
                    {
                        "nodeId": "not-missing",
                        "installable": True,
                        "installed": False,
                    },
                ],
            }
        }
    ) == ("SimpleSyrup",)


def test_sugarcubes_installable_missing_node_ids_falls_back_to_failed_nodes() -> None:
    """Legacy repair payloads should still identify failed missing node installs."""

    assert sugarcubes_maintenance_runner._sugarcubes_installable_missing_node_ids(
        {
            "dependencyReadiness": {
                "ready": False,
                "missingCustomNodes": ["SimpleSyrup"],
            },
            "repairResult": {
                "failedNodes": [
                    {"nodeId": "SimpleSyrup"},
                    {"nodeId": "not-missing"},
                ]
            },
        }
    ) == ("SimpleSyrup",)


def test_run_sugarcubes_baseline_maintenance_requires_entrypoint(
    tmp_path: Path,
) -> None:
    """A missing SugarCubes maintenance module should remain a structural failure."""

    python_path = _workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="entrypoint is missing"):
        sugarcubes_maintenance_runner.run_sugarcubes_baseline_maintenance(tmp_path)


def _write_maintenance_fixture(workspace: Path, *, packaged: bool = False) -> Path:
    """Create the minimum workspace files required by maintenance startup."""

    python_path = _workspace_python_path(workspace)
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    maintenance_package = Path("sugarcubes") if packaged else Path("backend")
    backend_package = Path("sugarcubes/backend") if packaged else Path("backend")
    sugarcubes_root = workspace / "custom_nodes" / "SugarCubes"
    maintenance_path = sugarcubes_root / maintenance_package / "maintenance.py"
    maintenance_path.parent.mkdir(parents=True)
    maintenance_path.write_text("", encoding="utf-8")
    backend_path = sugarcubes_root / backend_package / "__init__.py"
    backend_path.parent.mkdir(parents=True, exist_ok=True)
    backend_path.write_text("", encoding="utf-8")
    return python_path


def _workspace_python_path(workspace: Path) -> Path:
    """Return the host-native managed Python path for a Comfy workspace."""

    relative_path = (
        Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    )
    return workspace / ".venv" / relative_path


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
