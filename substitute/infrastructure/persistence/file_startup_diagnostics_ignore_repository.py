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

"""Persist ignored Comfy startup diagnostic fingerprints as JSON."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.startup_diagnostics_ignores")
_IGNORES_FILE_NAME = "startup_diagnostics_ignores.json"
_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FileStartupDiagnosticsIgnoreRepository(StartupDiagnosticsIgnoreRepository):
    """Load and save ignored startup incident fingerprints under diagnostics."""

    diagnostics_dir: Path

    def load_ignored_fingerprints(self) -> frozenset[str]:
        """Return ignored incident fingerprints or an empty set when unavailable."""

        path = self.path
        if not path.exists():
            return frozenset()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load startup diagnostics ignores; using none.",
                path=path,
                error=repr(error),
            )
            return frozenset()
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Startup diagnostics ignores file has unsupported root type.",
                path=path,
            )
            return frozenset()
        raw_entries = payload.get("ignored_fingerprints", [])
        if not isinstance(raw_entries, list):
            return frozenset()
        return frozenset(_fingerprint_from_entry(entry) for entry in raw_entries) - {""}

    def save_ignored_fingerprints(self, fingerprints: frozenset[str]) -> None:
        """Persist ignored incident fingerprints with stable JSON formatting."""

        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        ignored_at = datetime.now(UTC).isoformat()
        payload = {
            "version": _SCHEMA_VERSION,
            "ignored_fingerprints": [
                {
                    "fingerprint": fingerprint,
                    "ignored_at": ignored_at,
                }
                for fingerprint in sorted(fingerprints)
                if fingerprint
            ],
        }
        path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")

    @property
    def path(self) -> Path:
        """Return the startup diagnostics ignore JSON path."""

        return self.diagnostics_dir / _IGNORES_FILE_NAME


def _fingerprint_from_entry(entry: Any) -> str:
    """Return a fingerprint from one persisted ignore entry."""

    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        value = entry.get("fingerprint")
        if isinstance(value, str):
            return value
    return ""


__all__ = ["FileStartupDiagnosticsIgnoreRepository"]
