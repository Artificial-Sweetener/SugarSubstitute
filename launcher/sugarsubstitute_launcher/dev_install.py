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

"""Run a clean local installer proof against a disposable install target."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from launcher.sugarsubstitute_launcher.resources import launcher_uv_path
from launcher.sugarsubstitute_launcher.runtime import (
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
    runtime_environment,
)
from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    LauncherTarget,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTALL_ROOT = (
    REPO_ROOT / ".pytest-tmp" / "launcher-dev-install" / "SugarSubstitute"
)
DEFAULT_RELEASE_ROOT = REPO_ROOT / ".local-release-channel"
PROBE_TIMEOUT_SECONDS = 60.0


class DevInstallError(RuntimeError):
    """Raised when the local install proof cannot complete."""


@dataclass(frozen=True, slots=True)
class DevInstallProof:
    """Describe the completed clean local install proof."""

    layout: InstallLayout
    app_version: str
    runtime_python: Path
    readiness_route: str
    onboarding_window_class: str


def run_clean_dev_install(
    *,
    install_root: Path = DEFAULT_INSTALL_ROOT,
    release_root: Path = DEFAULT_RELEASE_ROOT,
    clean: bool = True,
    log: Callable[[str], None] = print,
    allow_non_default_clean: bool = False,
) -> DevInstallProof:
    """Install from the local release channel and prove first-run onboarding opens."""

    layout = InstallLayout.from_root(install_root)
    if clean:
        clean_install_root(
            layout.root,
            allow_non_default_clean=allow_non_default_clean,
            log=log,
        )

    log(f"[1/6] Preparing clean install root: {layout.root}")
    install_result = FirstRunInstaller(
        process_starter=lambda _command: None
    ).install_downloaded_launcher(
        install_root=layout.root,
        release_source=LocalFolderReleaseSource(release_root.resolve()),
        launch_installed=False,
    )
    log(f"Installed launcher: {install_result.layout.executable_path}")

    log(f"[2/6] Installing app payload from: {release_root.resolve()}")
    continued = FirstRunInstaller(
        process_starter=lambda _command: None
    ).continue_install(
        layout=layout,
        release_source=LocalFolderReleaseSource(release_root.resolve()),
    )
    log(f"Installed app payload version: {continued.app_version}")
    log(f"App entrypoint: {continued.layout.app_entrypoint}")

    log("[3/6] Provisioning Python runtime and app dependencies.")
    runtime_result = UvManagedRuntimeInstaller(
        bundled_uv_path=launcher_uv_path(),
        runner=SubprocessRuntimeCommandRunner(log),
    ).provision(layout=layout)
    log(f"Runtime ready: {runtime_result.python_executable}")

    log("[4/6] Proving startup readiness routes to onboarding.")
    readiness_route = run_readiness_probe(layout=layout, log=log)

    log("[5/6] Proving onboarding window can be constructed by installed app code.")
    onboarding_window_class = run_onboarding_probe(layout=layout, log=log)

    log("[6/6] Clean install proof completed.")
    return DevInstallProof(
        layout=layout,
        app_version=continued.app_version,
        runtime_python=runtime_result.python_executable,
        readiness_route=readiness_route,
        onboarding_window_class=onboarding_window_class,
    )


def clean_install_root(
    install_root: Path,
    *,
    allow_non_default_clean: bool = False,
    log: Callable[[str], None] = print,
) -> None:
    """Delete the disposable install target after validating the resolved path."""

    resolved_root = install_root.expanduser().resolve()
    default_root = DEFAULT_INSTALL_ROOT.resolve()
    if not allow_non_default_clean and resolved_root != default_root:
        raise DevInstallError(
            "Refusing to clean a non-default install root without explicit test override: "
            f"{resolved_root}"
        )
    if resolved_root.anchor == str(resolved_root):
        raise DevInstallError(f"Refusing to clean a filesystem root: {resolved_root}")
    if resolved_root.name.lower() != "sugarsubstitute":
        raise DevInstallError(
            f"Refusing to clean a path not named SugarSubstitute: {resolved_root}"
        )
    if not resolved_root.exists():
        log(f"Clean target is already absent: {resolved_root}")
        return
    log(f"Cleaning install target: {resolved_root}")
    shutil.rmtree(resolved_root)


def run_readiness_probe(
    *,
    layout: InstallLayout,
    log: Callable[[str], None] = print,
) -> str:
    """Run installed app readiness code and require the first-run onboarding route."""

    script = f"""
from pathlib import Path
from substitute.app.bootstrap.installation_context import build_onboarding_service_bundle

install_root = Path({str(layout.root)!r})
assessment = build_onboarding_service_bundle(install_root).readiness_service.assess()
print("READINESS_ROUTE=" + assessment.route.value)
for issue in assessment.issues:
    print("READINESS_ISSUE=" + issue.code.value + "|" + issue.summary)
if assessment.route.value != "onboarding":
    raise SystemExit(20)
"""
    output = _run_runtime_script(layout=layout, script=script, log=log)
    route = _extract_probe_value(output, "READINESS_ROUTE")
    if route != "onboarding":
        raise DevInstallError(f"Expected onboarding route, got: {route}")
    return route


def run_onboarding_probe(
    *,
    layout: InstallLayout,
    log: Callable[[str], None] = print,
) -> str:
    """Construct the installed app onboarding window with a target-safe Qt backend."""

    script = f"""
from pathlib import Path

from substitute.app.bootstrap import composition
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
    create_default_installation_context,
    load_persisted_installation_context,
)
from substitute.domain.onboarding import BootstrapRoute

install_root = Path({str(layout.root)!r})
bundle = build_onboarding_service_bundle(install_root)
assessment = bundle.readiness_service.assess()
if assessment.route is not BootstrapRoute.ONBOARDING:
    print("ONBOARDING_ROUTE=" + assessment.route.value)
    raise SystemExit(21)
context = load_persisted_installation_context(install_root)
if context is None:
    context = create_default_installation_context(install_root)
app = composition.create_application(["sugarsubstitute-onboarding-probe", "--install-root=" + str(install_root)])
window = composition.show_onboarding_window(
    context=context,
    readiness_assessment=assessment,
    entrypoint_path=resolve_app_layout(install_root).entrypoint_path,
)
app.processEvents()
print("ONBOARDING_ROUTE=" + assessment.route.value)
print("ONBOARDING_WINDOW_CLASS=" + type(window).__name__)
print("ONBOARDING_WINDOW_VISIBLE=" + str(window.isVisible()))
if not window.isVisible():
    raise SystemExit(22)
window.close()
app.processEvents()
"""
    output = _run_runtime_script(
        layout=layout,
        script=script,
        log=log,
        extra_env=onboarding_probe_environment(layout.target),
    )
    window_class = _extract_probe_value(output, "ONBOARDING_WINDOW_CLASS")
    visible = _extract_probe_value(output, "ONBOARDING_WINDOW_VISIBLE")
    if visible != "True":
        raise DevInstallError("Installed onboarding window was not visible in probe.")
    return window_class


def onboarding_probe_environment(target: LauncherTarget) -> dict[str, str]:
    """Build probe overrides without disabling native Cocoa window behavior."""

    environment = {"SUBSTITUTE_DISABLE_APP_USER_MODEL_ID": "1"}
    if target.operating_system is not LauncherOperatingSystem.MACOS:
        environment["QT_QPA_PLATFORM"] = "offscreen"
    return environment


def _run_runtime_script(
    *,
    layout: InstallLayout,
    script: str,
    log: Callable[[str], None],
    extra_env: dict[str, str] | None = None,
) -> str:
    """Run one installed-runtime Python script and return captured output."""

    env = runtime_environment(layout=layout)
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW
    process = subprocess.run(  # noqa: S603
        [str(layout.runtime_python), "-c", script],
        cwd=layout.root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        timeout=PROBE_TIMEOUT_SECONDS,
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
        check=False,
    )
    output = process.stdout or ""
    for line in output.splitlines():
        if line.strip():
            log(line)
    if process.returncode != 0:
        raise DevInstallError(
            f"Runtime probe failed with exit code {process.returncode}.\n{output}"
        )
    return output


def _extract_probe_value(output: str, key: str) -> str:
    """Read one `KEY=value` line from probe output."""

    prefix = key + "="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise DevInstallError(f"Probe output did not contain {key}.")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and run the clean local install proof."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    proof = run_clean_dev_install(
        install_root=args.install_root,
        release_root=args.release_root,
        clean=not args.no_clean,
        allow_non_default_clean=args.allow_non_default_clean,
    )
    print(
        "PROOF_COMPLETE "
        f"root={proof.layout.root} "
        f"version={proof.app_version} "
        f"route={proof.readiness_route} "
        f"window={proof.onboarding_window_class}"
    )
    return 0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments for the developer install proof."""

    parser = argparse.ArgumentParser(
        description="Run a clean SugarSubstitute installer proof."
    )
    parser.add_argument(
        "--install-root",
        type=Path,
        default=DEFAULT_INSTALL_ROOT,
        help="Disposable install root to clean and prove.",
    )
    parser.add_argument(
        "--release-root",
        type=Path,
        default=DEFAULT_RELEASE_ROOT,
        help="Local release-channel folder containing manifest.json.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Reuse the existing install root instead of deleting it first.",
    )
    parser.add_argument(
        "--allow-non-default-clean",
        action="store_true",
        help="Allow deletion of an explicitly supplied disposable install root.",
    )
    return parser.parse_args(list(argv))


if __name__ == "__main__":
    raise SystemExit(main())
