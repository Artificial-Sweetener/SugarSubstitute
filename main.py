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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.app.bootstrap.startup_timing import StartupTimingRecord
    from sugarsubstitute_shared.application_launch_guard import ApplicationLaunchGuard


_PROCESS_LAUNCH_GUARD: ApplicationLaunchGuard | None = None


def _record_elapsed(
    records: list[StartupTimingRecord],
    phase: str,
    started_at: float,
    *,
    record_type: type[StartupTimingRecord],
) -> float:
    """Append one pre-bootstrap timing record and return the current timestamp."""

    ended_at = time.perf_counter()
    records.append(
        record_type(
            phase=phase,
            elapsed_ms=max(0.0, (ended_at - started_at) * 1000.0),
        )
    )
    return ended_at


def main() -> None:
    """Execute startup flow and exit with Qt event-loop code."""

    phase_started_at = time.perf_counter()
    app_root = Path(__file__).resolve().parent
    if not _enter_application_launch_guard(argv=sys.argv, app_root=app_root):
        return
    from sugarsubstitute_shared.localization import (
        resolve_early_startup_locale,
        system_ui_languages,
    )
    from substitute.app.bootstrap.early_launch_splash import start_early_launch_splash

    early_locale = resolve_early_startup_locale(
        sys.argv,
        app_root=app_root,
        ui_languages=system_ui_languages(),
    )
    early_splash, cancel_relay = start_early_launch_splash(
        sys.argv,
        app_root,
        early_locale.effective_language.identifier,
    )

    from substitute.app.bootstrap.startup_timing import StartupTimingRecord

    startup_records: list[StartupTimingRecord] = []
    phase_started_at = _record_elapsed(
        startup_records,
        "entrypoint.start_early_launch_splash",
        phase_started_at,
        record_type=StartupTimingRecord,
    )
    try:
        from substitute.app.bootstrap.env_file import load_env_file

        load_env_file(app_root / ".env")
        phase_started_at = _record_elapsed(
            startup_records,
            "entrypoint.load_env_file",
            phase_started_at,
            record_type=StartupTimingRecord,
        )
        from substitute.app.bootstrap.startup import run_application

        phase_started_at = _record_elapsed(
            startup_records,
            "entrypoint.import_startup",
            phase_started_at,
            record_type=StartupTimingRecord,
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


def _enter_application_launch_guard(*, argv: list[str], app_root: Path) -> bool:
    """Claim this application process before any splash can be created."""

    from sugarsubstitute_shared.application_launch_guard import (
        ApplicationLaunchGuard,
        application_launch_install_root,
        clear_inherited_application_launch_token,
        inherited_application_launch_token,
    )

    global _PROCESS_LAUNCH_GUARD
    install_root = application_launch_install_root(argv, app_root=app_root)
    try:
        guard = ApplicationLaunchGuard.enter(
            install_root,
            inherited_token=inherited_application_launch_token(),
        )
    finally:
        clear_inherited_application_launch_token()
    if guard is None:
        return False
    _PROCESS_LAUNCH_GUARD = guard
    return True


if __name__ == "__main__":
    main()
