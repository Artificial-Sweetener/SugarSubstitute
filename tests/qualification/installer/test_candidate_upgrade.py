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

"""Qualify candidate installer update orchestration and readiness ownership."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import cast

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci import installer_ui_qualification
from tools.ci.candidate_release_source import CandidateReleaseSource
from tools.ci.historical_update_qualification import (
    HistoricalUpdateQualification,
    _verify_candidate_evidence,
    qualify_historical_update,
)
from tools.ci.installer_ui_qualification import (
    InstalledCandidateLaunch,
    prepare_qualification_evidence,
    verify_main_shell_evidence,
)
from tools.ci.loopback_port_lease import LoopbackPortLease
from tools.ci.verify_installer_lifecycle import (
    _parse_args,
)


def test_upgrade_cli_accepts_one_shared_installer_chain_timeout() -> None:
    """Focused update qualification must bound history and candidate readiness."""

    arguments = _parse_args(
        [
            "upgrade",
            "--historical-installer",
            "historical-installer",
            "--install-root",
            "installed",
            "--historical-manifest-url",
            "https://example.test/history.json",
            "--historical-version",
            "0.20.1",
            "--historical-published-at",
            "2026-08-12T00:27:36Z",
            "--source-cache",
            "source-cache",
            "--candidate-manifest-url",
            "https://example.test/candidate.json",
            "--candidate-installer",
            "candidate-installer",
            "--candidate-version",
            "9999.0.93",
            "--candidate-channel",
            "canary",
            "--timeout-seconds",
            "1200",
        ]
    )

    assert arguments.timeout_seconds == 1200.0
    assert arguments.source_cache == Path("source-cache")
    assert arguments.candidate_installer == Path("candidate-installer")


def test_candidate_update_uses_historical_launcher_before_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Qualification must let the historical launcher consume the candidate feed."""

    install_root = tmp_path / "installed"
    layout = InstallLayout.from_root(install_root)
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    events: list[tuple[str, str]] = []

    def launch_once(
        *,
        install_root: Path,
        environment: dict[str, str],
        progress_paths: tuple[Path | None, ...],
    ) -> object:
        """Record the manifest visible to the only installed launch."""

        del environment, progress_paths
        payload = json.loads(
            InstallLayout.from_root(install_root).config_path.read_text(
                encoding="utf-8"
            )
        )
        events.append(("launch", payload["release_source"]["manifest_url"]))
        return object()

    def verify_candidate(**arguments: object) -> None:
        """Record that readiness follows the single candidate-bound launch."""

        del arguments
        events.append(("verify", "9999.0.109"))

    monkeypatch.setattr(
        "tools.ci.historical_update_qualification."
        "assert_historical_installed_launch_contract",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.launch_installed_candidate",
        launch_once,
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification._verify_candidate_evidence",
        verify_candidate,
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.terminate_owned_managed_comfy",
        lambda _install_root: None,
    )

    with LoopbackPortLease.acquire() as endpoint_lease:
        qualify_historical_update(
            HistoricalUpdateQualification(
                install_root=install_root,
                historical_version="0.20.1",
                candidate_version="9999.0.109",
                candidate_manifest_url="https://example.test/candidate.json",
                candidate_release_root=None,
                candidate_installer_path=None,
                candidate_channel="canary",
                expected_update_manifest_url=None,
                managed_workspace=install_root / "comfyui",
                managed_model_root=install_root / "qualified-models",
                preservation_marker=(
                    install_root / "user" / "settings" / "marker.json"
                ),
                timeout_seconds=30.0,
            ),
            endpoint_lease=endpoint_lease,
        )

    assert events == [
        ("launch", "https://example.test/candidate.json"),
        ("verify", "9999.0.109"),
    ]


def test_candidate_evidence_requires_real_managed_comfy_before_preservation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Historical update proof must retain real managed-runtime verification."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="9999.0.109",
        endpoint_port=24567,
        phase="upgrade-0.20.1",
    )
    events: list[str] = []

    def require_live_shell(**arguments: object) -> None:
        """Record the exact managed evidence requested while the shell is live."""

        assert arguments["install_root"] == tmp_path / "installed"
        assert arguments["evidence"] is evidence
        assert arguments["require_governed_setup_record"] is False
        events.append("live-managed-shell")

    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.verify_main_shell_evidence",
        require_live_shell,
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification."
        "assert_historical_user_configuration_preserved",
        lambda **_arguments: events.append("preservation"),
    )

    qualification = HistoricalUpdateQualification(
        install_root=tmp_path / "installed",
        historical_version="0.20.1",
        candidate_version="9999.0.109",
        candidate_channel="canary",
        candidate_manifest_url="https://example.test/candidate.json",
        candidate_release_root=None,
        candidate_installer_path=None,
        expected_update_manifest_url=None,
        managed_workspace=tmp_path / "installed" / "comfyui",
        managed_model_root=tmp_path / "installed" / "qualified-models",
        preservation_marker=tmp_path / "installed" / "marker.json",
        timeout_seconds=30.0,
    )
    _verify_candidate_evidence(
        qualification=qualification,
        evidence=evidence,
        candidate_launch=None,
        candidate_source=CandidateReleaseSource(
            manifest_url="https://example.test/candidate.json",
            certificate_path=None,
        ),
        timeout_seconds=30.0,
    )

    assert events == ["live-managed-shell", "preservation"]


def test_managed_backend_is_verified_before_live_shell_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed HTTP proof must finish before its installed process is stopped."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="9999.0.109",
        endpoint_port=24567,
        phase="upgrade-0.20.1",
    )
    receipt = ApplicationReadinessReceipt(
        pid=456,
        parent_pid=123,
        token=evidence.token,
        surface=ApplicationReadinessSurface.MAIN_SHELL,
    )
    events: list[str] = []
    monkeypatch.setattr(
        installer_ui_qualification,
        "_wait_for_readiness_receipt",
        lambda **_arguments: receipt,
    )
    monkeypatch.setattr(
        installer_ui_qualification,
        "wait_for_installed_version",
        lambda **_arguments: events.append("version"),
    )
    monkeypatch.setattr(
        installer_ui_qualification,
        "assert_startup_trace_sequence",
        lambda *_arguments: events.append("trace"),
    )

    def require_managed(**arguments: object) -> None:
        """Record the live managed-runtime proof and its update policy."""

        assert arguments["require_governed_setup_record"] is False
        events.append("managed-comfy")

    monkeypatch.setattr(
        installer_ui_qualification,
        "assert_real_managed_comfy",
        require_managed,
    )
    monkeypatch.setattr(
        installer_ui_qualification,
        "terminate_verified_process",
        lambda pid: events.append(f"terminate:{pid}"),
    )

    verify_main_shell_evidence(
        install_root=tmp_path / "installed",
        expected_version="9999.0.109",
        evidence=evidence,
        required_qualification_events=(),
        require_governed_setup_record=False,
    )

    assert events == ["version", "trace", "managed-comfy", "terminate:456"]


def test_stalled_installed_launcher_fails_at_progress_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A launcher that never enters update or app handoff must fail promptly."""

    progress_path = tmp_path / "launcher.log"
    process = cast(
        subprocess.Popen[bytes],
        SimpleNamespace(pid=123, poll=lambda: None),
    )
    clock = iter((0.0, 121.0))
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.time.monotonic",
        lambda: next(clock),
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.process_tree_diagnostics",
        lambda pid: f"pid={pid}",
    )

    with pytest.raises(
        InstallerLifecycleError,
        match="within 120 seconds",
    ) as captured:
        installer_ui_qualification._wait_for_readiness_receipt(
            readiness_path=tmp_path / "readiness.json",
            token="qualification-token",
            timeout_seconds=300.0,
            candidate_launch=InstalledCandidateLaunch(
                process=process,
                output_path=tmp_path / "candidate.log",
                progress_baselines=((progress_path, (False, 0)),),
            ),
            diagnostic_paths=(progress_path,),
        )

    assert "process tree:\npid=123" in str(captured.value)


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


def test_completion_action_pid_must_match_readiness_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A visible unrelated process cannot satisfy the completion-button proof."""

    evidence = prepare_qualification_evidence(
        install_root=tmp_path / "installed",
        expected_version="1.2.3",
        endpoint_port=48188,
        phase="upgrade",
    )
    receipt = ApplicationReadinessReceipt(
        pid=456,
        parent_pid=123,
        token=evidence.token,
        surface=ApplicationReadinessSurface.MAIN_SHELL,
    )
    terminated: list[int] = []
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification._wait_for_readiness_receipt",
        lambda **_arguments: receipt,
    )
    monkeypatch.setattr(
        "tools.ci.installer_ui_qualification.terminate_verified_process",
        terminated.append,
    )

    with pytest.raises(InstallerLifecycleError, match="different main-shell"):
        verify_main_shell_evidence(
            install_root=evidence.plan.install_root,
            expected_version="1.2.3",
            evidence=evidence,
            required_qualification_events=(),
            expected_main_pid=123,
        )

    assert terminated == [456]
