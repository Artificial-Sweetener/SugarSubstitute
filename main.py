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

"""Program entrypoint that delegates startup to app bootstrap orchestration."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QLocale

from substitute.app.bootstrap.startup_timing import StartupTimingRecord
from sugarsubstitute_shared.localization import resolve_early_startup_locale


def _record_elapsed(
    records: list[StartupTimingRecord],
    phase: str,
    started_at: float,
) -> float:
    """Append one pre-bootstrap timing record and return the current timestamp."""

    ended_at = time.perf_counter()
    records.append(
        StartupTimingRecord(
            phase=phase,
            elapsed_ms=max(0.0, (ended_at - started_at) * 1000.0),
        )
    )
    return ended_at


def main() -> None:
    """Execute startup flow and exit with Qt event-loop code."""
    startup_records: list[StartupTimingRecord] = []
    phase_started_at = time.perf_counter()
    app_root = Path(__file__).resolve().parent
    phase_started_at = _record_elapsed(
        startup_records,
        "entrypoint.resolve_app_root",
        phase_started_at,
    )
    from substitute.app.bootstrap.env_file import load_env_file

    load_env_file(app_root / ".env")
    phase_started_at = _record_elapsed(
        startup_records,
        "entrypoint.load_env_file",
        phase_started_at,
    )
    from substitute.app.bootstrap.early_launch_splash import start_early_launch_splash

    phase_started_at = _record_elapsed(
        startup_records,
        "entrypoint.import_early_launch_splash",
        phase_started_at,
    )
    early_locale = resolve_early_startup_locale(
        sys.argv,
        app_root=app_root,
        ui_languages=tuple(QLocale.system().uiLanguages()),
    )
    early_splash, cancel_relay = start_early_launch_splash(
        sys.argv,
        app_root,
        early_locale.effective_language.identifier,
    )
    phase_started_at = _record_elapsed(
        startup_records,
        "entrypoint.start_early_launch_splash",
        phase_started_at,
    )
    try:
        from substitute.app.bootstrap.startup import run_application

        phase_started_at = _record_elapsed(
            startup_records,
            "entrypoint.import_startup",
            phase_started_at,
        )
        exit_code = run_application(
            sys.argv,
            initial_splash=early_splash,
            initial_splash_cancel_connector=cancel_relay.connect
            if cancel_relay is not None
            else None,
            prebootstrap_timing_records=tuple(startup_records),
        )
        early_splash = None
    finally:
        if early_splash is not None:
            early_splash.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
