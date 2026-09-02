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

"""Verify pending crash recovery cannot prevent a healthy application launch."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.cli import parse_launcher_args
from launcher.sugarsubstitute_launcher.crash_routing import (
    recover_pending_crash_reports,
    route_explicit_crash_operation,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)


def _incident(incident_id: str, occurred_at_utc: str) -> CrashIncident:
    """Build one pending incident owned by the recovery launcher."""

    return CrashIncident(
        incident_id=incident_id,
        run_id=incident_id,
        occurred_at_utc=occurred_at_utc,
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="Unexpected Python exception",
        process_id=42,
    )


def test_pending_recovery_delegates_in_time_order_without_owning_acknowledgement(
    tmp_path: Path,
) -> None:
    """The UI child should remain the only owner that acknowledges presentation."""

    layout = InstallLayout.from_root(tmp_path / "install")
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    later = _incident("later", "2026-08-31T13:00:00+00:00")
    earlier = _incident("earlier", "2026-08-31T12:00:00+00:00")
    store.record(later)
    store.record(earlier)
    calls: list[tuple[str, str | None]] = []

    def run_reporter(
        _layout: InstallLayout,
        incident_id: str,
        locale_override: str | None,
    ) -> int:
        """Model successful child presentation and acknowledgement."""

        calls.append((incident_id, locale_override))
        store.acknowledge(incident_id)
        return 0

    recovered = recover_pending_crash_reports(
        layout=layout,
        locale_override="es",
        reporter_runner=run_reporter,
    )

    assert recovered == 2
    assert calls == [("earlier", "es"), ("later", "es")]
    assert store.pending() == ()


def test_pending_recovery_failure_preserves_incident_and_allows_launch(
    tmp_path: Path,
) -> None:
    """A damaged report child must not become an installation repair signal."""

    layout = InstallLayout.from_root(tmp_path / "install")
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = _incident("incident-1", "2026-08-31T12:00:00+00:00")
    store.record(incident)

    def fail_reporter(
        _layout: InstallLayout,
        _incident_id: str,
        _locale_override: str | None,
    ) -> int:
        """Model a missing or unloadable Qt-capable report child."""

        raise OSError("reporter unavailable")

    recovered = recover_pending_crash_reports(
        layout=layout,
        locale_override=None,
        reporter_runner=fail_reporter,
    )

    assert recovered == 0
    assert store.pending() == (incident,)


def test_explicit_report_on_supervisor_delegates_to_ui_child(tmp_path: Path) -> None:
    """Even direct report requests must keep Qt out of the supervisor process."""

    layout = InstallLayout.from_root(tmp_path / "install")
    calls: list[tuple[InstallLayout, str, str | None]] = []

    def run_reporter(
        report_layout: InstallLayout,
        incident_id: str,
        locale_override: str | None,
    ) -> int:
        """Capture the delegated report without importing its presentation."""

        calls.append((report_layout, incident_id, locale_override))
        return 3

    result = route_explicit_crash_operation(
        parse_launcher_args(
            [
                f"--install-root={layout.root}",
                "--show-crash-report=incident-1",
                "--locale=ja",
            ]
        ),
        reporter_runner=run_reporter,
    )

    assert result == 3
    assert calls == [(layout, "incident-1", "ja")]
