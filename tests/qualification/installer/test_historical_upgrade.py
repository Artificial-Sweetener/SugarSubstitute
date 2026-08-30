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
from types import SimpleNamespace
from typing import cast

import pytest

from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)
from tools.ci import historical_install_qualification
from tools.ci.drive_windows_installer import (
    _wait_for_onboarding_window,
)
from tools.ci.historical_install_qualification import (
    prepare_portable_historical_install,
)


def test_portable_historical_path_runs_the_complete_installer_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linux and macOS updates should begin from an installed historical payload."""

    commands: list[list[str]] = []
    setup_requests: list[tuple[Path, Path, float]] = []

    def _run(command: list[str], **_kwargs: object) -> object:
        """Capture the native install invocation and report success."""

        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.run_owned_process",
        _run,
    )

    def _materialize(**arguments: object) -> None:
        """Record the bounded historical managed-state handoff."""

        setup_requests.append(
            (
                cast(Path, arguments["managed_workspace"]),
                cast(Path, arguments["managed_model_root"]),
                float(cast(float, arguments["timeout_seconds"])),
            )
        )

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification."
        "materialize_historical_managed_configuration",
        _materialize,
    )
    installer = tmp_path / "candidate-installer"
    install_root = tmp_path / "installed"
    repository_root = tmp_path / "repository-root"
    workspace = install_root / "comfyui"
    model_root = install_root / "models"
    source_repository = tmp_path / "source.git"

    prepare_portable_historical_install(
        repository_root=repository_root,
        installer_path=installer,
        install_root=install_root,
        manifest_url="https://example.test/v0.12.2/manifest.json",
        historical_version="0.12.2",
        endpoint_port=48188,
        managed_workspace=workspace,
        managed_model_root=model_root,
        source_repository=source_repository,
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
    assert len(setup_requests) == 1
    assert setup_requests[0][:2] == (workspace, model_root)
    assert 0.0 < setup_requests[0][2] <= 60.0


def test_portable_historical_install_preserves_one_deadline_through_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed materialization must receive only the install budget still available."""

    observed_timeout: list[float] = []
    clock = iter((100.0, 100.0, 105.0))
    monkeypatch.setattr(
        historical_install_qualification,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
        raising=False,
    )
    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.run_owned_process",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    def _materialize(**arguments: object) -> None:
        """Capture the exact remaining budget crossing the owner boundary."""

        observed_timeout.append(float(cast(float, arguments["timeout_seconds"])))

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification."
        "materialize_historical_managed_configuration",
        _materialize,
    )

    prepare_portable_historical_install(
        repository_root=tmp_path,
        installer_path=tmp_path / "historical-installer",
        install_root=tmp_path / "installed",
        manifest_url="https://example.test/v0.12.2/manifest.json",
        historical_version="0.12.2",
        endpoint_port=48188,
        managed_workspace=tmp_path / "managed-comfy",
        managed_model_root=tmp_path / "models",
        source_repository=tmp_path / "source.git",
        timeout_seconds=60.0,
    )

    assert observed_timeout == [55.0]


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
