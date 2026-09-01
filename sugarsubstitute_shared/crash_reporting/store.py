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

"""Persist authoritative crash incidents atomically until user acknowledgement."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile

from sugarsubstitute_shared.crash_reporting.model import CrashIncident


INCIDENT_FILENAME = "incident.json"
ACKNOWLEDGED_FILENAME = "acknowledged"
CORRUPT_DIRECTORY_NAME = "corrupt"
ACKNOWLEDGED_RETENTION_COUNT = 20
ACKNOWLEDGED_RETENTION_DAYS = 90
_LOGGER = logging.getLogger(__name__)


class CrashIncidentStore:
    """Own durable pending crash incidents below one diagnostics namespace."""

    def __init__(
        self,
        root: Path,
        *,
        acknowledged_retention_count: int = ACKNOWLEDGED_RETENTION_COUNT,
        acknowledged_retention_days: int = ACKNOWLEDGED_RETENTION_DAYS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Retain the authoritative crash namespace without creating it eagerly."""

        if acknowledged_retention_count < 0 or acknowledged_retention_days < 0:
            raise ValueError("Crash retention bounds cannot be negative.")
        self._root = root
        self._acknowledged_retention_count = acknowledged_retention_count
        self._acknowledged_retention_days = acknowledged_retention_days
        self._now = now or (lambda: datetime.now(timezone.utc))

    @property
    def root(self) -> Path:
        """Return the authoritative crash diagnostics root."""

        return self._root

    def record(self, incident: CrashIncident) -> Path:
        """Atomically create or replace one incident and return its directory."""

        incident_directory = self._incident_directory(incident.incident_id)
        incident_directory.mkdir(parents=True, exist_ok=True)
        _write_json_atomically(
            incident_directory / INCIDENT_FILENAME,
            incident.to_json(),
        )
        return incident_directory

    def pending(self) -> tuple[CrashIncident, ...]:
        """Return valid unacknowledged incidents and quarantine corrupt records."""

        if not self._root.is_dir():
            return ()
        incidents: list[CrashIncident] = []
        for incident_directory in sorted(
            self._root.iterdir(), key=lambda path: path.name
        ):
            if (
                not incident_directory.is_dir()
                or incident_directory.name == CORRUPT_DIRECTORY_NAME
            ):
                continue
            if (incident_directory / ACKNOWLEDGED_FILENAME).exists():
                continue
            incident_path = incident_directory / INCIDENT_FILENAME
            if not incident_path.exists():
                continue
            try:
                payload = json.loads(incident_path.read_text(encoding="utf-8"))
                incident = CrashIncident.from_json(payload)
                if incident.incident_id != incident_directory.name:
                    raise ValueError(
                        "Crash incident directory does not match its identifier."
                    )
            except (OSError, json.JSONDecodeError, ValueError):
                self._quarantine(incident_directory)
                continue
            incidents.append(incident)
        return tuple(incidents)

    def acknowledge(self, incident_id: str) -> None:
        """Atomically mark one incident handled while retaining its diagnostics."""

        incident_directory = self._incident_directory(incident_id)
        if not (incident_directory / INCIDENT_FILENAME).is_file():
            raise FileNotFoundError(f"Crash incident does not exist: {incident_id}")
        _write_text_atomically(
            incident_directory / ACKNOWLEDGED_FILENAME, "acknowledged\n"
        )
        self.prune_acknowledged()

    def prune_acknowledged(self) -> tuple[str, ...]:
        """Delete only acknowledged incidents beyond bounded count or age."""

        if not self._root.is_dir():
            return ()
        candidates: list[tuple[datetime, Path, str]] = []
        for directory in self._root.iterdir():
            if (
                not directory.is_dir()
                or directory.is_symlink()
                or directory.name == CORRUPT_DIRECTORY_NAME
                or not (directory / ACKNOWLEDGED_FILENAME).is_file()
            ):
                continue
            incident = self._read_incident(directory)
            if incident is None:
                continue
            try:
                occurred_at = datetime.fromisoformat(incident.occurred_at_utc)
            except ValueError:
                continue
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            candidates.append((occurred_at, directory, incident.incident_id))
        candidates.sort(key=lambda item: item[0], reverse=True)
        oldest_allowed = self._now() - timedelta(days=self._acknowledged_retention_days)
        removed: list[str] = []
        for index, (occurred_at, directory, incident_id) in enumerate(candidates):
            if (
                index < self._acknowledged_retention_count
                and occurred_at >= oldest_allowed
            ):
                continue
            try:
                shutil.rmtree(directory)
            except OSError:
                _LOGGER.warning(
                    "Acknowledged crash incident could not be pruned.",
                    extra={"incident_id": incident_id},
                    exc_info=True,
                )
                continue
            removed.append(incident_id)
        return tuple(removed)

    def _read_incident(self, incident_directory: Path) -> CrashIncident | None:
        """Read one valid incident without changing corrupt evidence."""

        try:
            payload = json.loads(
                (incident_directory / INCIDENT_FILENAME).read_text(encoding="utf-8")
            )
            incident = CrashIncident.from_json(payload)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        if incident.incident_id != incident_directory.name:
            return None
        return incident

    def attachment_path(self, incident_id: str, filename: str) -> Path:
        """Return a safe attachment path owned by one incident."""

        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
        ):
            raise ValueError("Crash attachment must be a safe filename.")
        return self._incident_directory(incident_id) / filename

    def retain_attachment(
        self,
        incident_id: str,
        source: Path,
        *,
        filename: str | None = None,
    ) -> Path:
        """Atomically copy external crash evidence into one incident."""

        destination = self.attachment_path(
            incident_id,
            source.name if filename is None else filename,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with source.open("rb") as source_file:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=destination.parent,
                    prefix=f".{destination.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    shutil.copyfileobj(source_file, temporary_file)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return destination

    def _incident_directory(self, incident_id: str) -> Path:
        """Return one incident directory after enforcing namespace containment."""

        if (
            not incident_id
            or incident_id in {".", ".."}
            or "/" in incident_id
            or "\\" in incident_id
        ):
            raise ValueError("Crash incident identifier is unsafe.")
        return self._root / incident_id

    def _quarantine(self, incident_directory: Path) -> None:
        """Move an unreadable incident aside without deleting diagnostic evidence."""

        corrupt_root = self._root / CORRUPT_DIRECTORY_NAME
        corrupt_root.mkdir(parents=True, exist_ok=True)
        destination = corrupt_root / incident_directory.name
        suffix = 1
        while destination.exists():
            destination = corrupt_root / f"{incident_directory.name}-{suffix}"
            suffix += 1
        os.replace(incident_directory, destination)


def _write_json_atomically(path: Path, payload: object) -> None:
    """Serialize one JSON document through a same-directory atomic replacement."""

    serialized = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    _write_text_atomically(path, serialized)


def _write_text_atomically(path: Path, content: str) -> None:
    """Durably replace one UTF-8 text file without exposing partial content."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


__all__ = ["CrashIncidentStore"]
