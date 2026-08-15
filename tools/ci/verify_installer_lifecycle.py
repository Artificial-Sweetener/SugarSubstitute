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
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from sugarsubstitute_shared.installer_qualification import (  # noqa: E402
    InstallerQualificationPlan,
)
from sugarsubstitute_shared.tls import EXTRA_CA_FILE_ENV  # noqa: E402
from tools.ci.drive_windows_installer import drive_windows_installer  # noqa: E402
from tools.ci.historical_install_qualification import (  # noqa: E402
    assert_historical_user_configuration_preserved,
    prepare_portable_historical_install,
    seed_historical_user_configuration,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError  # noqa: E402
from tools.ci.installer_ui_qualification import (  # noqa: E402
    assert_installed_version,
    available_loopback_port,
    launch_installed_candidate,
    prepare_qualification_evidence,
    run_current_installer_ui,
    terminate_verified_process,
    verify_main_shell_evidence,
)
from tools.ci.local_release_server import LocalReleaseServer  # noqa: E402
from tools.ci.managed_comfy_qualification import (  # noqa: E402
    assert_real_managed_comfy,
    terminate_owned_managed_comfy,
)
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
        )


def verify_clean_install(
    *,
    installer_path: Path,
    install_root: Path,
    expected_version: str,
    candidate_release_root: Path | None = None,
    managed_artifact_cache_root: Path | None = None,
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Install and prove the completion button reveals the post-splash shell."""

    _require_empty_install_root(install_root)
    qualification_deadline = time.monotonic() + timeout_seconds
    endpoint_port = available_loopback_port()
    with qualification_standalone_artifact_cache(
        install_root=install_root,
        external_cache_root=managed_artifact_cache_root,
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
            finally:
                terminate_owned_managed_comfy(install_root)
    print(f"INSTALLER_CLEAN_READY version={expected_version}", flush=True)


def verify_upgrade(
    *,
    historical_installer_path: Path,
    install_root: Path,
    historical_manifest_url: str,
    historical_version: str,
    candidate_manifest_url: str | None,
    candidate_version: str,
    candidate_release_root: Path | None = None,
    historical_release_root: Path | None = None,
) -> None:
    """Install one historical release, update it, and prove candidate readiness."""

    _require_empty_install_root(install_root)
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
        historical_environment = dict(os.environ)
        _trust_candidate_source(historical_environment, historical_source)
        if os.name == "nt":
            _complete_windows_historical_install(
                installer_path=historical_installer_path,
                install_root=install_root,
                manifest_url=historical_source.manifest_url,
                historical_version=historical_version,
                endpoint_port=historical_port,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
            )
        else:
            prepare_portable_historical_install(
                installer_path=historical_installer_path,
                install_root=install_root,
                manifest_url=historical_source.manifest_url,
                historical_version=historical_version,
                endpoint_port=historical_port,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
                timeout_seconds=_INSTALL_TIMEOUT_SECONDS,
                environment=historical_environment,
            )
            assert_installed_version(install_root, historical_version)
    preservation_marker = seed_historical_user_configuration(
        install_root=install_root,
        historical_version=historical_version,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
    )
    _activate_and_verify_candidate_update(
        install_root=install_root,
        historical_version=historical_version,
        candidate_version=candidate_version,
        candidate_manifest_url=candidate_manifest_url,
        candidate_release_root=candidate_release_root,
        endpoint_port=historical_port,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
        preservation_marker=preservation_marker,
    )
    print(
        f"INSTALLER_UPGRADE_READY from={historical_version} to={candidate_version}",
        flush=True,
    )


def _complete_windows_historical_install(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str,
    historical_version: str,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
) -> None:
    """Drive Windows historical setup through Open Substitute and real shell."""

    main_pid = drive_windows_installer(
        installer_path=installer_path,
        install_root=install_root,
        manifest_url=manifest_url,
        timeout_seconds=_INSTALL_TIMEOUT_SECONDS,
        managed_workspace_path=managed_workspace,
        managed_model_root=managed_model_root,
        endpoint_host="127.0.0.1",
        endpoint_port=endpoint_port,
    )
    try:
        assert_installed_version(install_root, historical_version)
        assert_real_managed_comfy(
            install_root=install_root,
            plan=_managed_plan(
                install_root=install_root,
                version=historical_version,
                endpoint_port=endpoint_port,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
            ),
            require_current_nodepack_versions=False,
            require_governed_setup_record=False,
        )
        print(
            "HISTORICAL_INSTALLER_MAIN_READY "
            f"version={historical_version} main_pid={main_pid}",
            flush=True,
        )
    finally:
        terminate_verified_process(main_pid)


def _activate_and_verify_candidate_update(
    *,
    install_root: Path,
    historical_version: str,
    candidate_version: str,
    candidate_manifest_url: str | None,
    candidate_release_root: Path | None,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    preservation_marker: Path,
) -> None:
    """Run the installed updater and require the candidate's real main shell."""

    with _candidate_release_source(
        release_root=candidate_release_root,
        manifest_url=candidate_manifest_url,
        certificate_root=install_root.parent / ".candidate-certificate",
    ) as candidate_source:
        if candidate_source.manifest_url is None:
            raise InstallerLifecycleError("Candidate update source is missing.")
        set_update_manifest(install_root, candidate_source.manifest_url)
        try:
            evidence = prepare_qualification_evidence(
                install_root=install_root,
                expected_version=candidate_version,
                endpoint_port=endpoint_port,
                phase=f"upgrade-{historical_version}",
            )
            _trust_candidate_source(evidence.environment, candidate_source)
            candidate_launch = launch_installed_candidate(
                install_root=install_root,
                environment=evidence.environment,
            )
            verify_main_shell_evidence(
                install_root=install_root,
                expected_version=candidate_version,
                evidence=evidence,
                required_qualification_events=(),
                require_governed_setup_record=False,
                candidate_launch=candidate_launch,
            )
            assert_historical_user_configuration_preserved(
                preservation_marker=preservation_marker,
                historical_version=historical_version,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
            )
        finally:
            terminate_owned_managed_comfy(install_root)


def _managed_plan(
    *,
    install_root: Path,
    version: str,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
) -> InstallerQualificationPlan:
    """Describe one installed managed target for live qualification."""

    return InstallerQualificationPlan(
        token=f"historical-{version}",
        install_root=install_root.resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=endpoint_port,
        event_log_path=install_root.resolve() / "historical-events.jsonl",
        timeout_seconds=_INSTALL_TIMEOUT_SECONDS,
        target_mode="managed_local",
        managed_workspace_path=managed_workspace,
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
    clean.add_argument(
        "--timeout-seconds",
        type=_positive_timeout,
        default=_INSTALL_TIMEOUT_SECONDS,
    )
    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("--historical-installer", type=Path, required=True)
    upgrade.add_argument("--install-root", type=Path, required=True)
    upgrade.add_argument("--historical-manifest-url", required=True)
    upgrade.add_argument("--historical-release-root", type=Path)
    upgrade.add_argument("--historical-version", required=True)
    upgrade.add_argument("--candidate-manifest-url")
    upgrade.add_argument("--candidate-release-root", type=Path)
    upgrade.add_argument("--candidate-version", required=True)
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
            timeout_seconds=args.timeout_seconds,
        )
    else:
        verify_upgrade(
            historical_installer_path=args.historical_installer,
            install_root=args.install_root,
            historical_manifest_url=args.historical_manifest_url,
            historical_version=args.historical_version,
            historical_release_root=args.historical_release_root,
            candidate_manifest_url=args.candidate_manifest_url,
            candidate_version=args.candidate_version,
            candidate_release_root=args.candidate_release_root,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
