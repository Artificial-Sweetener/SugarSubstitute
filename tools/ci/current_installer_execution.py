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

"""Run the current packaged installer without descendant-owned output pipes."""

from __future__ import annotations

from pathlib import Path
import subprocess

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_evidence_verification import diagnostic_tail


_INSTALL_TIMEOUT_SECONDS = 3_600.0


def run_current_installer_ui(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str | None,
    environment: dict[str, str],
    timeout_seconds: float = _INSTALL_TIMEOUT_SECONDS,
) -> None:
    """Launch packaged setup normally and let its real Install action run."""

    command = [
        str(installer_path.resolve()),
        f"--install-root={install_root.resolve()}",
    ]
    if manifest_url is not None:
        command.append(f"--manifest-url={manifest_url}")
    output_path = install_root.resolve().parent / (
        f".{install_root.resolve().name}-installer-output.log"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    try:
        with output_path.open("wb") as output:
            result = subprocess.run(
                command,
                cwd=installer_path.resolve().parent,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
    except subprocess.TimeoutExpired as error:
        diagnostics = _installer_failure_diagnostics(
            install_root=install_root,
            environment=environment,
        )
        raise InstallerLifecycleError(
            f"Installer UI did not complete within {timeout_seconds:g} seconds.\n"
            "installer output:\n"
            f"{_installer_output(output_path, fallback=error.stdout)}\n"
            f"{diagnostics}"
        ) from error
    if result.returncode != 0:
        diagnostics = _installer_failure_diagnostics(
            install_root=install_root,
            environment=environment,
        )
        raise InstallerLifecycleError(
            f"Installer UI exited with {result.returncode}.\n"
            "installer output:\n"
            f"{_installer_output(output_path, fallback=result.stdout)}\n"
            f"{diagnostics}"
        )


def _installer_failure_diagnostics(
    *,
    install_root: Path,
    environment: dict[str, str],
) -> str:
    """Expose token-bound UI events and launcher logs after a failed install."""

    plan = InstallerQualificationPlan.from_environment(environment)
    event_log = (
        diagnostic_tail(plan.event_log_path)
        if plan is not None
        else "Qualification plan was not inherited."
    )
    launcher_log = diagnostic_tail(
        InstallLayout.from_root(install_root).logs_dir / "launcher.log"
    )
    return f"qualification events:\n{event_log}\nlauncher log:\n{launcher_log}"


def _installer_output(path: Path, *, fallback: bytes | str | None) -> str:
    """Read file-backed setup output without waiting on descendant pipe handles."""

    output = diagnostic_tail(path)
    if output and not output.startswith("<missing diagnostics:"):
        return output
    return _timeout_output(fallback)


def _timeout_output(output: bytes | str | None) -> str:
    """Render bounded subprocess timeout output without losing byte diagnostics."""

    if output is None:
        return "<no output>"
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


__all__ = ["run_current_installer_ui"]
