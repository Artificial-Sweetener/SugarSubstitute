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

"""Run the release installer path against a fixed fresh Windows install target."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller  # noqa: E402
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from launcher.sugarsubstitute_launcher.release_sources import (  # noqa: E402
    LocalFolderReleaseSource,
)
from launcher.sugarsubstitute_launcher.resources import launcher_uv_path  # noqa: E402
from launcher.sugarsubstitute_launcher.runtime import (  # noqa: E402
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
    runtime_environment,
)
from substitute.infrastructure.comfy.managed_process_registry import (  # noqa: E402
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_shutdown import (  # noqa: E402
    kill_managed_comfy_metadata,
)


DEFAULT_INSTALL_ROOT = Path("D:/SugarSubstitute")
DEFAULT_MODEL_ROOT = Path("E:/ImageGen Models")
DEFAULT_SETUP_TIMEOUT_SECONDS = 14_400

REQUIRED_LIVE_NODE_CLASSES = (
    "SeedVR2LoadDiTModel",
    "SeedVR2LoadVAEModel",
    "SeedVR2VideoUpscaler",
    "SimpleSyrup.KSamplerExtras",
    "SimpleSyrup.PromptEncodeStyle",
    "SimpleSyrup.ScaleFactor",
    "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl",
    "SimpleSyrup.Seed",
    "SimpleSyrup.SimpleLoadCheckpoint",
)


def _configure_stdio() -> None:
    """Make harness console output tolerant of Unicode Comfy logs on Windows."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


class CleanInstallHarnessError(RuntimeError):
    """Raised when the clean install harness cannot complete."""


@dataclass(frozen=True, slots=True)
class CleanInstallHarnessResult:
    """Describe one completed clean install harness run."""

    install_root: Path
    package_root: Path
    release_root: Path
    app_version: str


def run_clean_install_harness(
    *,
    install_root: Path = DEFAULT_INSTALL_ROOT,
    model_root: Path = DEFAULT_MODEL_ROOT,
    package_root: Path | None = None,
    release_root: Path | None = None,
    clean: bool = True,
    setup_timeout_seconds: int = DEFAULT_SETUP_TIMEOUT_SECONDS,
    log: Callable[[str], None] = print,
) -> CleanInstallHarnessResult:
    """Install from an external package and verify Base-Cubes live node classes."""

    resolved_install_root = install_root.expanduser().resolve()
    resolved_model_root = model_root.expanduser().resolve()
    resolved_package_root = (
        package_root.expanduser().resolve()
        if package_root is not None
        else _latest_tester_package_root()
    )
    resolved_release_root = (
        release_root.expanduser().resolve()
        if release_root is not None
        else _release_root_from_package(resolved_package_root)
    )

    if clean:
        _stop_owned_managed_comfy(resolved_install_root, log=log)
        _clean_install_root(resolved_install_root, log=log)

    layout = InstallLayout.from_root(resolved_install_root)
    release_source = LocalFolderReleaseSource(resolved_release_root)
    log(f"[1/5] Installing launcher from package: {resolved_package_root}")
    FirstRunInstaller(
        process_starter=lambda _command: None
    ).install_downloaded_launcher(
        install_root=layout.root,
        release_source=release_source,
        launch_installed=False,
    )

    log(f"[2/5] Installing app payload from release channel: {resolved_release_root}")
    continued = FirstRunInstaller(
        process_starter=lambda _command: None
    ).continue_install(
        layout=layout,
        release_source=release_source,
    )

    log("[3/5] Provisioning installed app runtime.")
    UvManagedRuntimeInstaller(
        bundled_uv_path=launcher_uv_path(),
        runner=SubprocessRuntimeCommandRunner(log),
    ).provision(layout=layout)

    log("[4/5] Running first-run setup through installed app code.")
    _run_installed_runtime_script(
        layout=layout,
        script=_full_setup_script(
            install_root=layout.root,
            model_root=resolved_model_root,
            setup_timeout_seconds=setup_timeout_seconds,
        ),
        timeout_seconds=setup_timeout_seconds + 300,
        log=log,
    )

    log("[5/5] Clean install harness completed.")
    return CleanInstallHarnessResult(
        install_root=layout.root,
        package_root=resolved_package_root,
        release_root=resolved_release_root,
        app_version=continued.app_version,
    )


def _latest_tester_package_root() -> Path:
    """Return the newest unpacked tester package with a local release channel."""

    candidates = sorted(
        (
            path
            for path in (REPO_ROOT / "dist").glob("SugarSubstitute-tester-*")
            if path.is_dir()
            and (path / "dist" / ".local-release-channel" / "manifest.json").is_file()
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise CleanInstallHarnessError(
            "No unpacked tester package with dist\\.local-release-channel was found."
        )
    return candidates[0].resolve()


def _release_root_from_package(package_root: Path) -> Path:
    """Return the local release-channel folder for one external package root."""

    candidates = (
        package_root / "dist" / ".local-release-channel",
        package_root / ".local-release-channel",
        package_root,
    )
    for candidate in candidates:
        if (candidate / "manifest.json").is_file():
            return candidate.resolve()
    raise CleanInstallHarnessError(
        f"Package root does not contain a local release channel: {package_root}"
    )


def _stop_owned_managed_comfy(
    install_root: Path,
    *,
    log: Callable[[str], None],
) -> None:
    """Stop a previously owned managed Comfy process before deleting the target."""

    runtime_state_dir = install_root / "appdata" / "runtime_state"
    metadata = ManagedProcessRegistry(runtime_state_dir).load()
    if metadata is None:
        return
    result = kill_managed_comfy_metadata(metadata)
    log(f"Stopped existing owned managed Comfy process: {result.status.value}")


def _clean_install_root(
    install_root: Path,
    *,
    log: Callable[[str], None],
) -> None:
    """Delete the fixed install target after validating the exact path shape."""

    resolved = install_root.expanduser().resolve()
    expected = DEFAULT_INSTALL_ROOT.resolve()
    if resolved != expected:
        raise CleanInstallHarnessError(
            f"Refusing to clean any target except {expected}; got {resolved}"
        )
    if resolved.anchor == str(resolved):
        raise CleanInstallHarnessError(
            f"Refusing to clean a filesystem root: {resolved}"
        )
    if resolved.name.lower() != "sugarsubstitute":
        raise CleanInstallHarnessError(
            f"Refusing to clean a path not named SugarSubstitute: {resolved}"
        )
    if not resolved.exists():
        log(f"Clean target is already absent: {resolved}")
        return
    log(f"Cleaning install target: {resolved}")
    shutil.rmtree(resolved, onexc=_clear_readonly_and_retry)


def _clear_readonly_and_retry(
    function: Callable[[str], object],
    path: str,
    _error: BaseException,
) -> None:
    """Clear Windows read-only attributes for owned cleanup and retry once."""

    os.chmod(path, stat.S_IWRITE)
    function(path)


def _run_installed_runtime_script(
    *,
    layout: InstallLayout,
    script: str,
    timeout_seconds: int,
    log: Callable[[str], None],
) -> None:
    """Run a long installed-runtime script while streaming output."""

    env = runtime_environment(layout=layout)
    env["PYTHONUNBUFFERED"] = "1"
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW

    process = subprocess.Popen(  # noqa: S603
        [str(layout.runtime_python), "-c", script],
        cwd=layout.root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    started_at = time.monotonic()
    captured: list[str] = []
    try:
        if process.stdout is not None:
            while True:
                if time.monotonic() - started_at > timeout_seconds:
                    _kill_process_tree(process.pid)
                    raise CleanInstallHarnessError(
                        f"Installed runtime script timed out after {timeout_seconds} seconds."
                    )
                line = process.stdout.readline()
                if line:
                    stripped = line.rstrip()
                    captured.append(stripped)
                    if stripped:
                        log(stripped)
                    continue
                if process.poll() is not None:
                    break
                time.sleep(0.25)
        return_code = process.wait(timeout=5)
    except Exception:
        if process.poll() is None:
            _kill_process_tree(process.pid)
        raise
    if return_code != 0:
        raise CleanInstallHarnessError(
            "Installed runtime script failed with exit code "
            f"{return_code}.\n" + "\n".join(captured[-300:])
        )


def _kill_process_tree(pid: int) -> None:
    """Terminate a Windows process tree started by the harness."""

    if sys.platform != "win32":
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def _full_setup_script(
    *,
    install_root: Path,
    model_root: Path,
    setup_timeout_seconds: int,
) -> str:
    """Build the installed-runtime script that performs setup and live verification."""

    return f"""
from __future__ import annotations

import json
from pathlib import Path
import time
import urllib.request

from substitute.app.bootstrap.installation_context import build_onboarding_service_bundle
from substitute.application.onboarding import OnboardingFlowService, OnboardingDraftState
from substitute.domain.onboarding import ComfyTargetMode
from substitute.domain.onboarding.setup_transaction_models import SetupTransactionMode
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_launcher import start_managed_comfy_background
from substitute.infrastructure.comfy.managed_shutdown import kill_managed_comfy_metadata

install_root = Path({json.dumps(str(install_root))})
model_root = Path({json.dumps(str(model_root))})
required_classes = tuple({json.dumps(REQUIRED_LIVE_NODE_CLASSES)})
setup_timeout_seconds = int({setup_timeout_seconds})


def emit_status(message: str) -> None:
    print("SETUP_STATUS " + message, flush=True)


def emit_log(message: str) -> None:
    print("SETUP_LOG " + message, flush=True)


flow = OnboardingFlowService(
    service_bundle_factory=build_onboarding_service_bundle,
    managed_workspace_provisioner=ensure_managed_comfy_setup,
    entrypoint_path=install_root / "app" / "main.py",
    transaction_mode=SetupTransactionMode.FIRST_RUN,
)
draft = OnboardingDraftState(
    installation_root=install_root,
    target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
    endpoint_host="127.0.0.1",
    endpoint_port=8188,
    managed_workspace_path=install_root / "comfyui",
    attached_workspace_path=install_root / "comfyui",
    managed_model_root=model_root,
    managed_model_root_uses_default=False,
    output_root=install_root / "user" / "outputs",
    output_root_uses_default=True,
    danbooru_tag_help_enabled=True,
    danbooru_safe_previews_enabled=True,
    danbooru_image_rating_policy="all_ratings",
    civitai_model_help_enabled=True,
    civitai_downloads_enabled=True,
    civitai_safe_thumbnails_enabled=True,
    civitai_thumbnail_safety_policy="allow_all",
)
result = flow.provision(
    draft=draft,
    credential_draft=None,
    restart_required=False,
    on_status=emit_status,
    on_log=emit_log,
)
context = result.context
workspace = context.comfy_target.workspace_path or context.managed_comfy_dir
print("HARNESS_SETUP_READY root=" + str(context.install_root), flush=True)
print("HARNESS_WORKSPACE " + str(workspace), flush=True)
print("HARNESS_MODEL_ROOT " + str(model_root), flush=True)

state = start_managed_comfy_background(
    endpoint=context.comfy_target.endpoint,
    workspace=workspace,
    runtime_state_dir=context.runtime_state_dir,
    on_status=lambda message: print("COMFY_STATUS " + message, flush=True),
    on_log=lambda message: print("COMFY_LOG " + message, flush=True),
)
try:
    deadline = time.monotonic() + setup_timeout_seconds
    while time.monotonic() < deadline:
        startup_result = state.get("startup_result")
        if startup_result is not None:
            if not startup_result.ready:
                detail = (
                    startup_result.fatal_incident.message
                    if startup_result.fatal_incident is not None
                    else "unknown startup failure"
                )
                raise RuntimeError("Managed Comfy did not become ready: " + detail)
            break
        if state.get("metadata") is not None and state.get("proc") is None:
            break
        thread = state.get("thread")
        if thread is not None and not thread.is_alive() and state.get("metadata") is None:
            raise RuntimeError("Managed Comfy startup thread exited without metadata.")
        time.sleep(1.0)
    else:
        raise RuntimeError("Managed Comfy did not become ready before timeout.")

    object_info_url = (
        "http://"
        + context.comfy_target.endpoint.host
        + ":"
        + str(context.comfy_target.endpoint.port)
        + "/object_info"
    )
    with urllib.request.urlopen(object_info_url, timeout=30) as response:
        object_info = json.loads(response.read().decode("utf-8", errors="replace"))
    missing = [node_class for node_class in required_classes if node_class not in object_info]
    if missing:
        print("HARNESS_LIVE_NODE_MISSING " + ", ".join(missing), flush=True)
        raise RuntimeError("Missing live node definitions: " + ", ".join(missing))
    print("HARNESS_LIVE_NODES_READY " + ", ".join(required_classes), flush=True)
finally:
    termination = kill_managed_comfy_metadata(
        state.get("metadata"),
        containment_handle=state.get("containment_handle"),
    )
    print("HARNESS_COMFY_SHUTDOWN " + termination.status.value, flush=True)
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line options and run the clean install harness."""

    _configure_stdio()
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    result = run_clean_install_harness(
        install_root=args.install_root,
        model_root=args.model_root,
        package_root=args.package_root,
        release_root=args.release_root,
        clean=not args.no_clean,
        setup_timeout_seconds=args.setup_timeout_seconds,
    )
    print(
        "HARNESS_COMPLETE "
        f"root={result.install_root} "
        f"version={result.app_version} "
        f"package={result.package_root}"
    )
    return 0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse harness CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Run a fixed-target clean install and live node verification."
    )
    parser.add_argument("--install-root", type=Path, default=DEFAULT_INSTALL_ROOT)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--package-root", type=Path, default=None)
    parser.add_argument("--release-root", type=Path, default=None)
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument(
        "--setup-timeout-seconds",
        type=int,
        default=DEFAULT_SETUP_TIMEOUT_SECONDS,
    )
    return parser.parse_args(list(argv))


if __name__ == "__main__":
    raise SystemExit(main())
