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

"""Qualify packaged clean installs and historical updates through main shell."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import time
from collections.abc import Iterator, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from launcher.sugarsubstitute_launcher.config import (  # noqa: E402
    RELEASE_SOURCE_KIND_GITHUB,
    LauncherConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from sugarsubstitute_shared.tls import EXTRA_CA_FILE_ENV  # noqa: E402
from tools.ci.historical_install_qualification import (  # noqa: E402
    assert_historical_user_configuration_preserved,
    install_candidate_over_historical_install,
    prepare_portable_historical_install,
    seed_historical_user_configuration,
)
from tools.ci.historical_launch_qualification import (  # noqa: E402
    assert_historical_installed_launch_contract,
)
from tools.ci.historical_release_contract import historical_install_environment  # noqa: E402
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError  # noqa: E402
from tools.ci.installer_ui_qualification import (  # noqa: E402
    InstalledCandidateLaunch,
    InstallerQualificationEvidence,
    assert_installed_version,
    available_loopback_port,
    launch_installed_candidate,
    prepare_qualification_evidence,
    run_current_installer_ui,
    verify_main_shell_evidence,
)
from tools.ci.local_release_server import LocalReleaseServer  # noqa: E402
from tools.ci.managed_comfy_qualification import terminate_owned_managed_comfy  # noqa: E402
from tools.ci.standalone_artifact_cache import (  # noqa: E402
    qualification_standalone_artifact_cache,
)

_INSTALL_TIMEOUT_SECONDS = 3_600.0
_REQUIRED_INSTALLER_EVENTS = (
    "installer.window.ready",
    "installer.install.clicked",
    "onboarding.page.ready",
    "onboarding.target.selected",
    "onboarding.completion.ready",
    "onboarding.open_substitute.clicked",
)


@dataclass(frozen=True, slots=True)
class _CandidateReleaseSource:
    """Describe the candidate manifest and optional local trust anchor."""

    manifest_url: str | None
    certificate_path: Path | None
    request_log_path: Path | None = None


@contextmanager
def _candidate_release_source(
    *,
    release_root: Path | None,
    manifest_url: str | None,
    certificate_root: Path,
) -> Iterator[_CandidateReleaseSource]:
    """Serve temporary artifacts or retain the published manifest source."""

    if release_root is None:
        yield _CandidateReleaseSource(
            manifest_url=manifest_url,
            certificate_path=None,
        )
        return
    with LocalReleaseServer(
        release_root=release_root,
        certificate_root=certificate_root,
    ) as server:
        yield _CandidateReleaseSource(
            manifest_url=server.manifest_url,
            certificate_path=server.trust_bundle_path,
            request_log_path=server.request_log_path,
        )


def verify_clean_install(
    *,
    installer_path: Path,
    install_root: Path,
    expected_version: str,
    candidate_release_root: Path | None = None,
    managed_artifact_cache_root: Path | None = None,
    expected_channel: str | None = None,
    expected_update_manifest_url: str | None = None,
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Install and prove the completion button reveals the post-splash shell."""

    _require_empty_install_root(install_root)
    qualification_deadline = time.monotonic() + timeout_seconds
    endpoint_port = available_loopback_port()
    with qualification_standalone_artifact_cache(
        install_root=install_root,
        external_cache_root=managed_artifact_cache_root,
        timeout_seconds=timeout_seconds,
    ):
        with _candidate_release_source(
            release_root=candidate_release_root,
            manifest_url=None,
            certificate_root=install_root.parent / ".candidate-certificate",
        ) as candidate_source:
            evidence = prepare_qualification_evidence(
                install_root=install_root,
                expected_version=expected_version,
                endpoint_port=endpoint_port,
                phase="clean",
                timeout_seconds=timeout_seconds,
            )
            _trust_candidate_source(evidence.environment, candidate_source)
            try:
                run_current_installer_ui(
                    installer_path=installer_path,
                    install_root=install_root,
                    manifest_url=candidate_source.manifest_url,
                    environment=evidence.environment,
                    timeout_seconds=_remaining_qualification_timeout(
                        qualification_deadline,
                        phase="installer UI",
                    ),
                )
                verify_main_shell_evidence(
                    install_root=install_root,
                    expected_version=expected_version,
                    evidence=evidence,
                    required_qualification_events=_REQUIRED_INSTALLER_EVENTS,
                    timeout_seconds=_remaining_qualification_timeout(
                        qualification_deadline,
                        phase="main-shell readiness",
                    ),
                )
                assert_installed_release_channel(
                    install_root=install_root,
                    expected_channel=expected_channel,
                    expected_update_manifest_url=expected_update_manifest_url,
                )
            finally:
                terminate_owned_managed_comfy(install_root)
    print(f"INSTALLER_CLEAN_READY version={expected_version}", flush=True)


def verify_upgrade(
    *,
    historical_installer_path: Path,
    candidate_installer_path: Path,
    install_root: Path,
    historical_manifest_url: str,
    historical_version: str,
    historical_published_at: str,
    candidate_manifest_url: str | None,
    candidate_version: str,
    candidate_channel: str | None = None,
    expected_update_manifest_url: str | None = None,
    candidate_release_root: Path | None = None,
    historical_release_root: Path | None = None,
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Install history and reach the candidate shell through one launch action."""

    _require_empty_install_root(install_root)
    qualification_deadline = time.monotonic() + timeout_seconds
    historical_port = available_loopback_port()
    managed_workspace = install_root.resolve() / "comfyui"
    managed_model_root = install_root.resolve() / "qualified-models"
    with _candidate_release_source(
        release_root=historical_release_root,
        manifest_url=historical_manifest_url,
        certificate_root=install_root.parent / ".historical-certificate",
    ) as historical_source:
        if historical_source.manifest_url is None:
            raise InstallerLifecycleError("Historical install source is missing.")
        historical_environment = historical_install_environment(
            os.environ,
            published_at=historical_published_at,
            install_root=install_root,
        )
        _trust_candidate_source(historical_environment, historical_source)
        prepare_portable_historical_install(
            installer_path=historical_installer_path,
            install_root=install_root,
            manifest_url=historical_source.manifest_url,
            historical_version=historical_version,
            endpoint_port=historical_port,
            managed_workspace=managed_workspace,
            managed_model_root=managed_model_root,
            timeout_seconds=_remaining_qualification_timeout(
                qualification_deadline,
                phase="historical native install",
            ),
            environment=historical_environment,
        )
        assert_installed_version(install_root, historical_version)
        assert_historical_installed_launch_contract(install_root)
    preservation_marker = seed_historical_user_configuration(
        install_root=install_root,
        historical_version=historical_version,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
    )
    _verify_candidate_installer_update(
        candidate_installer_path=candidate_installer_path,
        install_root=install_root,
        historical_version=historical_version,
        candidate_version=candidate_version,
        candidate_channel=candidate_channel,
        expected_update_manifest_url=expected_update_manifest_url,
        candidate_manifest_url=candidate_manifest_url,
        candidate_release_root=candidate_release_root,
        endpoint_port=historical_port,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
        preservation_marker=preservation_marker,
        timeout_seconds=_remaining_qualification_timeout(
            qualification_deadline,
            phase="candidate update and readiness",
        ),
    )
    print(
        f"INSTALLER_UPGRADE_READY from={historical_version} to={candidate_version}",
        flush=True,
    )


def _verify_candidate_installer_update(
    *,
    candidate_installer_path: Path,
    install_root: Path,
    historical_version: str,
    candidate_version: str,
    candidate_channel: str | None = None,
    expected_update_manifest_url: str | None = None,
    candidate_manifest_url: str | None,
    candidate_release_root: Path | None,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    preservation_marker: Path,
    timeout_seconds: float,
) -> None:
    """Launch once after candidate activation and require the real main shell."""

    qualification_deadline = time.monotonic() + timeout_seconds
    with _candidate_release_source(
        release_root=candidate_release_root,
        manifest_url=candidate_manifest_url,
        certificate_root=install_root.parent / ".candidate-certificate",
    ) as candidate_source:
        try:
            evidence = prepare_qualification_evidence(
                install_root=install_root,
                expected_version=candidate_version,
                endpoint_port=endpoint_port,
                phase=f"upgrade-{historical_version}",
                timeout_seconds=_remaining_qualification_timeout(
                    qualification_deadline,
                    phase="candidate qualification setup",
                ),
            )
            _trust_candidate_source(evidence.environment, candidate_source)
            install_candidate_over_historical_install(
                installer_path=candidate_installer_path,
                install_root=install_root,
                manifest_url=candidate_source.manifest_url,
                timeout_seconds=_remaining_qualification_timeout(
                    qualification_deadline,
                    phase="candidate installer update",
                ),
                environment=evidence.environment,
            )
            assert_installed_version(install_root, candidate_version)
            assert_installed_release_channel(
                install_root=install_root,
                expected_channel=candidate_channel,
                expected_update_manifest_url=expected_update_manifest_url,
            )
            assert_historical_installed_launch_contract(install_root)
            candidate_launch = launch_installed_candidate(
                install_root=install_root,
                environment=evidence.environment,
                progress_paths=(candidate_source.request_log_path,),
            )
            _verify_candidate_evidence(
                install_root=install_root,
                historical_version=historical_version,
                candidate_version=candidate_version,
                evidence=evidence,
                candidate_launch=candidate_launch,
                candidate_source=candidate_source,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
                preservation_marker=preservation_marker,
                timeout_seconds=_remaining_qualification_timeout(
                    qualification_deadline,
                    phase="candidate main-shell readiness",
                ),
            )
        finally:
            terminate_owned_managed_comfy(install_root)


def _verify_candidate_evidence(
    *,
    install_root: Path,
    historical_version: str,
    candidate_version: str,
    evidence: InstallerQualificationEvidence,
    candidate_launch: InstalledCandidateLaunch | None,
    expected_main_pid: int | None = None,
    candidate_source: _CandidateReleaseSource,
    managed_workspace: Path,
    managed_model_root: Path,
    preservation_marker: Path,
    timeout_seconds: float,
) -> None:
    """Require candidate readiness and exact preservation of historical state."""

    verify_main_shell_evidence(
        install_root=install_root,
        expected_version=candidate_version,
        evidence=evidence,
        required_qualification_events=(),
        require_governed_setup_record=False,
        candidate_launch=candidate_launch,
        expected_main_pid=expected_main_pid,
        additional_diagnostic_paths=(candidate_source.request_log_path,),
        timeout_seconds=timeout_seconds,
    )
    assert_historical_user_configuration_preserved(
        preservation_marker=preservation_marker,
        historical_version=historical_version,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
    )


def _trust_candidate_source(
    environment: dict[str, str],
    candidate_source: _CandidateReleaseSource,
) -> None:
    """Add the temporary release certificate only to qualification children."""

    if candidate_source.certificate_path is not None:
        environment["SSL_CERT_FILE"] = str(candidate_source.certificate_path)
        environment[EXTRA_CA_FILE_ENV] = str(candidate_source.certificate_path)
        environment["UV_NATIVE_TLS"] = "1"
        environment["UV_SYSTEM_CERTS"] = "true"


def set_update_manifest(install_root: Path, manifest_url: str) -> None:
    """Point a historical installation at the exact candidate manifest."""

    layout = InstallLayout.from_root(install_root)
    payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InstallerLifecycleError("Historical launcher config is invalid.")
    payload["release_source"] = {
        "kind": RELEASE_SOURCE_KIND_GITHUB,
        "manifest_url": manifest_url,
    }
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
    layout = InstallLayout.from_root(install_root)
    config = LauncherConfig.load(layout.config_path)
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


def _require_empty_install_root(install_root: Path) -> None:
    """Reject reuse so every qualification begins from a real clean install."""

    if install_root.exists() and any(install_root.iterdir()):
        raise InstallerLifecycleError(
            f"Qualification install root is not empty: {install_root}"
        )


def _remaining_qualification_timeout(deadline: float, *, phase: str) -> float:
    """Return the remaining shared installer-chain budget for one phase."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InstallerLifecycleError(
            f"Installer qualification exhausted its total timeout before {phase}."
        )
    return remaining


def _positive_timeout(raw_value: str) -> float:
    """Parse one positive qualification timeout for argparse."""

    try:
        timeout_seconds = float(raw_value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Timeout must be a number.") from error
    if timeout_seconds <= 0:
        raise argparse.ArgumentTypeError("Timeout must be greater than zero.")
    return timeout_seconds


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse clean-install or upgrade verification arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    clean = subparsers.add_parser("clean")
    clean.add_argument("--installer", type=Path, required=True)
    clean.add_argument("--install-root", type=Path, required=True)
    clean.add_argument("--expected-version", required=True)
    clean.add_argument("--candidate-release-root", type=Path)
    clean.add_argument("--managed-artifact-cache-root", type=Path)
    clean.add_argument("--expected-channel")
    clean.add_argument("--expected-update-manifest-url")
    clean.add_argument(
        "--timeout-seconds",
        type=_positive_timeout,
        default=_INSTALL_TIMEOUT_SECONDS,
    )
    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("--historical-installer", type=Path, required=True)
    upgrade.add_argument("--candidate-installer", type=Path, required=True)
    upgrade.add_argument("--install-root", type=Path, required=True)
    upgrade.add_argument("--historical-manifest-url", required=True)
    upgrade.add_argument("--historical-release-root", type=Path)
    upgrade.add_argument("--historical-version", required=True)
    upgrade.add_argument("--historical-published-at", required=True)
    upgrade.add_argument("--candidate-manifest-url")
    upgrade.add_argument("--candidate-release-root", type=Path)
    upgrade.add_argument("--candidate-version", required=True)
    upgrade.add_argument("--candidate-channel")
    upgrade.add_argument("--expected-update-manifest-url")
    upgrade.add_argument(
        "--timeout-seconds",
        type=_positive_timeout,
        default=_INSTALL_TIMEOUT_SECONDS,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one requested installer lifecycle qualification."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "clean":
        verify_clean_install(
            installer_path=args.installer,
            install_root=args.install_root,
            expected_version=args.expected_version,
            candidate_release_root=args.candidate_release_root,
            managed_artifact_cache_root=args.managed_artifact_cache_root,
            expected_channel=args.expected_channel,
            expected_update_manifest_url=args.expected_update_manifest_url,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        verify_upgrade(
            historical_installer_path=args.historical_installer,
            candidate_installer_path=args.candidate_installer,
            install_root=args.install_root,
            historical_manifest_url=args.historical_manifest_url,
            historical_version=args.historical_version,
            historical_published_at=args.historical_published_at,
            historical_release_root=args.historical_release_root,
            candidate_manifest_url=args.candidate_manifest_url,
            candidate_version=args.candidate_version,
            candidate_channel=args.candidate_channel,
            expected_update_manifest_url=args.expected_update_manifest_url,
            candidate_release_root=args.candidate_release_root,
            timeout_seconds=args.timeout_seconds,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
