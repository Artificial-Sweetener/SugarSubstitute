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

"""Qualify crash-reporter recovery across independent real processes."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)


_REPORTER_MODULE = "tests.support.crash_reporting.reporter_child"


def _incident() -> CrashIncident:
    """Return one valid pending incident for cross-process presentation."""

    return CrashIncident(
        incident_id="qualified-incident",
        run_id="qualified-run",
        occurred_at_utc="2026-08-31T12:00:00+00:00",
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="Qualified reporter recovery",
        process_id=42,
    )


def _run_reporter(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one reporter attempt without inheriting terminal streams."""

    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", _REPORTER_MODULE, *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        timeout=10,
    )


def test_reporter_failure_preserves_then_recovers_valid_incident(
    tmp_path: Path,
) -> None:
    """A later process must recover evidence after reporter failure and corruption."""

    layout = InstallLayout.from_root(tmp_path / "install")
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = _incident()
    store.record(incident)
    corrupt = store.root / "corrupt-input"
    corrupt.mkdir(parents=True)
    (corrupt / "incident.json").write_text("{broken", encoding="utf-8")

    failed = _run_reporter("fail", str(layout.root))

    assert failed.returncode != 0
    assert "qualified reporter failure" in failed.stderr
    assert store.pending() == (incident,)
    quarantined = tuple((store.root / "corrupt").iterdir())
    assert len(quarantined) == 1
    assert (quarantined[0] / "incident.json").read_text(encoding="utf-8") == ("{broken")

    recovered_path = tmp_path / "presented.txt"
    recovered = _run_reporter("recover", str(layout.root), str(recovered_path))

    assert recovered.returncode == 0, recovered.stderr
    assert recovered_path.read_text(encoding="utf-8") == incident.incident_id
    assert store.pending() == ()
