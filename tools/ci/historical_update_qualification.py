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

"""Qualify automatic and installer-mediated historical release migrations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import sys
import time

from launcher.sugarsubstitute_launcher.config import (
    RELEASE_SOURCE_KIND_GITHUB,
    LauncherConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions
from tools.ci.candidate_release_source import (
    CandidateReleaseSource,
    candidate_release_source,
    trust_candidate_source,
)
from tools.ci.historical_install_qualification import (
    assert_historical_user_configuration_preserved,
)
from tools.ci.historical_launch_qualification import (
    assert_historical_installed_launch_contract,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import (
    InstalledCandidateLaunch,
    InstallerQualificationEvidence,
    launch_installed_candidate,
    prepare_qualification_evidence,
    verify_main_shell_evidence,
)
from tools.ci.loopback_port_lease import LoopbackPortLease
from tools.ci.managed_comfy_qualification import terminate_owned_managed_comfy
from tools.ci.owned_process_runner import run_owned_process


_POSIX_AUTOMATIC_UPDATE_BASELINE = "0.21.1"


class HistoricalUpdateRoute(Enum):
    """Identify the required migration route for one immutable launcher."""

    AUTOMATIC_LAUNCHER_UPDATE = "automatic_launcher_update"
    CANDIDATE_INSTALLER_MIGRATION = "candidate_installer_migration"


@dataclass(frozen=True, slots=True)
class HistoricalUpdateQualification:
    """Describe one exact historical installation-to-candidate migration."""

    install_root: Path
    historical_version: str
    candidate_version: str
    candidate_channel: str
    candidate_manifest_url: str | None
    candidate_release_root: Path | None
    candidate_installer_path: Path | None
    expected_update_manifest_url: str | None
    managed_workspace: Path
    managed_model_root: Path
    preservation_marker: Path
    timeout_seconds: float


def historical_update_route(
    *,
    historical_version: str,
    platform: str,
) -> HistoricalUpdateRoute:
    """Select the strongest supported migration route for a published launcher."""

    is_posix_launcher = platform.startswith("linux") or platform == "darwin"
    predates_posix_routing_fix = (
        compare_release_versions(
            historical_version,
            _POSIX_AUTOMATIC_UPDATE_BASELINE,
        )
        < 0
    )
    if is_posix_launcher and predates_posix_routing_fix:
        return HistoricalUpdateRoute.CANDIDATE_INSTALLER_MIGRATION
    return HistoricalUpdateRoute.AUTOMATIC_LAUNCHER_UPDATE


def qualify_historical_update(
    qualification: HistoricalUpdateQualification,
    *,
    endpoint_lease: LoopbackPortLease,
) -> HistoricalUpdateRoute:
    """Migrate history through its required route and prove the candidate shell."""

    deadline = time.monotonic() + qualification.timeout_seconds
    route = historical_update_route(
        historical_version=qualification.historical_version,
        platform=sys.platform,
    )
    with candidate_release_source(
        release_root=qualification.candidate_release_root,
        manifest_url=qualification.candidate_manifest_url,
        certificate_root=(qualification.install_root.parent / ".candidate-certificate"),
    ) as candidate_source:
        try:
            manifest_url = candidate_source.manifest_url
            if manifest_url is None:
                raise InstallerLifecycleError("Candidate update manifest is missing.")
            evidence = prepare_qualification_evidence(
                install_root=qualification.install_root,
                expected_version=qualification.candidate_version,
                endpoint_port=endpoint_lease.port,
                phase=f"upgrade-{qualification.historical_version}",
                timeout_seconds=_remaining_timeout(
                    deadline,
                    phase="candidate qualification setup",
                ),
            )
            trust_candidate_source(evidence.environment, candidate_source)
            if route is HistoricalUpdateRoute.AUTOMATIC_LAUNCHER_UPDATE:
                _prepare_automatic_launcher_update(
                    qualification=qualification,
                    manifest_url=manifest_url,
                )
            else:
                _install_candidate_over_historical_install(
                    qualification=qualification,
                    manifest_url=manifest_url,
                    environment=evidence.environment,
                    timeout_seconds=_remaining_timeout(
                        deadline,
                        phase="candidate installer migration",
                    ),
                )
            endpoint_lease.release_for_handoff()
            candidate_launch = launch_installed_candidate(
                install_root=qualification.install_root,
                environment=evidence.environment,
                progress_paths=(candidate_source.request_log_path,),
            )
            _verify_candidate_evidence(
                qualification=qualification,
                evidence=evidence,
                candidate_launch=candidate_launch,
                candidate_source=candidate_source,
                timeout_seconds=_remaining_timeout(
                    deadline,
                    phase="candidate main-shell readiness",
                ),
            )
            assert_installed_release_channel(
                install_root=qualification.install_root,
                expected_channel=qualification.candidate_channel,
                expected_update_manifest_url=(
                    qualification.expected_update_manifest_url or manifest_url
                ),
            )
        finally:
            terminate_owned_managed_comfy(qualification.install_root)
    return route


def _prepare_automatic_launcher_update(
    *,
    qualification: HistoricalUpdateQualification,
    manifest_url: str,
) -> None:
    """Bind a capable historical launcher to the exact candidate feed."""

    set_update_manifest(
        install_root=qualification.install_root,
        manifest_url=manifest_url,
        channel=qualification.candidate_channel,
    )
    assert_historical_installed_launch_contract(qualification.install_root)


def _install_candidate_over_historical_install(
    *,
    qualification: HistoricalUpdateQualification,
    manifest_url: str,
    environment: dict[str, str],
    timeout_seconds: float,
) -> None:
    """Use the current setup binary to migrate a launcher with broken POSIX routing."""

    installer_path = qualification.candidate_installer_path
    if installer_path is None or not installer_path.is_file():
        raise InstallerLifecycleError(
            "Legacy POSIX migration requires the exact candidate installer."
        )
    result = run_owned_process(
        [
            str(installer_path.resolve()),
            "--headless-install",
            f"--install-root={qualification.install_root.resolve()}",
            f"--manifest-url={manifest_url}",
        ],
        cwd=installer_path.resolve().parent,
        environment=environment,
        timeout_seconds=timeout_seconds,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            "Candidate installer migration failed with exit code "
            f"{result.returncode}.\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _verify_candidate_evidence(
    *,
    qualification: HistoricalUpdateQualification,
    evidence: InstallerQualificationEvidence,
    candidate_launch: InstalledCandidateLaunch | None,
    candidate_source: CandidateReleaseSource,
    timeout_seconds: float,
) -> None:
    """Require candidate readiness and exact preservation of historical state."""

    verify_main_shell_evidence(
        install_root=qualification.install_root,
        expected_version=qualification.candidate_version,
        evidence=evidence,
        required_qualification_events=(),
        require_governed_setup_record=False,
        candidate_launch=candidate_launch,
        additional_diagnostic_paths=(candidate_source.request_log_path,),
        timeout_seconds=timeout_seconds,
    )
    assert_historical_user_configuration_preserved(
        preservation_marker=qualification.preservation_marker,
        historical_version=qualification.historical_version,
        managed_workspace=qualification.managed_workspace,
        managed_model_root=qualification.managed_model_root,
    )


def set_update_manifest(
    install_root: Path,
    manifest_url: str,
    *,
    channel: str,
) -> None:
    """Point a historical installation at the exact candidate update channel."""

    layout = InstallLayout.from_root(install_root)
    payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InstallerLifecycleError("Historical launcher config is invalid.")
    payload["release_source"] = {
        "kind": RELEASE_SOURCE_KIND_GITHUB,
        "manifest_url": manifest_url,
    }
    payload["channel"] = channel
    layout.config_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assert_installed_release_channel(
    *,
    install_root: Path,
    expected_channel: str | None,
    expected_update_manifest_url: str | None,
) -> None:
    """Require a published installer to persist its authoritative update feed."""

    if expected_channel is None and expected_update_manifest_url is None:
        return
    if expected_channel is None or expected_update_manifest_url is None:
        raise InstallerLifecycleError(
            "Release-channel qualification requires both channel and manifest URL."
        )
    config = LauncherConfig.load(InstallLayout.from_root(install_root).config_path)
    if config.channel != expected_channel:
        raise InstallerLifecycleError(
            "Installed release channel mismatch: "
            f"expected {expected_channel}, got {config.channel}."
        )
    if config.release_source is None:
        raise InstallerLifecycleError("Installed release update source is missing.")
    if config.release_source.manifest_url != expected_update_manifest_url:
        raise InstallerLifecycleError(
            "Installed release manifest URL mismatch: "
            f"expected {expected_update_manifest_url}, "
            f"got {config.release_source.manifest_url}."
        )


def _remaining_timeout(deadline: float, *, phase: str) -> float:
    """Return the positive shared migration budget remaining for one phase."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InstallerLifecycleError(
            f"Historical update exhausted its timeout before {phase}."
        )
    return remaining


__all__ = [
    "HistoricalUpdateQualification",
    "HistoricalUpdateRoute",
    "assert_installed_release_channel",
    "historical_update_route",
    "qualify_historical_update",
    "set_update_manifest",
]
