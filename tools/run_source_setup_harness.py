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

"""Run repeated real source installs against the fixed disposable test root."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import stat
import subprocess
import sys
from threading import Thread
import time


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller  # noqa: E402
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller  # noqa: E402
from launcher.sugarsubstitute_launcher.release_sources import (  # noqa: E402
    LocalFolderReleaseSource,
)
from launcher.sugarsubstitute_launcher.resources import launcher_uv_path  # noqa: E402
from launcher.sugarsubstitute_launcher.runtime import (  # noqa: E402
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
    runtime_environment,
)
from launcher.sugarsubstitute_launcher.update_state import (  # noqa: E402
    LauncherUpdateState,
)
from substitute.infrastructure.comfy.managed_process_registry import (  # noqa: E402
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_shutdown import (  # noqa: E402
    kill_managed_comfy_metadata,
)
from tools.release_assets.assembly import build_local_release_channel  # noqa: E402


DEFAULT_INSTALL_ROOT = REPO_ROOT / ".pytest-tmp" / "SugarSubstitute-Test"
DEFAULT_RELEASE_ROOT = REPO_ROOT / ".pytest-tmp" / "source-setup-release"
DEFAULT_ARTIFACT_CACHE_ROOT = REPO_ROOT / ".pytest-tmp" / "source-setup-artifact-cache"
DEFAULT_RESULT_ROOT = REPO_ROOT / "artifacts" / "source_setup_harness"
EXISTING_INSTALL_CACHE_ROOT = REPO_ROOT / ".pytest-tmp" / "source-setup-existing-cache"
_CHILD_SCRIPT = REPO_ROOT / "tools" / "source_setup_harness_child.py"
_WATCHDOG_TIMEOUT_SECONDS = 15.0
_PROCESS_TIMEOUT_SECONDS = 7_500.0


class SourceSetupHarnessError(RuntimeError):
    """Report a failed, stalled, or unsafe source fresh-install run."""


def run_source_setup_harness(
    *,
    iterations: int = 2,
    install_root: Path = DEFAULT_INSTALL_ROOT,
    log: Callable[[str], None] = print,
) -> tuple[dict[str, object], ...]:
    """Build current source and complete repeated off-screen fresh installs."""

    if iterations < 1:
        raise ValueError("Harness iterations must be positive.")
    resolved_install_root = _require_exact_test_root(install_root)
    release_root = DEFAULT_RELEASE_ROOT.resolve()
    artifact_cache_root = DEFAULT_ARTIFACT_CACHE_ROOT.resolve()
    result_root = DEFAULT_RESULT_ROOT.resolve()
    _rebuild_source_release(release_root=release_root, log=log)
    _seed_harness_artifact_cache(
        artifact_cache_root=artifact_cache_root,
        log=log,
    )
    results: list[dict[str, object]] = []

    for iteration in range(1, iterations + 1):
        log(f"[{iteration}/{iterations}] Resetting {resolved_install_root}")
        _stop_owned_managed_comfy(resolved_install_root, log=log)
        _clean_exact_test_root(resolved_install_root, log=log)
        layout = _install_current_source(
            install_root=resolved_install_root,
            release_root=release_root,
            log=log,
        )
        _restore_harness_artifact_cache(
            artifact_cache_root=artifact_cache_root,
            install_root=resolved_install_root,
            log=log,
        )
        result_path = result_root / f"iteration-{iteration}.json"
        result_path.unlink(missing_ok=True)
        result = _run_installed_setup_child(
            layout=layout,
            result_path=result_path,
            log=log,
        )
        if result.get("success") is not True:
            raise SourceSetupHarnessError(
                f"Installed setup iteration {iteration} did not succeed: {result}"
            )
        results.append(result)
        _capture_harness_artifact_cache(
            install_root=resolved_install_root,
            artifact_cache_root=artifact_cache_root,
            log=log,
        )
        log(
            f"[{iteration}/{iterations}] Setup completed responsively in "
            f"{result.get('duration_seconds')} seconds with maximum Qt gap "
            f"{result.get('maximum_heartbeat_gap_seconds')} seconds."
        )

    return tuple(results)


def _rebuild_source_release(
    *,
    release_root: Path,
    log: Callable[[str], None],
) -> None:
    """Build a local app payload containing the current checkout source."""

    if release_root.exists():
        shutil.rmtree(release_root, onexc=_clear_readonly_and_retry)
    log(f"Building current source payload: {release_root}")
    build_local_release_channel(
        repo_root=REPO_ROOT,
        output_dir=release_root,
        version="0.9.0-source-harness",
        channel="test",
    )


def _install_current_source(
    *,
    install_root: Path,
    release_root: Path,
    log: Callable[[str], None],
) -> InstallLayout:
    """Install the real source payload and runtime into the disposable root."""

    prepared = LayoutInstaller().prepare(install_root)
    layout = prepared.layout
    log(f"Prepared launcher layout: {layout.root}")
    continued = FirstRunInstaller(
        process_starter=lambda _command: None
    ).continue_install(
        layout=layout,
        release_source=LocalFolderReleaseSource(release_root),
    )
    log(f"Installed app payload: {continued.app_version}")
    update_state = LauncherUpdateState.load(layout.state_path)
    if update_state.installed_app_version != continued.app_version:
        raise SourceSetupHarnessError(
            "First-run install did not record the installed app payload version."
        )
    runtime_installer = UvManagedRuntimeInstaller(
        bundled_uv_path=launcher_uv_path(),
        runner=SubprocessRuntimeCommandRunner(log),
    )
    runtime_installer.provision(layout=layout)
    log(f"Installed runtime: {layout.runtime_python}")
    runtime_installer.provision(layout=layout)
    log("Reconciled the existing managed runtime without rebuilding its venv.")
    return layout


def _seed_harness_artifact_cache(
    *,
    artifact_cache_root: Path,
    log: Callable[[str], None],
) -> None:
    """Seed immutable downloads from the existing install without modifying it."""

    if _contains_complete_artifact(artifact_cache_root):
        return
    source_root = EXISTING_INSTALL_CACHE_ROOT.resolve()
    if not _contains_complete_artifact(source_root):
        log("No existing verified artifact cache is available to seed the harness.")
        return
    if artifact_cache_root.exists():
        shutil.rmtree(artifact_cache_root, onexc=_clear_readonly_and_retry)
    log(f"Seeding harness-owned artifact cache from: {source_root}")
    _copy_complete_cache(source_root=source_root, destination=artifact_cache_root)


def _restore_harness_artifact_cache(
    *,
    artifact_cache_root: Path,
    install_root: Path,
    log: Callable[[str], None],
) -> None:
    """Restore cached downloads into an otherwise-clean test installation."""

    if not _contains_complete_artifact(artifact_cache_root):
        return
    destination = install_root / ".sugarsubstitute-cache"
    if destination.exists():
        shutil.rmtree(destination, onexc=_clear_readonly_and_retry)
    log("Restoring harness-owned verified download cache.")
    _copy_complete_cache(source_root=artifact_cache_root, destination=destination)


def _capture_harness_artifact_cache(
    *,
    install_root: Path,
    artifact_cache_root: Path,
    log: Callable[[str], None],
) -> None:
    """Keep completed downloads for the next clean harness iteration."""

    source = install_root / ".sugarsubstitute-cache"
    if not _contains_complete_artifact(source):
        return
    if artifact_cache_root.exists():
        shutil.rmtree(artifact_cache_root, onexc=_clear_readonly_and_retry)
    log("Capturing verified downloads for the next clean iteration.")
    _copy_complete_cache(source_root=source, destination=artifact_cache_root)


def _contains_complete_artifact(cache_root: Path) -> bool:
    """Return whether a cache contains at least one finalized artifact."""

    if not cache_root.is_dir():
        return False
    return any(
        path.is_file() and not path.name.endswith(".part")
        for path in cache_root.rglob("*")
    )


def _copy_complete_cache(*, source_root: Path, destination: Path) -> None:
    """Copy finalized cache files while excluding interrupted partial downloads."""

    for source_path in source_root.rglob("*"):
        relative_path = source_path.relative_to(source_root)
        destination_path = destination / relative_path
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue
        if source_path.name.endswith(".part"):
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def _run_installed_setup_child(
    *,
    layout: InstallLayout,
    result_path: Path,
    log: Callable[[str], None],
) -> dict[str, object]:
    """Run installed onboarding with live output and a heartbeat watchdog."""

    environment = runtime_environment(layout=layout)
    environment.update(
        {
            "PYTHONUNBUFFERED": "1",
            "QT_QPA_PLATFORM": "offscreen",
            "SUBSTITUTE_DISABLE_APP_USER_MODEL_ID": "1",
        }
    )
    command = (
        str(layout.runtime_python),
        str(_CHILD_SCRIPT),
        f"--install-root={layout.root}",
        f"--result-path={result_path}",
    )
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=layout.root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    output_queue: Queue[str | None] = Queue()
    reader = Thread(
        target=_read_output,
        args=(process, output_queue),
        name="source-setup-harness-output",
        daemon=True,
    )
    reader.start()
    started_at = time.monotonic()
    last_output_at = started_at
    captured: list[str] = []
    try:
        while process.poll() is None:
            try:
                line = output_queue.get(timeout=0.25)
            except Empty:
                line = None
            if line:
                captured.append(line)
                log(line)
                last_output_at = time.monotonic()
            elapsed = time.monotonic() - started_at
            if elapsed > _PROCESS_TIMEOUT_SECONDS:
                raise SourceSetupHarnessError(
                    "Installed setup exceeded its total process timeout."
                )
            if time.monotonic() - last_output_at > _WATCHDOG_TIMEOUT_SECONDS:
                raise SourceSetupHarnessError(
                    "Installed setup stopped servicing its Qt heartbeat for more than "
                    f"{_WATCHDOG_TIMEOUT_SECONDS:.0f} seconds."
                )
    except BaseException:
        _kill_process_tree(process.pid)
        raise

    reader.join(timeout=2.0)
    while True:
        try:
            line = output_queue.get_nowait()
        except Empty:
            break
        if line:
            captured.append(line)
            log(line)
    if process.returncode != 0:
        details = "\n".join(captured[-200:])
        raise SourceSetupHarnessError(
            f"Installed setup exited with code {process.returncode}.\n{details}"
        )
    if not result_path.is_file():
        raise SourceSetupHarnessError(
            "Installed setup exited successfully without writing its result."
        )
    decoded = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise SourceSetupHarnessError("Installed setup result is not an object.")
    return {str(key): value for key, value in decoded.items()}


def _read_output(process: subprocess.Popen[str], output: Queue[str | None]) -> None:
    """Read child output without blocking the watchdog loop."""

    if process.stdout is None:
        output.put(None)
        return
    for raw_line in process.stdout:
        output.put(raw_line.rstrip())
    output.put(None)


def _require_exact_test_root(install_root: Path) -> Path:
    """Allow destructive cleanup only for the fixed E-drive harness root."""

    resolved = install_root.expanduser().resolve()
    expected = DEFAULT_INSTALL_ROOT.resolve()
    if str(resolved).casefold() != str(expected).casefold():
        raise SourceSetupHarnessError(
            f"Refusing to use any install root except {expected}; got {resolved}."
        )
    if resolved.anchor == str(resolved):
        raise SourceSetupHarnessError("Refusing to use a filesystem root.")
    if resolved.name.casefold() != "sugarsubstitute-test":
        raise SourceSetupHarnessError(
            f"Disposable root has the wrong final component: {resolved}."
        )
    return resolved


def _clean_exact_test_root(
    install_root: Path,
    *,
    log: Callable[[str], None],
) -> None:
    """Delete only the already-validated disposable harness installation."""

    _require_exact_test_root(install_root)
    if not install_root.exists():
        return
    log(f"Deleting disposable install: {install_root}")
    shutil.rmtree(install_root, onexc=_clear_readonly_and_retry)


def _stop_owned_managed_comfy(
    install_root: Path,
    *,
    log: Callable[[str], None],
) -> None:
    """Stop managed Comfy owned by an earlier harness iteration."""

    metadata = ManagedProcessRegistry(install_root / "appdata" / "runtime_state").load()
    if metadata is None:
        return
    result = kill_managed_comfy_metadata(metadata)
    log(f"Stopped previous harness Comfy process: {result.status.value}")


def _clear_readonly_and_retry(
    function: Callable[[str], object],
    path: str,
    _error: BaseException,
) -> None:
    """Clear one Windows read-only attribute and retry cleanup."""

    os.chmod(path, stat.S_IWRITE)
    function(path)


def _kill_process_tree(process_id: int) -> None:
    """Terminate only the child process tree started by this harness."""

    if sys.platform == "win32":
        subprocess.run(
            ("taskkill", "/F", "/T", "/PID", str(process_id)),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            shell=False,
        )
        return
    process = subprocess.Popen(  # noqa: S603
        ("kill", "-TERM", str(process_id)),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    process.wait(timeout=10)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse fresh-install harness arguments."""

    parser = argparse.ArgumentParser(
        description="Run repeated real source installs against an isolated test root."
    )
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--install-root", type=Path, default=DEFAULT_INSTALL_ROOT)
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested number of source fresh-install iterations."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    results = run_source_setup_harness(
        iterations=args.iterations,
        install_root=args.install_root,
        log=lambda line: print(line, flush=True),
    )
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
