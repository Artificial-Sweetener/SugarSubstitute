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

"""Verify durable crash reporter presentation and startup recovery."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.crash_reporter import (
    show_crash_report,
    show_pending_crash_reports,
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
    """Build one durable incident for reporter ownership tests."""

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


def test_reporter_acknowledges_only_after_presentation_returns(tmp_path: Path) -> None:
    """A durable incident must remain pending for the complete dialog lifetime."""

    layout = InstallLayout.from_root(tmp_path / "install")
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = _incident("incident-1", "2026-08-31T12:00:00+00:00")
    store.record(incident)
    observed_pending: list[tuple[CrashIncident, ...]] = []

    def present(
        _layout: InstallLayout,
        _incident_value: CrashIncident,
        _locale: str | None,
        _restart: Callable[[], None],
    ) -> None:
        """Observe the store while the modal is notionally visible."""

        observed_pending.append(store.pending())

    result = show_crash_report(
        layout=layout,
        incident_id=incident.incident_id,
        locale_override="ja",
        restart=lambda: None,
        presenter=present,
    )

    assert result == 0
    assert observed_pending == [(incident,)]
    assert store.pending() == ()


def test_reporter_keeps_incident_pending_when_presentation_fails(
    tmp_path: Path,
) -> None:
    """A reporter crash must preserve evidence for the next launcher invocation."""

    layout = InstallLayout.from_root(tmp_path / "install")
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = _incident("incident-1", "2026-08-31T12:00:00+00:00")
    store.record(incident)

    def fail_presentation(
        _layout: InstallLayout,
        _incident_value: CrashIncident,
        _locale: str | None,
        _restart: Callable[[], None],
    ) -> None:
        """Simulate a failure before the user can dismiss the dialog."""

        raise RuntimeError("reporter failed")

    with pytest.raises(RuntimeError, match="reporter failed"):
        show_crash_report(
            layout=layout,
            incident_id=incident.incident_id,
            locale_override=None,
            restart=lambda: None,
            presenter=fail_presentation,
        )

    assert store.pending() == (incident,)


def test_normal_startup_recovers_all_pending_incidents_in_time_order(
    tmp_path: Path,
) -> None:
    """The stable launcher should recover reports missed by an earlier reporter."""

    layout = InstallLayout.from_root(tmp_path / "install")
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    later = _incident("later", "2026-08-31T13:00:00+00:00")
    earlier = _incident("earlier", "2026-08-31T12:00:00+00:00")
    store.record(later)
    store.record(earlier)
    presented: list[str] = []

    def present(
        _layout: InstallLayout,
        incident: CrashIncident,
        locale: str | None,
        restart: Callable[[], None],
    ) -> None:
        """Capture the recovery order and callable restart contract."""

        assert locale == "es"
        restart()
        presented.append(incident.incident_id)

    restart_calls: list[None] = []
    count = show_pending_crash_reports(
        layout=layout,
        locale_override="es",
        restart=lambda: restart_calls.append(None),
        presenter=present,
    )

    assert count == 2
    assert presented == ["earlier", "later"]
    assert restart_calls == [None, None]
    assert store.pending() == ()
