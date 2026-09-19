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

"""Own immutable paired application/runtime generations and atomic selection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Final

from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic


LEGACY_RELEASE_GENERATION: Final = "legacy-layout"
_RELEASE_RECORD_NAME: Final = "release.json"
_SELECTION_SCHEMA_VERSION: Final = 1
_RELEASE_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class ApplicationReleaseSelectionRecord:
    """Identify the active and last-known-good application generations."""

    current: str
    previous: str | None

    @classmethod
    def from_json(cls, payload: object) -> ApplicationReleaseSelectionRecord:
        """Parse one selection while rejecting redirected generation names."""

        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported application release selection schema.")
        current = _generation_name(payload.get("current"))
        raw_previous = payload.get("previous")
        previous = None if raw_previous is None else _generation_name(raw_previous)
        if previous == current:
            raise ValueError(
                "Application release selection cannot repeat a generation."
            )
        return cls(current=current, previous=previous)

    def to_json(self) -> dict[str, object]:
        """Return the stable atomic selection representation."""

        return {
            "current": self.current,
            "previous": self.previous,
            "schema_version": _SELECTION_SCHEMA_VERSION,
        }


class ApplicationReleaseSelection:
    """Prepare, activate, accept, reject, and retain paired release generations."""

    def __init__(self, install_root: Path) -> None:
        """Resolve generation storage beneath one installation root."""

        self._root = install_root.expanduser().resolve()
        self._releases = self._root / "launcher" / "releases"
        self._generations = self._releases / "generations"
        self._preparing = self._releases / "preparing"
        self._selection = self._releases / "active.json"

    @property
    def selection_path(self) -> Path:
        """Return the atomic active-generation record path."""

        return self._selection

    def prepare(self, *, generation: str, version: str) -> Path:
        """Create one empty transaction-owned generation at its permanent path."""

        name = _generation_name(generation)
        destination = self.generation_root(name)
        if destination.exists() or self.preparing_root(name).exists():
            raise ValueError("Application release generation already exists.")
        destination.mkdir(parents=True)
        write_json_atomic(
            destination / _RELEASE_RECORD_NAME,
            {
                "generation": name,
                "schema_version": _RELEASE_SCHEMA_VERSION,
                "status": "preparing",
                "version": _required_text(version),
            },
        )
        return destination

    def activate(self, *, generation: str) -> ApplicationReleaseSelectionRecord:
        """Seal one prepared generation and atomically make it current."""

        name = _generation_name(generation)
        prepared = self.candidate_root(name)
        record = self._read_release_record(prepared, expected_generation=name)
        if not (prepared / "app").is_dir() or not (prepared / "runtime").is_dir():
            raise ValueError("Prepared application release is incomplete.")
        current = self.load()
        destination = self.generation_root(name)
        if prepared != destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            prepared.replace(destination)
        self._write_release_status(destination, record, status="active")
        selected = ApplicationReleaseSelectionRecord(
            current=name,
            previous=current.current,
        )
        write_json_atomic(self._selection, selected.to_json())
        return selected

    def accept(self, *, generation: str) -> None:
        """Mark the selected generation as last-known-good after health readiness."""

        name = _generation_name(generation)
        selection = self.load()
        if selection.current != name:
            raise ValueError("Cannot accept a non-current application generation.")
        root = self.generation_root(name)
        record = self._read_release_record(root, expected_generation=name)
        self._write_release_status(root, record, status="accepted")

    def rollback(self, *, generation: str) -> ApplicationReleaseSelectionRecord:
        """Restore the prior selection and quarantine the failed generation."""

        name = _generation_name(generation)
        selection = self.load()
        if selection.current != name:
            raise ValueError("Cannot roll back a non-current application generation.")
        restored = ApplicationReleaseSelectionRecord(
            current=selection.previous or LEGACY_RELEASE_GENERATION,
            previous=None,
        )
        write_json_atomic(self._selection, restored.to_json())
        root = self.generation_root(name)
        record = self._read_release_record(root, expected_generation=name)
        self._write_release_status(root, record, status="rejected")
        return restored

    def abandon_preparation(self, *, generation: str) -> None:
        """Remove only the incomplete storage owned by one failed transaction."""

        name = _generation_name(generation)
        shutil.rmtree(self.preparing_root(name), ignore_errors=True)
        destination = self.generation_root(name)
        if not destination.exists():
            return
        record = self._read_release_record(destination, expected_generation=name)
        if record["status"] == "preparing":
            shutil.rmtree(destination, ignore_errors=True)

    def recover_failed_activation(self, *, generation: str) -> None:
        """Rollback a selected candidate or quarantine an interrupted publication."""

        name = _generation_name(generation)
        selection = self.load()
        if selection.current == name:
            self.rollback(generation=name)
            return
        self.abandon_preparation(generation=name)
        root = self.generation_root(name)
        if root.exists():
            record = self._read_release_record(root, expected_generation=name)
            self._write_release_status(root, record, status="rejected")

    def prune(self, *, retained_rejected: int = 2) -> None:
        """Bound unselected generations while retaining current rollback safety."""

        if retained_rejected < 0:
            raise ValueError("Retained rejected generation count cannot be negative.")
        selection = self.load()
        protected = {selection.current, selection.previous}
        candidates: list[tuple[Path, str]] = []
        if self._generations.exists():
            for root in self._generations.iterdir():
                if not root.is_dir() or root.name in protected:
                    continue
                record = self._read_release_record(
                    root, expected_generation=_generation_name(root.name)
                )
                candidates.append((root, str(record["status"])))
        rejected = sorted(
            (root for root, status in candidates if status == "rejected"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        retained = set(rejected[:retained_rejected])
        for root, _status in candidates:
            if root not in retained:
                shutil.rmtree(root)

    def load(self) -> ApplicationReleaseSelectionRecord:
        """Return the selected generations or the untouched legacy layout."""

        try:
            payload = json.loads(self._selection.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ApplicationReleaseSelectionRecord(
                current=LEGACY_RELEASE_GENERATION,
                previous=None,
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Application release selection is unreadable.") from error
        selection = ApplicationReleaseSelectionRecord.from_json(payload)
        self.release_root(selection.current)
        if selection.previous is not None:
            self.release_root(selection.previous)
        return selection

    def active_root(self) -> Path:
        """Return the immutable root selected for application and runtime paths."""

        return self.release_root(self.load().current)

    def release_root(self, generation: str) -> Path:
        """Resolve one selected release and require its sealed metadata."""

        name = _generation_name(generation)
        if name == LEGACY_RELEASE_GENERATION:
            return self._root
        root = self.generation_root(name)
        self._read_release_record(root, expected_generation=name)
        return root

    def preparing_root(self, generation: str) -> Path:
        """Return the legacy relocatable preparation path for recovery."""

        return self._preparing / _generation_name(generation)

    def candidate_root(self, generation: str) -> Path:
        """Resolve permanent preparation or a retained legacy transaction path."""

        name = _generation_name(generation)
        destination = self.generation_root(name)
        if destination.exists():
            return destination
        legacy = self.preparing_root(name)
        if legacy.exists():
            return legacy
        return destination

    def generation_root(self, generation: str) -> Path:
        """Return immutable storage for one safe generation identity."""

        return self._generations / _generation_name(generation)

    @staticmethod
    def _read_release_record(
        root: Path, *, expected_generation: str
    ) -> dict[str, object]:
        """Read and validate immutable generation metadata."""

        try:
            payload = json.loads(
                (root / _RELEASE_RECORD_NAME).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "Application release generation is unavailable."
            ) from error
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _RELEASE_SCHEMA_VERSION
            or payload.get("generation") != expected_generation
            or not isinstance(payload.get("version"), str)
            or payload.get("status")
            not in {"preparing", "active", "accepted", "rejected"}
        ):
            raise ValueError("Application release generation metadata is invalid.")
        return payload

    @staticmethod
    def _write_release_status(
        root: Path, record: dict[str, object], *, status: str
    ) -> None:
        """Atomically update only the generation's lifecycle status."""

        updated = dict(record)
        updated["status"] = status
        write_json_atomic(root / _RELEASE_RECORD_NAME, updated)


def _generation_name(value: object) -> str:
    """Return one path-safe generation identity."""

    text = _required_text(value)
    if text == LEGACY_RELEASE_GENERATION:
        return text
    if len(text) != 32 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError("Application release generation identity is invalid.")
    return text


def _required_text(value: object) -> str:
    """Return one non-empty text field."""

    if not isinstance(value, str) or not value:
        raise ValueError("Application release text must not be empty.")
    return value


__all__ = [
    "ApplicationReleaseSelection",
    "ApplicationReleaseSelectionRecord",
    "LEGACY_RELEASE_GENERATION",
]
