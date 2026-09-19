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

"""Exercise crash-reporter durability from a dedicated process."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys

from launcher.sugarsubstitute_launcher.crash_reporter import (
    CrashReportPresenter,
    show_pending_crash_reports,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting import CrashIncident


def _fail_presenter(
    layout: InstallLayout,
    incident: CrashIncident,
    locale_override: str | None,
    restart: Callable[[], None],
) -> None:
    """Simulate a reporter process failing before user acknowledgement."""

    del layout, incident, locale_override, restart
    raise RuntimeError("qualified reporter failure")


def _record_presenter(
    output_path: Path,
) -> Callable[
    [InstallLayout, CrashIncident, str | None, Callable[[], None]],
    None,
]:
    """Return a presenter that records the recovered incident identifier."""

    def present(
        layout: InstallLayout,
        incident: CrashIncident,
        locale_override: str | None,
        restart: Callable[[], None],
    ) -> None:
        """Record one successful cross-process presentation."""

        del layout, locale_override, restart
        output_path.write_text(incident.incident_id, encoding="utf-8")

    return present


def main() -> int:
    """Run one failing or successful reporter attempt."""

    mode = sys.argv[1]
    layout = InstallLayout.from_root(Path(sys.argv[2]))
    presenter: CrashReportPresenter
    if mode == "fail":
        presenter = _fail_presenter
    elif mode == "recover":
        presenter = _record_presenter(Path(sys.argv[3]))
    else:
        raise ValueError(f"Unknown reporter qualification mode: {mode}")
    show_pending_crash_reports(
        layout=layout,
        locale_override=None,
        restart=lambda: None,
        presenter=presenter,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
