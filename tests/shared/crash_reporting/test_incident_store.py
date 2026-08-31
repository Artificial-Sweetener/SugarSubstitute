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

"""Verify durable crash incident serialization and recovery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)


def _incident(*, incident_id: str = "incident-1") -> CrashIncident:
    """Return one complete deterministic crash incident."""

    return CrashIncident(
        incident_id=incident_id,
        run_id="run-1",
        occurred_at_utc="2026-08-31T12:00:00+00:00",
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="SugarSubstitute crashed during startup.",
        process_id=42,
        exception_type="RuntimeError",
        exception_message="boom",
        traceback=("Traceback", "RuntimeError: boom"),
        all_thread_traceback=("Thread main",),
        exit_code=1,
        thread_name="MainThread",
        application_version="0.22.0",
        platform="Windows-11",
        python_version="3.12",
        launch_arguments=("main.py", "--install-root=<install-root>"),
        breadcrumbs=("startup.begin",),
        attachments=("python-fault.log", "minidump.dmp"),
        metadata={"operation": "startup"},
    )


def test_incident_json_round_trip_preserves_complete_diagnostics() -> None:
    """The cross-process payload should preserve every diagnostic field."""

    incident = _incident()

    assert CrashIncident.from_json(incident.to_json()) == incident


def test_store_records_pending_incident_atomically_and_acknowledges_it(
    tmp_path: Path,
) -> None:
    """An incident should remain pending until the user-facing reporter handles it."""

    store = CrashIncidentStore(tmp_path / "appdata" / "diagnostics" / "crashes")
    incident = _incident()

    incident_directory = store.record(incident)

    assert (
        json.loads((incident_directory / "incident.json").read_text("utf-8"))
        == incident.to_json()
    )
    assert store.pending() == (incident,)

    store.acknowledge(incident.incident_id)

    assert store.pending() == ()
    assert (incident_directory / "incident.json").is_file()


def test_store_quarantines_corrupt_incident_without_deleting_evidence(
    tmp_path: Path,
) -> None:
    """Corruption should not block recovery or silently destroy diagnostics."""

    store = CrashIncidentStore(tmp_path / "crashes")
    corrupt_directory = store.root / "incident-corrupt"
    corrupt_directory.mkdir(parents=True)
    (corrupt_directory / "incident.json").write_text("{broken", encoding="utf-8")
    valid = _incident(incident_id="incident-valid")
    store.record(valid)

    assert store.pending() == (valid,)
    quarantined = tuple((store.root / "corrupt").iterdir())
    assert len(quarantined) == 1
    assert (quarantined[0] / "incident.json").read_text("utf-8") == "{broken"


def test_store_preserves_staged_fatal_evidence_until_incident_is_recorded(
    tmp_path: Path,
) -> None:
    """A pre-opened fatal log must not be mistaken for a corrupt incident."""

    store = CrashIncidentStore(tmp_path / "crashes")
    staged_directory = store.root / "run-in-progress"
    staged_directory.mkdir(parents=True)
    fault_log = staged_directory / "python-fault.log"
    fault_log.write_text("fatal traceback", encoding="utf-8")

    assert store.pending() == ()
    assert fault_log.read_text(encoding="utf-8") == "fatal traceback"
    assert not (store.root / "corrupt").exists()


def test_store_atomically_retains_external_crash_attachment(tmp_path: Path) -> None:
    """Crashpad evidence should be copied into the durable incident namespace."""

    store = CrashIncidentStore(tmp_path / "crashes")
    source = tmp_path / "crashpad" / "captured.dmp"
    source.parent.mkdir()
    source.write_bytes(b"minidump evidence")

    destination = store.retain_attachment("incident-1", source)

    assert destination == store.root / "incident-1" / "captured.dmp"
    assert destination.read_bytes() == b"minidump evidence"
    assert not tuple(destination.parent.glob("*.tmp"))


def test_store_prunes_only_acknowledged_incidents_beyond_retention(
    tmp_path: Path,
) -> None:
    """Bounded cleanup must preserve pending, corrupt, and newest evidence."""

    store = CrashIncidentStore(
        tmp_path / "crashes",
        acknowledged_retention_count=2,
        acknowledged_retention_days=365,
        now=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    acknowledged = (
        _incident(incident_id="acknowledged-oldest"),
        _incident(incident_id="acknowledged-middle"),
        _incident(incident_id="acknowledged-newest"),
    )
    dates = (
        "2026-08-01T12:00:00+00:00",
        "2026-08-02T12:00:00+00:00",
        "2026-08-03T12:00:00+00:00",
    )
    for incident, occurred_at in zip(acknowledged, dates, strict=True):
        dated = CrashIncident.from_json(
            {**incident.to_json(), "occurred_at_utc": occurred_at}
        )
        store.record(dated)
        store.acknowledge(dated.incident_id)
    pending = _incident(incident_id="still-pending")
    store.record(pending)
    corrupt = store.root / "acknowledged-corrupt"
    corrupt.mkdir()
    (corrupt / "incident.json").write_text("{broken", encoding="utf-8")
    (corrupt / "acknowledged").write_text("acknowledged\n", encoding="utf-8")

    removed = store.prune_acknowledged()

    assert removed == ()
    assert not (store.root / "acknowledged-oldest").exists()
    assert (store.root / "acknowledged-middle").is_dir()
    assert (store.root / "acknowledged-newest").is_dir()
    assert store.pending() == (pending,)
    assert (corrupt / "incident.json").read_text(encoding="utf-8") == "{broken"


@pytest.mark.parametrize(
    "unsafe_name",
    ("", ".", "..", "../escape", "nested/file", "nested\\file"),
)
def test_store_rejects_paths_outside_incident_namespace(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    """Untrusted incident and attachment names must remain within the store."""

    store = CrashIncidentStore(tmp_path / "crashes")

    with pytest.raises(ValueError):
        store.attachment_path("incident-1", unsafe_name)


def test_incident_rejects_unsafe_attachment_names() -> None:
    """Serialized incident attachments must never introduce path traversal."""

    with pytest.raises(ValueError):
        CrashIncident(
            incident_id="incident-1",
            run_id="run-1",
            occurred_at_utc="2026-08-31T12:00:00+00:00",
            kind=CrashKind.NATIVE,
            boundary=CrashBoundary.NATIVE_HANDLER,
            attribution=CrashAttribution.CONFIRMED,
            summary="Native crash",
            process_id=42,
            attachments=("../outside.dmp",),
        )
