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

"""Prove a release installer can install, update, and reveal the application."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from collections.abc import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState  # noqa: E402
from sugarsubstitute_shared.application_readiness import (  # noqa: E402
    ApplicationReadinessReceipt,
    READINESS_PATH_ENV,
    READINESS_TOKEN_ENV,
)


_INSTALL_TIMEOUT_SECONDS = 3_600.0
_LAUNCH_TIMEOUT_SECONDS = 600.0


class InstallerLifecycleError(RuntimeError):
    """Report a packaged install or update lifecycle failure."""


def verify_clean_install(
    *,
    installer_path: Path,
    install_root: Path,
    expected_version: str,
) -> None:
    """Install through the candidate's default binding and reveal onboarding."""

    _require_empty_install_root(install_root)
    _run_installer(
        installer_path=installer_path,
        install_root=install_root,
        manifest_url=None,
    )
    _assert_installed_version(install_root, expected_version)
    _launch_and_verify_readiness(
        install_root=install_root,
        expected_version=expected_version,
    )
    print(f"INSTALLER_CLEAN_READY version={expected_version}", flush=True)


def verify_upgrade(
    *,
    historical_installer_path: Path,
    install_root: Path,
    historical_manifest_url: str,
    historical_version: str,
    candidate_manifest_url: str,
    candidate_version: str,
) -> None:
    """Install one historical release, update it, and prove candidate readiness."""

    _require_empty_install_root(install_root)
    _run_installer(
        installer_path=historical_installer_path,
        install_root=install_root,
        manifest_url=historical_manifest_url,
    )
    _assert_installed_version(install_root, historical_version)
    _set_update_manifest(install_root, candidate_manifest_url)
    _launch_and_verify_readiness(
        install_root=install_root,
        expected_version=candidate_version,
    )
    print(
        f"INSTALLER_UPGRADE_READY from={historical_version} to={candidate_version}",
        flush=True,
    )


def _run_installer(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str | None,
) -> None:
    """Run the packaged headless installer through its public CLI contract."""

    command = [
        str(installer_path.resolve()),
        "--headless-install",
        f"--install-root={install_root.resolve()}",
    ]
    if manifest_url is not None:
        command.append(f"--manifest-url={manifest_url}")
    result = subprocess.run(  # noqa: S603
        command,
        cwd=installer_path.resolve().parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_INSTALL_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Installer exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _launch_and_verify_readiness(
    *,
    install_root: Path,
    expected_version: str,
) -> None:
    """Launch the installed shortcut and wait for its post-splash receipt."""

    layout = InstallLayout.from_root(install_root)
    readiness_path = layout.launcher_dir / "readiness" / "ci-lifecycle.json"
    try:
        readiness_path.unlink()
    except FileNotFoundError:
        pass
    token = f"ci-lifecycle-{expected_version}-{os.getpid()}"
    environment = dict(os.environ)
    environment[READINESS_PATH_ENV] = str(readiness_path)
    environment[READINESS_TOKEN_ENV] = token
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(  # noqa: S603
        [str(layout.executable_path)],
        cwd=layout.root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_LAUNCH_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Installed launcher exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    receipt = _wait_for_readiness_receipt(
        readiness_path=readiness_path,
        token=token,
        timeout_seconds=_LAUNCH_TIMEOUT_SECONDS,
    )
    try:
        _assert_installed_version(install_root, expected_version)
    finally:
        _terminate_verified_process(receipt.pid)


def _wait_for_readiness_receipt(
    *,
    readiness_path: Path,
    token: str,
    timeout_seconds: float,
) -> ApplicationReadinessReceipt:
    """Wait for a valid receipt or surface launcher and app diagnostics."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if readiness_path.is_file():
            try:
                payload = json.loads(readiness_path.read_text(encoding="utf-8"))
                receipt = ApplicationReadinessReceipt.from_json(payload)
            except (OSError, json.JSONDecodeError, ValueError) as error:
                raise InstallerLifecycleError(
                    f"Application wrote an invalid readiness receipt: {readiness_path}."
                ) from error
            if receipt.token != token:
                raise InstallerLifecycleError(
                    "Application readiness receipt did not match this CI launch."
                )
            return receipt
        time.sleep(0.1)
    layout_root = readiness_path.parents[2]
    raise InstallerLifecycleError(
        "Application did not reveal a post-splash window before timeout.\n"
        + _diagnostic_tail(layout_root / "launcher" / "logs" / "app-startup.log")
        + "\n"
        + _diagnostic_tail(
            layout_root.parent
            / "appdata"
            / "diagnostics"
            / "logs"
            / "startup-trace.jsonl"
        )
    )


def _set_update_manifest(install_root: Path, manifest_url: str) -> None:
    """Point a historical installation at the exact candidate manifest."""

    layout = InstallLayout.from_root(install_root)
    payload = json.loads(layout.config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InstallerLifecycleError("Historical launcher config is invalid.")
    payload["release_source"] = {
        "kind": "github",
        "manifest_url": manifest_url,
    }
    layout.config_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_installed_version(install_root: Path, expected_version: str) -> None:
    """Require both launcher state and app source to identify the expected release."""

    layout = InstallLayout.from_root(install_root)
    state = LauncherUpdateState.load(layout.state_path)
    if state.installed_app_version != expected_version:
        raise InstallerLifecycleError(
            "Launcher state version mismatch: "
            f"{state.installed_app_version} != {expected_version}."
        )
    version_path = layout.app_dir / "substitute" / "_version.py"
    expected_line = f'__version__ = "{expected_version}"'
    if expected_line not in version_path.read_text(encoding="utf-8"):
        raise InstallerLifecycleError(
            f"Installed app source does not identify version {expected_version}."
        )


def _terminate_verified_process(pid: int) -> None:
    """Terminate only the token-verified app process and its child processes."""

    if os.name == "nt":
        result = subprocess.run(  # noqa: S603
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        if result.returncode not in {0, 128}:
            raise InstallerLifecycleError(
                f"Could not terminate verified app process {pid}: "
                + result.stderr.decode("utf-8", errors="replace")
            )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _require_empty_install_root(install_root: Path) -> None:
    """Reject reuse so every qualification begins from a real clean install."""

    if install_root.exists() and any(install_root.iterdir()):
        raise InstallerLifecycleError(
            f"Qualification install root is not empty: {install_root}"
        )


def _diagnostic_tail(path: Path, *, maximum_lines: int = 80) -> str:
    """Return bounded lifecycle diagnostics when a readiness wait fails."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"Unavailable diagnostic: {path}"
    return f"Diagnostic tail ({path}):\n" + "\n".join(lines[-maximum_lines:])


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse clean-install or historical-upgrade verification inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    clean = subparsers.add_parser("clean")
    clean.add_argument("--installer", type=Path, required=True)
    clean.add_argument("--install-root", type=Path, required=True)
    clean.add_argument("--expected-version", required=True)
    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("--historical-installer", type=Path, required=True)
    upgrade.add_argument("--install-root", type=Path, required=True)
    upgrade.add_argument("--historical-manifest-url", required=True)
    upgrade.add_argument("--historical-version", required=True)
    upgrade.add_argument("--candidate-manifest-url", required=True)
    upgrade.add_argument("--candidate-version", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one installer lifecycle qualification."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.mode == "clean":
        verify_clean_install(
            installer_path=args.installer,
            install_root=args.install_root,
            expected_version=args.expected_version,
        )
    else:
        verify_upgrade(
            historical_installer_path=args.historical_installer,
            install_root=args.install_root,
            historical_manifest_url=args.historical_manifest_url,
            historical_version=args.historical_version,
            candidate_manifest_url=args.candidate_manifest_url,
            candidate_version=args.candidate_version,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
