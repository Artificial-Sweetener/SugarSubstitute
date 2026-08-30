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
import os
from pathlib import Path
import sys
import time
from collections.abc import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.ci.candidate_release_source import (  # noqa: E402
    candidate_release_source,
    trust_candidate_source,
)
from tools.ci.comfy_source_cache import (  # noqa: E402
    require_comfy_source_repository,
)
from tools.ci.historical_install_qualification import (  # noqa: E402
    prepare_portable_historical_install,
    seed_historical_user_configuration,
)
from tools.ci.historical_launch_qualification import (  # noqa: E402
    assert_historical_installed_launch_contract,
)
from tools.ci.historical_release_contract import historical_install_environment  # noqa: E402
from tools.ci.historical_update_qualification import (  # noqa: E402
    HistoricalUpdateQualification,
    assert_installed_release_channel,
    qualify_historical_update,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError  # noqa: E402
from tools.ci.external_comfy_readiness_server import (  # noqa: E402
    ExternalComfyReadinessServer,
)
from tools.ci.installer_ui_qualification import (  # noqa: E402
    prepare_qualification_evidence,
    run_current_installer_ui,
    verify_main_shell_evidence,
)
from tools.ci.installed_version_evidence import assert_installed_version  # noqa: E402
from tools.ci.loopback_port_lease import LoopbackPortLease  # noqa: E402

_INSTALL_TIMEOUT_SECONDS = 3_600.0
_REQUIRED_INSTALLER_EVENTS = (
    "installer.window.ready",
    "installer.install.clicked",
    "onboarding.page.ready",
    "onboarding.target.selected",
    "onboarding.completion.ready",
    "onboarding.open_substitute.clicked",
)


def verify_clean_install(
    *,
    installer_path: Path,
    install_root: Path,
    expected_version: str,
    candidate_release_root: Path | None = None,
    expected_channel: str | None = None,
    expected_update_manifest_url: str | None = None,
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Install and prove the completion button reveals the post-splash shell."""

    _require_empty_install_root(install_root)
    qualification_deadline = time.monotonic() + timeout_seconds
    with ExternalComfyReadinessServer() as external_comfy:
        with candidate_release_source(
            release_root=candidate_release_root,
            manifest_url=None,
            certificate_root=install_root.parent / ".candidate-certificate",
        ) as candidate_source:
            evidence = prepare_qualification_evidence(
                install_root=install_root,
                expected_version=expected_version,
                endpoint_port=external_comfy.port,
                phase="clean",
                timeout_seconds=timeout_seconds,
                target_mode="remote",
            )
            trust_candidate_source(evidence.environment, candidate_source)
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
            external_comfy.require_qualification_probes()
    print(f"INSTALLER_CLEAN_READY version={expected_version}", flush=True)


def verify_upgrade(
    *,
    historical_installer_path: Path,
    install_root: Path,
    historical_manifest_url: str,
    historical_version: str,
    historical_published_at: str,
    candidate_manifest_url: str | None,
    candidate_installer_path: Path | None,
    candidate_version: str,
    candidate_channel: str,
    expected_update_manifest_url: str | None = None,
    candidate_release_root: Path | None = None,
    historical_release_root: Path | None = None,
    source_cache_path: Path,
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Install history and reach the candidate shell through one launch action."""

    _require_empty_install_root(install_root)
    qualification_deadline = time.monotonic() + timeout_seconds
    managed_workspace = install_root.resolve() / "comfyui"
    managed_model_root = install_root.resolve() / "qualified-models"
    source_repository = require_comfy_source_repository(cache_path=source_cache_path)
    with LoopbackPortLease.acquire() as endpoint_lease:
        with candidate_release_source(
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
            trust_candidate_source(historical_environment, historical_source)
            prepare_portable_historical_install(
                repository_root=REPOSITORY_ROOT,
                installer_path=historical_installer_path,
                install_root=install_root,
                manifest_url=historical_source.manifest_url,
                historical_version=historical_version,
                endpoint_port=endpoint_lease.port,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
                source_repository=source_repository,
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
        route = qualify_historical_update(
            HistoricalUpdateQualification(
                install_root=install_root,
                historical_version=historical_version,
                candidate_version=candidate_version,
                candidate_channel=candidate_channel,
                candidate_manifest_url=candidate_manifest_url,
                candidate_release_root=candidate_release_root,
                candidate_installer_path=candidate_installer_path,
                expected_update_manifest_url=expected_update_manifest_url,
                managed_workspace=managed_workspace,
                managed_model_root=managed_model_root,
                preservation_marker=preservation_marker,
                timeout_seconds=_remaining_qualification_timeout(
                    qualification_deadline,
                    phase="candidate update and readiness",
                ),
            ),
            endpoint_lease=endpoint_lease,
        )
    print(
        "INSTALLER_UPGRADE_READY "
        f"from={historical_version} to={candidate_version} route={route.value}",
        flush=True,
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
    clean.add_argument("--expected-channel")
    clean.add_argument("--expected-update-manifest-url")
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
    upgrade.add_argument("--historical-published-at", required=True)
    upgrade.add_argument("--source-cache", type=Path, required=True)
    upgrade.add_argument("--candidate-manifest-url")
    upgrade.add_argument("--candidate-release-root", type=Path)
    upgrade.add_argument("--candidate-installer", type=Path)
    upgrade.add_argument("--candidate-version", required=True)
    upgrade.add_argument("--candidate-channel", required=True)
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
            expected_channel=args.expected_channel,
            expected_update_manifest_url=args.expected_update_manifest_url,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        verify_upgrade(
            historical_installer_path=args.historical_installer,
            install_root=args.install_root,
            historical_manifest_url=args.historical_manifest_url,
            historical_version=args.historical_version,
            historical_published_at=args.historical_published_at,
            historical_release_root=args.historical_release_root,
            source_cache_path=args.source_cache,
            candidate_manifest_url=args.candidate_manifest_url,
            candidate_installer_path=args.candidate_installer,
            candidate_version=args.candidate_version,
            candidate_channel=args.candidate_channel,
            expected_update_manifest_url=args.expected_update_manifest_url,
            candidate_release_root=args.candidate_release_root,
            timeout_seconds=args.timeout_seconds,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
