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

"""Qualify installed payload admission before runtime setup has completed."""

from pathlib import Path
from dataclasses import replace
import os

import pytest

from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
)
from launcher.sugarsubstitute_launcher.cli import parse_launcher_args
from launcher.sugarsubstitute_launcher.config import LauncherConfig, UpdateCheckConfig
from launcher.sugarsubstitute_launcher.installed_runtime_setup import (
    InstalledRuntimeSetup,
    pending_runtime_application,
)
from launcher.sugarsubstitute_launcher.runtime_models import (
    RuntimeCommandCancelled,
    RuntimeProvisioningResult,
)
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from launcher.sugarsubstitute_launcher.startup_plan import (
    resolve_startup_plan,
    should_launch_installed_app,
    should_show_repair,
)
from tests.launcher.installation_workflow.first_run.support import (
    write_manifest,
    write_valid_payload_zip,
)


@pytest.fixture
def incomplete_runtime(tmp_path: Path) -> InstallLayout:
    """Publish a real verified payload with only a partially created interpreter."""
    release = tmp_path / "release"
    archive = write_valid_payload_zip(release / "app.zip")
    write_manifest(release / "manifest.json", app_zip=archive)
    layout = InstallLayout.from_root(tmp_path / "installation")
    FirstRunInstaller().continue_install(
        layout=layout, release_source=LocalFolderReleaseSource(release)
    )
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_bytes(b"interpreter exists; dependencies incomplete")
    return layout


def test_unfinished_runtime_is_not_admitted_as_a_ready_application(
    incomplete_runtime: InstallLayout,
) -> None:
    """Interpreter presence cannot certify a verified application runtime."""
    plan = resolve_startup_plan(
        explicit_install_root=incomplete_runtime.root,
        executable_path=incomplete_runtime.executable_path,
    )
    assert not should_launch_installed_app(
        args=parse_launcher_args([]), startup_plan=plan
    )


def test_ordinary_launch_resumes_runtime_instead_of_generic_repair(
    incomplete_runtime: InstallLayout,
) -> None:
    """Known unfinished setup must not require downloading another release."""
    plan = resolve_startup_plan(
        explicit_install_root=incomplete_runtime.root,
        executable_path=incomplete_runtime.executable_path,
    )
    args = parse_launcher_args([])
    assert not should_show_repair(args=args, startup_plan=plan, app_launch_error=None)


class ControlledProvisioner:
    """Expose completion and interruption at the external runtime boundary."""

    def __init__(self, failure: BaseException | None = None) -> None:
        """Retain the outcome requested by the scenario."""
        self.failure = failure

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Require durable pending state before any runtime mutation starts."""
        assert LauncherConfig.load(layout.config_path).runtime_setup_pending
        if self.failure is not None:
            raise self.failure
        return RuntimeProvisioningResult(
            layout.runtime_python, layout.app_dir / "requirements.txt"
        )


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeCommandCancelled("cancelled"),
        RuntimeError("dependency failure"),
        SystemExit(73),
    ],
)
def test_runtime_failure_retains_local_resumption(
    incomplete_runtime: InstallLayout,
    failure: BaseException,
) -> None:
    """Every unsuccessful provisioning outcome must preserve unfinished setup."""
    with pytest.raises(type(failure)):
        InstalledRuntimeSetup(ControlledProvisioner(failure)).provision(
            layout=incomplete_runtime
        )
    application = pending_runtime_application(incomplete_runtime)
    assert application.layout == incomplete_runtime
    assert application.app_version == "0.4.0"
    assert LauncherConfig.load(incomplete_runtime.config_path).runtime_setup_pending


def test_verified_runtime_completion_admits_ordinary_launch(
    incomplete_runtime: InstallLayout,
) -> None:
    """Admit completed setup while preserving the configured update preferences."""
    configured = replace(
        LauncherConfig.load(incomplete_runtime.config_path),
        channel="canary",
        update_check=UpdateCheckConfig(enabled=False, frequency="daily"),
    )
    configured.save(incomplete_runtime.config_path)
    InstalledRuntimeSetup(ControlledProvisioner()).provision(layout=incomplete_runtime)
    plan = resolve_startup_plan(
        explicit_install_root=incomplete_runtime.root,
        executable_path=incomplete_runtime.executable_path,
    )
    assert should_launch_installed_app(args=parse_launcher_args([]), startup_plan=plan)
    assert LauncherConfig.load(incomplete_runtime.config_path) == replace(
        configured, runtime_setup_pending=False
    )


@pytest.mark.parametrize("value", [None, "false", 0, 1, []])
def test_ambiguous_runtime_phase_is_rejected(value: object, tmp_path: Path) -> None:
    """Malformed authoritative completion state must never masquerade as ready."""
    payload = LauncherConfig.from_layout(
        layout=InstallLayout.from_root(tmp_path)
    ).to_json()
    payload["runtime_setup_pending"] = value
    with pytest.raises(ValueError, match="boolean"):
        LauncherConfig.from_json(payload)


def test_legacy_configuration_preserves_completed_installation(tmp_path: Path) -> None:
    """A compatible existing install requires no new setup solely for migration."""
    payload = LauncherConfig.from_layout(
        layout=InstallLayout.from_root(tmp_path)
    ).to_json()
    payload.pop("runtime_setup_pending")
    assert not LauncherConfig.from_json(payload).runtime_setup_pending


def test_failed_completion_publication_preserves_resumable_configuration(
    incomplete_runtime: InstallLayout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed atomic replacement must retain the last complete configuration."""
    before = incomplete_runtime.config_path.read_bytes()

    def fail_replace(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        """Reject only the native configuration publication boundary."""
        assert Path(target) == incomplete_runtime.config_path
        raise OSError("publication unavailable")

    with monkeypatch.context() as scoped:
        scoped.setattr(os, "replace", fail_replace)
        with pytest.raises(OSError, match="publication unavailable"):
            replace(
                LauncherConfig.load(incomplete_runtime.config_path),
                runtime_setup_pending=False,
            ).save(incomplete_runtime.config_path)
    assert incomplete_runtime.config_path.read_bytes() == before
    assert LauncherConfig.load(incomplete_runtime.config_path).runtime_setup_pending


def test_failed_runtime_completion_releases_owner_for_resumption(
    incomplete_runtime: InstallLayout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain pending intent and release ownership when final publication fails."""
    save = LauncherConfig.save

    def fail_completion(config: LauncherConfig, path: Path) -> None:
        """Allow durable preparation but reject the final completion boundary."""
        if path == incomplete_runtime.config_path and not config.runtime_setup_pending:
            raise OSError("publication unavailable")
        save(config, path)

    with monkeypatch.context() as scoped:
        scoped.setattr(LauncherConfig, "save", fail_completion)
        with pytest.raises(OSError, match="publication unavailable"):
            InstalledRuntimeSetup(ControlledProvisioner()).provision(
                layout=incomplete_runtime
            )
    assert LauncherConfig.load(incomplete_runtime.config_path).runtime_setup_pending
    assert pending_runtime_application(incomplete_runtime).layout == incomplete_runtime
    InstalledRuntimeSetup(ControlledProvisioner()).provision(layout=incomplete_runtime)
    plan = resolve_startup_plan(
        explicit_install_root=incomplete_runtime.root,
        executable_path=incomplete_runtime.executable_path,
    )
    assert should_launch_installed_app(args=parse_launcher_args([]), startup_plan=plan)


def test_supervised_ui_child_receives_installed_completion_state(
    incomplete_runtime: InstallLayout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The split launcher UI must use the same installed phase as its parent."""
    from launcher.sugarsubstitute_launcher import app, launcher_window_application
    from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupPlan

    observed: list[LauncherStartupPlan] = []

    def capture_window(**kwargs: object) -> int:
        """Record the real application's decision at its GUI lifetime boundary."""
        plan = kwargs["startup_plan"]
        assert isinstance(plan, LauncherStartupPlan)
        observed.append(plan)
        return 0

    monkeypatch.setattr(
        launcher_window_application, "run_launcher_window", capture_window
    )
    assert (
        app.main(
            [
                "--launcher-ui-child",
                f"--install-root={incomplete_runtime.root}",
                "--no-update-check",
            ]
        )
        == 0
    )
    assert len(observed) == 1
    assert observed[0].installed_config_found
    assert observed[0].runtime_setup_pending


@pytest.mark.parametrize("continue_install", [False, True])
def test_pending_runtime_has_one_setup_path(
    incomplete_runtime: InstallLayout,
    monkeypatch: pytest.MonkeyPatch,
    continue_install: bool,
) -> None:
    """Resume local dependencies once without scheduling payload replacement."""
    from collections.abc import Callable, Sequence
    from threading import Event

    from launcher.sugarsubstitute_launcher.application.installation import composition
    from launcher.sugarsubstitute_launcher.application.installation.models import (
        ReleaseManifestSource,
    )
    from launcher.sugarsubstitute_launcher.application.installation.workflow import (
        InstallationWorkflow,
    )
    from launcher.sugarsubstitute_launcher.first_run import ContinuedInstallResult
    from launcher.sugarsubstitute_launcher.launcher_window_application import (
        run_launcher_window,
    )
    from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
    from tests.launcher.installation_workflow.support import (
        close_and_delete_launcher_window,
        wait_for_launcher_condition,
        workflow_factory,
    )
    from tests.launcher.support import launcher_test_application

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.localization.build_launcher_localization_runtime",
        build_launcher_localization_runtime,
    )
    application = launcher_test_application()
    payload_calls: list[InstallLayout] = []
    runtime_calls: list[InstallLayout] = []
    handoffs: list[Sequence[str]] = []

    class ObservedArtifacts(FirstRunInstaller):
        """Record unwanted release acquisition without contacting a server."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: ReleaseManifestSource
        ) -> ContinuedInstallResult:
            """Expose a duplicate payload path while allowing orderly cleanup."""
            payload_calls.append(layout)
            installed = pending_runtime_application(layout)
            return ContinuedInstallResult(
                layout, list(installed.app_command), installed.app_version
            )

    class ObservedRuntime(ControlledProvisioner):
        """Record the actual worker's runtime request."""

        def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
            """Count provisioning without changing the synthetic interpreter."""
            runtime_calls.append(layout)
            return super().provision(layout=layout)

    factory = workflow_factory(
        artifact_installer=ObservedArtifacts(),
        runtime_provisioner=ObservedRuntime(),
        process_starter=handoffs.append,
    )

    def build_workflow(
        *,
        output_callback: Callable[[str], None],
        cancellation: Event,
        admit_installation: Callable[[InstallLayout], bool],
        process_starter: Callable[[Sequence[str]], None],
    ) -> InstallationWorkflow:
        """Replace external install adapters while preserving Qt orchestration."""
        return factory(output_callback, cancellation)

    monkeypatch.setattr(composition, "build_installation_workflow", build_workflow)
    plan = resolve_startup_plan(
        explicit_install_root=incomplete_runtime.root,
        executable_path=incomplete_runtime.executable_path,
    )
    args = parse_launcher_args(
        ["--no-update-check"] + (["--continue-install"] if continue_install else [])
    )
    assert run_launcher_window(args=args, startup_plan=plan, broker=None) == 0
    windows = [
        window
        for window in application.topLevelWidgets()
        if isinstance(window, LauncherMainWindow)
    ]
    assert len(windows) == 1
    window = windows[0]
    try:
        wait_for_launcher_condition(
            application,
            lambda: (
                bool(handoffs)
                and not window.execution.initial_running
                and not window.execution.setup_running
            ),
        )
        assert payload_calls == []
        assert runtime_calls == [incomplete_runtime]
        assert len(handoffs) == 1
    finally:
        close_and_delete_launcher_window(window)
