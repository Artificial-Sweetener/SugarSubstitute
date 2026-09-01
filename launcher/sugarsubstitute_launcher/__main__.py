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

"""Run the SugarSubstitute launcher as a module."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import sys
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sugarsubstitute_shared.crash_reporting.runtime import ProcessCrashRuntime


def run_launcher(launcher_main: Callable[[], int] | None = None) -> int:
    """Run the launcher and preserve unexpected packaged-bootstrap failures."""

    crash_runtime = _install_supervised_crash_runtime()
    try:
        if launcher_main is None:
            from launcher.sugarsubstitute_launcher.app import main

            launcher_main = main
        result = launcher_main()
    except SystemExit:
        _request_clean_exit(crash_runtime)
        raise
    except Exception:
        failure = traceback.format_exc()
        _record_bootstrap_failure(failure)
        _emit_bootstrap_failure(failure)
        raise
    _request_clean_exit(crash_runtime)
    return result


def _install_supervised_crash_runtime() -> ProcessCrashRuntime | None:
    """Install Crashpad and Python hooks in a supervised launcher UI child."""

    from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext

    context = CrashRunContext.from_environment()
    if context is None:
        return None
    from launcher.sugarsubstitute_launcher import __version__
    from sugarsubstitute_shared.crash_reporting.runtime import (
        install_process_crash_runtime,
    )

    return install_process_crash_runtime(
        context=context,
        application_version=__version__,
        launch_arguments=sys.argv,
        install_root=context.incident_root.parents[2],
    )


def _request_clean_exit(runtime: ProcessCrashRuntime | None) -> None:
    """Authenticate launcher UI completion only after normal cleanup."""

    if runtime is None or runtime.clean_exit_outcome is not None:
        return
    from sugarsubstitute_shared.crash_reporting.protocol import CleanExitOutcome

    runtime.request_clean_exit(CleanExitOutcome.CLOSED)


def _record_bootstrap_failure(failure: str) -> None:
    """Append an unexpected failure to the installed launcher's diagnostic log."""

    try:
        log_path = _installed_bootstrap_log_path()
        if log_path is None:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp} launcher bootstrap failed\n{failure}\n")
    except OSError:
        return


def _installed_bootstrap_log_path() -> Path | None:
    """Find installed launcher state without importing application modules."""

    candidate_roots = [Path.cwd().resolve()]
    if sys.argv and sys.argv[0]:
        invocation_path = Path(sys.argv[0]).expanduser().absolute()
        candidate_roots.extend(list(invocation_path.parents)[:5])
    checked_roots: set[Path] = set()
    for candidate_root in candidate_roots:
        resolved_root = candidate_root.resolve()
        if resolved_root in checked_roots:
            continue
        checked_roots.add(resolved_root)
        launcher_dir = resolved_root / "launcher"
        if (launcher_dir / "config.json").is_file():
            return launcher_dir / "logs" / "launcher-bootstrap.log"
    return None


def _emit_bootstrap_failure(failure: str) -> None:
    """Expose the traceback to an inherited qualification output stream."""

    stream = sys.stderr if sys.stderr is not None else sys.stdout
    if stream is None:
        return
    try:
        stream.write(failure)
        stream.flush()
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(run_launcher())
