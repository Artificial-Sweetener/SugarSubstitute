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


def run_launcher(launcher_main: Callable[[], int] | None = None) -> int:
    """Run the launcher and preserve unexpected packaged-bootstrap failures."""

    try:
        if launcher_main is None:
            from launcher.sugarsubstitute_launcher.app import main

            launcher_main = main
        return launcher_main()
    except Exception:
        failure = traceback.format_exc()
        _record_bootstrap_failure(failure)
        _emit_bootstrap_failure(failure)
        raise


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
