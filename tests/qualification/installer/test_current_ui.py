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

"""Qualify current installer UI actions and bounded failure evidence."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import cast
import urllib.request

import pytest

from launcher.sugarsubstitute_launcher.ui.installer_qualification import (
    InstallerQualificationDriver,
)
from launcher.sugarsubstitute_launcher.ui import experience_pages
from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)
from substitute.presentation.onboarding.installer_qualification import (
    qualification_preflight_action,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import (
    assert_qualification_event_sequence,
    prepare_qualification_evidence,
    run_current_installer_ui,
)
from tools.ci.verify_installer_lifecycle import verify_clean_install


def test_qualification_event_sequence_requires_real_ui_actions(tmp_path: Path) -> None:
    """Lifecycle evidence should require ordered Install and Open button clicks."""

    event_log_path = tmp_path / "events.jsonl"
    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=event_log_path,
        timeout_seconds=45.0,
    )
    required_events = (
        "installer.window.ready",
        "installer.install.clicked",
        "onboarding.open_substitute.clicked",
    )
    for event in required_events:
        plan.record(event)

    assert_qualification_event_sequence(
        event_log_path,
        token=plan.token,
        required_events=required_events,
    )


def test_current_onboarding_driver_advances_the_real_welcome_page() -> None:
    """Release qualification must not wait past the first installed page."""

    assert (
        qualification_preflight_action(
            current_page="OnboardingWelcomePage",
            primary_enabled=True,
            welcome_continued=False,
        )
        == "continue_welcome"
    )


def test_installer_qualification_fails_fast_when_runtime_setup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed production phase should terminate CI with actionable evidence."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
    )
    exit_codes: list[int] = []
    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.installer_qualification."
        "QCoreApplication.exit",
        exit_codes.append,
    )
    driver = cast(
        InstallerQualificationDriver,
        SimpleNamespace(_plan=plan),
    )

    InstallerQualificationDriver._record_installation_failure(
        driver,
        phase="runtime_setup",
        reason="dependency_install_failed",
        details="pip exited with status 1",
    )

    event = json.loads(plan.event_log_path.read_text(encoding="utf-8"))
    assert event["event"] == "installer.qualification.failed"
    assert event["fields"] == {
        "details": "pip exited with status 1",
        "phase": "runtime_setup",
        "reason": "dependency_install_failed",
    }
    assert exit_codes == [1]
    assert (
        qualification_preflight_action(
            current_page="OnboardingTargetModePage",
            primary_enabled=True,
            welcome_continued=True,
        )
        == "drive_onboarding"
    )


def test_installer_qualification_has_no_launcher_model_setup_stage() -> None:
    """Keep model choices out of launcher UI and launcher qualification."""

    assert not hasattr(experience_pages, "ModelInterestPage")
    assert not hasattr(InstallerQualificationDriver, "_skip_optional_model_setup")


def test_qualification_event_sequence_rejects_missing_install_click(
    tmp_path: Path,
) -> None:
    """A main-window receipt cannot conceal a bypassed installer action."""

    event_log_path = tmp_path / "events.jsonl"
    event_log_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "token": "qualification-token",
                "event": "onboarding.open_substitute.clicked",
                "pid": 1,
                "fields": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(InstallerLifecycleError, match="interaction sequence"):
        assert_qualification_event_sequence(
            event_log_path,
            token="qualification-token",
            required_events=(
                "installer.install.clicked",
                "onboarding.open_substitute.clicked",
            ),
        )


def test_current_qualification_launches_normal_installer_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate qualification must never invoke the headless install bypass."""

    captured_command: list[str] = []
    captured_kwargs: dict[str, object] = {}

    def _run(command: list[str], **kwargs: object) -> object:
        """Capture the packaged installer command and report success."""

        captured_command.extend(command)
        captured_kwargs.update(kwargs)
        return type(
            "CompletedInstaller",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )()

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.run",
        _run,
    )
    installer = tmp_path / "SugarSubstitute Setup.exe"
    install_root = tmp_path / "installed"

    run_current_installer_ui(
        installer_path=installer,
        install_root=install_root,
        manifest_url=None,
        environment={},
    )

    assert captured_command == [
        str(installer.resolve()),
        f"--install-root={install_root.resolve()}",
    ]
    assert "--headless-install" not in captured_command
    assert captured_kwargs["timeout"] == 3_600.0


def test_clean_qualification_uses_live_external_comfy_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clean setup must select and probe a continuously owned remote target."""

    def install_with_external_probe(**arguments: object) -> None:
        """Model installed onboarding against the supplied external endpoint."""

        environment = cast(dict[str, str], arguments["environment"])
        plan = InstallerQualificationPlan.from_environment(environment)
        assert plan is not None
        assert plan.target_mode == "remote"
        assert plan.managed_workspace_path is None
        assert plan.managed_model_root is None
        assert plan.force_cpu_mode is False
        with urllib.request.urlopen(
            f"http://{plan.endpoint_host}:{plan.endpoint_port}/system_stats",
            timeout=5.0,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["system"]["comfyui_version"] == (
            "installer-qualification-boundary"
        )
        with urllib.request.urlopen(
            f"http://{plan.endpoint_host}:{plan.endpoint_port}"
            "/substitute/v1/capabilities",
            timeout=5.0,
        ) as response:
            capabilities = json.loads(response.read().decode("utf-8"))
        assert capabilities["apiVersion"] == 1

    monkeypatch.setattr(
        "tools.ci.verify_installer_lifecycle.run_current_installer_ui",
        install_with_external_probe,
    )
    monkeypatch.setattr(
        "tools.ci.verify_installer_lifecycle.verify_main_shell_evidence",
        lambda **_arguments: None,
    )
    verify_clean_install(
        installer_path=tmp_path / "installer",
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        timeout_seconds=120.0,
    )


def test_timed_out_current_installer_reports_process_bound_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bounded setup timeout must report durable events before CI kills the job."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        endpoint_port=48188,
        phase="clean",
        timeout_seconds=900.0,
    )
    evidence.plan.record("onboarding.install.started", operation="managed_comfy")

    def _timeout(command: list[str], **kwargs: object) -> object:
        """Simulate setup exceeding the shared focused timeout."""

        raise subprocess.TimeoutExpired(
            command,
            cast(float, kwargs["timeout"]),
            output="partial setup output",
        )

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.run",
        _timeout,
    )

    with pytest.raises(InstallerLifecycleError) as captured:
        run_current_installer_ui(
            installer_path=tmp_path / "installer",
            install_root=evidence.plan.install_root,
            manifest_url="https://example.test/manifest.json",
            environment=evidence.environment,
            timeout_seconds=900.0,
        )

    message = str(captured.value)
    assert "did not complete within 900 seconds" in message
    assert "partial setup output" in message
    assert "onboarding.install.started" in message


def test_failed_current_installer_reports_process_bound_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A packaged installer failure must expose its UI event and launcher logs."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        endpoint_port=48188,
        phase="clean",
    )
    evidence.plan.record(
        "installer.qualification.failed",
        phase="initial_install",
        details="archive rejected",
    )
    launcher_log = evidence.plan.install_root / "launcher" / "logs" / "launcher.log"
    launcher_log.parent.mkdir(parents=True, exist_ok=True)
    launcher_log.write_text("launcher rejected archive\n", encoding="utf-8")

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="installer output",
            stderr="installer error",
        ),
    )

    with pytest.raises(InstallerLifecycleError) as captured:
        run_current_installer_ui(
            installer_path=tmp_path / "installer",
            install_root=evidence.plan.install_root,
            manifest_url="https://example.test/manifest.json",
            environment=evidence.environment,
        )

    message = str(captured.value)
    assert "installer.qualification.failed" in message
    assert "archive rejected" in message
    assert "launcher rejected archive" in message
