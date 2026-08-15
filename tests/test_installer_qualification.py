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

"""Verify cross-process release-qualification plans and UI evidence."""

from __future__ import annotations

import json
from pathlib import Path
import ssl
import subprocess
import sys
from types import SimpleNamespace
from typing import cast
import urllib.request

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.installer_qualification import (
    InstallerQualificationDriver,
)
from sugarsubstitute_shared.installer_qualification import (
    INSTALLER_QUALIFICATION_PLAN_ENV,
    InstallerQualificationPlan,
)
from sugarsubstitute_shared.tls import EXTRA_CA_FILE_ENV, SystemTrustTlsContext
from substitute.presentation.onboarding.installer_qualification import (
    OnboardingQualificationDriver,
    qualification_preflight_action,
)
from tools.ci.historical_install_qualification import (
    _prepare_qualified_existing_managed_workspace,
    assert_historical_user_configuration_preserved,
    prepare_portable_historical_install,
    seed_historical_user_configuration,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import (
    InstalledCandidateLaunch,
    assert_qualification_event_sequence,
    launch_installed_candidate,
    prepare_qualification_evidence,
    run_current_installer_ui,
    terminate_verified_process,
    verify_main_shell_evidence,
)
from tools.ci.local_release_server import (
    LOCAL_RELEASE_BASE_URL,
    LocalReleaseServer,
)
from tools.ci.drive_windows_installer import (
    _complete_historical_onboarding,
    _wait_for_onboarding_window,
)


def test_qualification_plan_round_trips_through_environment(tmp_path: Path) -> None:
    """Installer children should inherit one exact typed qualification plan."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        force_cpu_mode=True,
    )

    restored = InstallerQualificationPlan.from_environment(
        {INSTALLER_QUALIFICATION_PLAN_ENV: plan.to_json()}
    )

    assert restored == plan


def test_legacy_qualification_plan_defaults_cpu_override_off(tmp_path: Path) -> None:
    """Older serialized plans should remain compatible without forcing CPU."""

    payload = {
        "schema_version": 2,
        "token": "qualification-token",
        "install_root": str((tmp_path / "install").resolve()),
        "endpoint_host": "127.0.0.1",
        "endpoint_port": 8188,
        "event_log_path": str((tmp_path / "events.jsonl").resolve()),
        "timeout_seconds": 45.0,
    }

    restored = InstallerQualificationPlan.from_json(json.dumps(payload))

    assert restored.force_cpu_mode is False


def test_managed_qualification_applies_explicit_cpu_choice(tmp_path: Path) -> None:
    """The production managed page should receive the platform qualification choice."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=48188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        target_mode="managed_local",
        managed_workspace_path=(tmp_path / "comfyui").resolve(),
        force_cpu_mode=True,
    )
    values: dict[str, object] = {}
    checkbox = SimpleNamespace(
        setChecked=lambda value: values.__setitem__("force_cpu", value)
    )
    window = SimpleNamespace(
        managed_local_page=SimpleNamespace(
            runtime_summary_panel=SimpleNamespace(force_cpu_checkbox=checkbox)
        )
    )
    widgets = {
        "OnboardingManagedHostEdit": SimpleNamespace(
            setText=lambda value: values.__setitem__("host", value)
        ),
        "OnboardingManagedPortSpinBox": SimpleNamespace(
            setValue=lambda value: values.__setitem__("port", value)
        ),
        "OnboardingManagedWorkspaceEdit": SimpleNamespace(
            setText=lambda value: values.__setitem__("workspace", value)
        ),
    }
    driver = cast(
        OnboardingQualificationDriver,
        SimpleNamespace(
            _plan=plan,
            _window=window,
            _wait_for_page=lambda _page: None,
            _widget=lambda _type, name: widgets[name],
        ),
    )

    OnboardingQualificationDriver._configure_managed_target(driver)

    assert values == {
        "force_cpu": True,
        "host": "127.0.0.1",
        "port": 48188,
        "workspace": str((tmp_path / "comfyui").resolve()),
    }


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


def test_local_candidate_channel_uses_trusted_https_and_exact_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Temporary non-release assets should use the launcher's real HTTPS path."""

    release_root = tmp_path / "candidate"
    release_root.mkdir()
    (release_root / "manifest.json").write_text(
        '{"version":"9999.0.1"}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    with LocalReleaseServer(
        release_root=release_root,
        certificate_root=Path("certificate"),
    ) as server:
        monkeypatch.setenv(EXTRA_CA_FILE_ENV, str(server.trust_bundle_path))
        context = SystemTrustTlsContext.create()
        with urllib.request.urlopen(
            server.manifest_url,
            timeout=5.0,
            context=context,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        legacy_context = ssl.create_default_context(
            cafile=str(server.trust_bundle_path)
        )
        with urllib.request.urlopen(
            server.manifest_url,
            timeout=5.0,
            context=legacy_context,
        ) as response:
            assert response.status == 200

        assert server.manifest_url == f"{LOCAL_RELEASE_BASE_URL}/manifest.json"
        assert payload == {"version": "9999.0.1"}
        assert server.certificate_path.is_absolute()
        assert server.trust_bundle_path.is_absolute()
        assert (
            server.trust_bundle_path.read_text(encoding="ascii").count(
                "-----BEGIN CERTIFICATE-----"
            )
            > 1
        )


def test_qualification_evidence_is_absolute_across_process_working_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every process handoff should resolve evidence against the same location."""

    monkeypatch.chdir(tmp_path)

    evidence = prepare_qualification_evidence(
        install_root=Path("installed"),
        expected_version="1.2.3",
        endpoint_port=8188,
        phase="clean",
    )
    plan = InstallerQualificationPlan.from_environment(evidence.environment)

    assert plan is not None
    assert plan.install_root == (tmp_path / "installed").resolve()
    assert plan.event_log_path == evidence.event_log_path
    assert evidence.readiness_path.is_absolute()
    assert evidence.trace_path.is_absolute()
    assert evidence.event_log_path.is_absolute()
    assert plan.target_mode == "managed_local"
    assert plan.managed_workspace_path == (tmp_path / "installed" / "comfyui")
    assert plan.managed_model_root == (tmp_path / "installed" / "qualified-models")
    assert plan.force_cpu_mode is sys.platform.startswith("linux")


def test_qualification_evidence_preserves_focused_timeout(tmp_path: Path) -> None:
    """Focused diagnostics should carry their exact total chain timeout."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        endpoint_port=8188,
        phase="clean",
        timeout_seconds=900.0,
    )

    assert evidence.plan.timeout_seconds == 900.0


def test_installed_candidate_launch_is_observed_without_capture_bound_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updater qualification should observe a process while evidence arrives."""

    install_root = tmp_path / "installed"
    layout = InstallLayout.from_root(install_root)
    layout.root.mkdir(parents=True)
    observed: dict[str, object] = {}
    fake_process = cast(
        subprocess.Popen[bytes],
        SimpleNamespace(pid=123, poll=lambda: None),
    )

    def _popen(command: list[str], **kwargs: object) -> object:
        """Capture the process contract without starting an executable."""

        observed["command"] = command
        observed.update(kwargs)
        return fake_process

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.Popen",
        _popen,
    )

    launch = launch_installed_candidate(
        install_root=install_root,
        environment={"QUALIFICATION": "1"},
    )

    assert isinstance(launch, InstalledCandidateLaunch)
    assert launch.process is fake_process
    assert observed["command"] == [str(layout.executable_path)]
    assert observed["stdout"] is observed["stderr"]
    assert observed["env"] == {"QUALIFICATION": "1"}


def test_failed_candidate_evidence_wait_terminates_only_owned_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A readiness failure must not leave the qualification launcher running."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        endpoint_port=48188,
        phase="upgrade",
    )
    fake_process = SimpleNamespace(pid=321, poll=lambda: None)
    launch = InstalledCandidateLaunch(
        process=cast(subprocess.Popen[bytes], fake_process),
        output_path=tmp_path / "candidate.log",
    )
    terminated: list[int] = []

    def _fail_wait(**_kwargs: object) -> object:
        """Fail before a token-bound child can publish readiness."""

        raise InstallerLifecycleError("readiness failed")

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification._wait_for_readiness_receipt",
        _fail_wait,
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.terminate_verified_process",
        terminated.append,
    )

    with pytest.raises(InstallerLifecycleError, match="readiness failed"):
        verify_main_shell_evidence(
            install_root=evidence.plan.install_root,
            expected_version="1.2.3",
            evidence=evidence,
            required_qualification_events=(),
            candidate_launch=launch,
        )

    assert terminated == [321]


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
    ) -> None:
        """Record real managed-setup orchestration at the external boundary."""

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
    workspace = install_root / "comfyui"
    model_root = install_root / "models"

    prepare_portable_historical_install(
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
    assert prepared_environments == [(Path.cwd().resolve(), workspace)]
    assert (install_root / "user" / "settings" / "installation.json").is_file()
    assert (install_root / "user" / "settings" / "runtime.json").is_file()
    target = json.loads(
        (install_root / "user" / "settings" / "comfy_target.json").read_text(
            encoding="utf-8"
        )
    )
    assert target["mode"] == "managed_local"
    assert target["workspace_path"] == str(workspace)


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

    monkeypatch.setattr(
        "tools.ci.historical_install_qualification.ensure_managed_workspace_manager",
        lambda *_args, **_kwargs: operations.append("manager"),
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
    assert payload["runtime_configuration"]["validation_status"] == "valid"


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


def test_historical_onboarding_reaches_open_button_and_real_main_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Historical qualification must complete onboarding instead of killing it."""

    page_controls = [
        "OnboardingInstallRootEdit",
        "OnboardingTargetCardRadio_managed_local",
        "OnboardingManagedWorkspaceEdit",
        "OnboardingManagedModelRootEdit",
        "OnboardingCivitaiApiKeyEdit",
        "OnboardingProgressStatus",
        "OnboardingCompletionSurface",
    ]
    state = {"page": 0, "main": False}
    values: dict[str, object] = {}

    class _Control:
        """Expose the UI Automation patterns used by historical qualification."""

        def __init__(self, suffix: str) -> None:
            self.suffix = suffix
            self.element_info = SimpleNamespace(automation_id=f"qt_{suffix}")

        def is_visible(self) -> bool:
            """Expose only the active page and its controls."""

            if self.suffix in page_controls:
                return self.suffix == page_controls[state["page"]]
            return True

        def is_enabled(self) -> bool:
            """Keep deterministic controls actionable."""

            return True

        def window_text(self) -> str:
            """Return terminal primary labels when qualification requires them."""

            if state["page"] == 5:
                return "Review setup"
            if state["page"] == 6:
                return "Open Substitute"
            return "Continue"

        def invoke(self) -> None:
            """Advance the production primary route or reveal the main shell."""

            if self.suffix == "OnboardingPrimaryButton":
                if state["page"] == 6:
                    state["main"] = True
                else:
                    state["page"] += 1

        def select(self) -> None:
            """Record the managed target choice."""

            values[self.suffix] = True

        def set_edit_text(self, value: str) -> None:
            """Record a production line-edit value."""

            values[self.suffix] = value

        def set_value(self, value: int) -> None:
            """Record a production numeric value."""

            values[self.suffix] = value

    controls = [
        *(_Control(control) for control in page_controls),
        _Control("OnboardingPrimaryButton"),
        _Control("OnboardingManagedHostEdit"),
        _Control("OnboardingManagedPortSpinBox"),
    ]
    onboarding = SimpleNamespace(
        element_info=SimpleNamespace(process_id=100),
        is_visible=lambda: True,
        descendants=lambda: controls,
    )
    toolbar = _Control("WorkflowChromeToolbar")
    main_window = SimpleNamespace(
        element_info=SimpleNamespace(process_id=200),
        is_visible=lambda: state["main"],
        descendants=lambda: [toolbar],
    )
    desktop = SimpleNamespace(windows=lambda: [onboarding, main_window])
    monkeypatch.setattr("tools.ci.drive_windows_installer.time.sleep", lambda _: None)

    main_pid = _complete_historical_onboarding(
        desktop=desktop,
        onboarding_pid=100,
        managed_workspace_path=tmp_path / "comfyui",
        managed_model_root=tmp_path / "models",
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        deadline=float("inf"),
    )

    assert main_pid == 200
    assert values["OnboardingTargetCardRadio_managed_local"] is True
    assert values["OnboardingManagedWorkspaceEdit"] == str(
        (tmp_path / "comfyui").resolve()
    )
    assert values["OnboardingManagedModelRootEdit"] == str(
        (tmp_path / "models").resolve()
    )


def test_verified_process_cleanup_accepts_an_already_exited_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child-exit race must not fail cleanup after the verified root is gone."""

    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.os.name",
        "nt",
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stderr=b"child already exited",
        ),
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification._windows_process_exists",
        lambda _pid: False,
    )

    terminate_verified_process(5678)


def test_upgrade_preservation_marker_requires_exact_authoritative_state(
    tmp_path: Path,
) -> None:
    """Candidate activation must preserve user configuration from history."""

    install_root = tmp_path / "SugarSubstitute"
    workspace = install_root / "comfyui"
    model_root = install_root / "models"
    marker = seed_historical_user_configuration(
        install_root=install_root,
        historical_version="0.19.0",
        managed_workspace=workspace,
        managed_model_root=model_root,
    )
    target_path = install_root / "user" / "settings" / "comfy_target.json"
    target_path.write_text(
        json.dumps(
            {
                "mode": "managed_local",
                "workspace_path": str(workspace.resolve()),
            }
        ),
        encoding="utf-8",
    )

    assert_historical_user_configuration_preserved(
        preservation_marker=marker,
        historical_version="0.19.0",
        managed_workspace=workspace,
        managed_model_root=model_root,
    )

    marker.write_text("{}", encoding="utf-8")
    with pytest.raises(InstallerLifecycleError, match="authoritative"):
        assert_historical_user_configuration_preserved(
            preservation_marker=marker,
            historical_version="0.19.0",
            managed_workspace=workspace,
            managed_model_root=model_root,
        )
