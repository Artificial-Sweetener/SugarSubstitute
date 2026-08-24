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

"""Qualify portable historical installation and update orchestration."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)
from tools.ci.historical_install_qualification import (
    _prepare_qualified_existing_managed_workspace,
    install_candidate_over_historical_install,
    prepare_portable_historical_install,
)
from tools.ci.drive_windows_installer import (
    _wait_for_onboarding_window,
)


def test_portable_historical_path_runs_the_complete_installer_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linux and macOS updates should begin from an installed historical payload."""

    commands: list[list[str]] = []
    setup_requests: list[tuple[Path, Path]] = []
    prepared_checkouts: list[tuple[Path, str]] = []
    prepared_environments: list[tuple[Path, Path]] = []

    def _run(command: list[str], **_kwargs: object) -> object:
        """Capture the native install invocation and report success."""

        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def _prepare_existing_workspace(
        *,
        workspace: Path,
        model_root: Path,
        runtime_state_dir: Path,
    ) -> None:
        """Record real managed-setup orchestration at the external boundary."""

        assert runtime_state_dir == install_root / "appdata" / "runtime_state"
        setup_requests.append((workspace, model_root))

    def _prepare_environment(repository_root: Path, workspace: Path) -> Path:
        """Record real portable-Comfy environment preparation."""

        prepared_environments.append((repository_root, workspace))
        executable = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        return workspace / ".venv" / executable

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.subprocess.run",
        _run,
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification."
        "_prepare_qualified_existing_managed_workspace",
        _prepare_existing_workspace,
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.prepare_checkout",
        lambda workspace, tag: prepared_checkouts.append((workspace, tag)),
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.prepare_environment",
        _prepare_environment,
    )
    installer = tmp_path / "candidate-installer"
    install_root = tmp_path / "installed"
    repository_root = tmp_path / "repository-root"
    workspace = install_root / "comfyui"
    model_root = install_root / "models"

    prepare_portable_historical_install(
        repository_root=repository_root,
        installer_path=installer,
        install_root=install_root,
        manifest_url="https://example.test/v0.12.2/manifest.json",
        historical_version="0.12.2",
        endpoint_port=48188,
        managed_workspace=workspace,
        managed_model_root=model_root,
        timeout_seconds=60.0,
    )

    assert commands == [
        [
            str(installer.resolve()),
            "--headless-install",
            f"--install-root={install_root.resolve()}",
            "--manifest-url=https://example.test/v0.12.2/manifest.json",
        ]
    ]
    assert setup_requests == [(workspace, model_root)]
    assert prepared_checkouts == [(workspace, "v0.28.2")]
    assert prepared_environments == [(repository_root, workspace)]
    assert (install_root / "user" / "settings" / "installation.json").is_file()
    assert (install_root / "user" / "settings" / "runtime.json").is_file()
    target = json.loads(
        (install_root / "user" / "settings" / "comfy_target.json").read_text(
            encoding="utf-8"
        )
    )
    assert target["mode"] == "managed_local"
    assert target["workspace_path"] == str(workspace)


def test_update_uses_real_candidate_installer_over_historical_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Updates must execute the candidate installer's real pipeline."""

    commands: list[list[str]] = []

    def _run(command: list[str], **_kwargs: object) -> object:
        """Capture the update invocation and report success."""

        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.subprocess.run",
        _run,
    )
    installer = tmp_path / "candidate-installer"
    install_root = tmp_path / "installed"

    install_candidate_over_historical_install(
        installer_path=installer,
        install_root=install_root,
        manifest_url="https://example.test/candidate/manifest.json",
        timeout_seconds=60.0,
        environment={"QUALIFICATION": "1"},
    )

    assert commands == [
        [
            str(installer.resolve()),
            "--headless-install",
            f"--install-root={install_root.resolve()}",
            "--manifest-url=https://example.test/candidate/manifest.json",
        ]
    ]


def test_existing_historical_runtime_is_converged_before_readiness_is_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical qualification should prove one real existing runtime in order."""

    from substitute.infrastructure.comfy.managed_environment_validator import (
        ManagedEnvironmentValidationResult,
    )
    from substitute.infrastructure.comfy.managed_setup_cache_storage import (
        prepare_managed_setup_cache,
    )

    workspace = tmp_path / "comfyui"
    model_root = tmp_path / "models"
    workspace.mkdir()
    operations: list[str] = []

    def _manager_runtime(*_args: object, **_kwargs: object) -> ComfyManagerRuntime:
        """Record provisioning and return the runtime qualified downstream."""

        operations.append("manager")
        executable = workspace / ("python.exe" if sys.platform == "win32" else "python")
        return ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=executable,
            version="4.1",
        )

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.ensure_managed_workspace_manager",
        _manager_runtime,
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.ensure_core_comfy_nodepacks",
        lambda *_args, **_kwargs: operations.append("nodepacks"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.run_sugarcubes_baseline_maintenance",
        lambda *_args, **_kwargs: operations.append("sugarcubes"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.configure_backend_model_root",
        lambda **_kwargs: operations.append("model_root"),
    )

    def _validate(**_kwargs: object) -> ManagedEnvironmentValidationResult:
        """Return real-runtime evidence at the validation boundary."""

        operations.append("validation")
        return ManagedEnvironmentValidationResult(
            success=True,
            detail="Managed workspace validation succeeded.",
            detected_backend="cpu",
            detected_torch_channel="stable",
            torch_version="2.13.0",
            device_name="cpu",
        )

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.validate_managed_environment",
        _validate,
    )

    _prepare_qualified_existing_managed_workspace(
        workspace=workspace,
        model_root=model_root,
        runtime_state_dir=tmp_path / "runtime-state",
    )

    cache = prepare_managed_setup_cache(workspace)
    try:
        payload = json.loads(cache.record_path.read_text(encoding="utf-8"))
    finally:
        cache.close()
    assert operations == [
        "manager",
        "nodepacks",
        "sugarcubes",
        "model_root",
        "validation",
    ]
    assert payload["success"] is True
    assert payload["key"]["strategy"]["source"] == ("existing_qualification_runtime")
    expected_force_cpu_mode = sys.platform != "darwin"
    assert payload["request"]["force_cpu_mode"] is expected_force_cpu_mode
    assert payload["runtime_configuration"]["force_cpu_mode"] is expected_force_cpu_mode
    assert payload["runtime_configuration"]["validation_status"] == "valid"
    persisted_runtime = json.loads(
        (tmp_path / "runtime-state" / "managed_runtime.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted_runtime["force_cpu_mode"] is expected_force_cpu_mode
    assert (
        persisted_runtime["install_target"].endswith("_cpu") or sys.platform == "darwin"
    )


def test_qualification_plan_preserves_legacy_remote_schema(tmp_path: Path) -> None:
    """Existing schema-one automation remains parseable after managed proof support."""

    raw_plan = json.dumps(
        {
            "schema_version": 1,
            "token": "legacy-token",
            "install_root": str(tmp_path / "install"),
            "endpoint_host": "127.0.0.1",
            "endpoint_port": 8188,
            "event_log_path": str(tmp_path / "events.jsonl"),
            "timeout_seconds": 45.0,
        }
    )

    restored = InstallerQualificationPlan.from_json(raw_plan)

    assert restored.target_mode == "remote"
    assert restored.managed_workspace_path is None
    assert restored.managed_model_root is None


def test_historical_onboarding_preserves_handoff_when_old_setup_lingers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lingering setup parent must not be allowed to kill handed-off onboarding."""

    terminated_pids: list[int] = []

    class _HistoricalProcess:
        """Represent an old setup that does not exit after handoff."""

        pid = 1234
        returncode: int | None = None

        def poll(self) -> int | None:
            """Keep the historical setup active."""

            return None

        def wait(self, timeout: float | None = None) -> int:
            """Expose the historical lingering-process behavior."""

            raise subprocess.TimeoutExpired(str(self.pid), timeout or 0.0)

    onboarding_window = SimpleNamespace(
        element_info=SimpleNamespace(
            automation_id="qt_OnboardingWindow",
            process_id=5678,
        ),
        is_visible=lambda: True,
    )
    desktop = SimpleNamespace(windows=lambda: [onboarding_window])
    monkeypatch.setattr(
        "tools.ci.drive_windows_installer._terminate_process_tree",
        terminated_pids.append,
    )

    onboarding_pid = _wait_for_onboarding_window(
        desktop=desktop,
        setup_window=SimpleNamespace(exists=lambda: False),
        process=_HistoricalProcess(),
        deadline=float("inf"),
    )

    assert onboarding_pid == 5678
    assert terminated_pids == []


def test_historical_installer_exercises_each_primary_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical setup should invoke every enabled primary action before handoff."""

    actions = ["Install", "Install runtime", "Open setup"]
    invoked: list[str] = []

    class _PrimaryButton:
        """Advance through the historical setup's production actions."""

        def window_text(self) -> str:
            """Return the current production action."""

            return actions[len(invoked)]

        def is_enabled(self) -> bool:
            """Keep the current phase actionable."""

            return True

        def is_visible(self) -> bool:
            """Expose the production control."""

            return True

        def invoke(self) -> None:
            """Record the real automation invocation."""

            invoked.append(self.window_text())

    class _CompletedProcess:
        """Represent a setup that exits after onboarding handoff."""

        pid = 1234
        returncode: int | None = None

        def poll(self) -> int | None:
            """Remain active during setup."""

            return None

        def wait(self, timeout: float | None = None) -> int:
            """Exit successfully after handoff."""

            self.returncode = 0
            return 0

    onboarding_window = SimpleNamespace(
        element_info=SimpleNamespace(
            automation_id="qt_OnboardingWindow",
            process_id=5678,
        ),
        is_visible=lambda: True,
    )
    desktop = SimpleNamespace(
        windows=lambda: [onboarding_window] if len(invoked) == len(actions) else []
    )
    monkeypatch.setattr(
        "tools.ci.drive_windows_installer._control_by_suffix",
        lambda _window, _suffix: _PrimaryButton(),
    )
    monkeypatch.setattr(
        "tools.ci.drive_windows_installer.time.sleep",
        lambda _seconds: None,
    )

    onboarding_pid = _wait_for_onboarding_window(
        desktop=desktop,
        setup_window=SimpleNamespace(exists=lambda: True),
        process=_CompletedProcess(),
        deadline=float("inf"),
    )

    assert onboarding_pid == 5678
    assert invoked == actions
