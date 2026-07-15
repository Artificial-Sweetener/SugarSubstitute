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

"""Persist and update Substitute-owned managed ComfyUI process metadata."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.managed_process_registry")
_REGISTRY_FILE_NAME = "managed_comfy_process.json"


@dataclass
class ManagedProcessRegistry:
    """Load and save the single managed ComfyUI ownership record for one install."""

    runtime_state_dir: Path

    def load(self) -> ManagedProcessMetadata | None:
        """Return the persisted metadata when one ownership record exists."""

        path = self._path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log_warning(
                _LOGGER,
                "Managed process registry could not be read",
                path=str(path),
            )
            return None
        if not isinstance(payload, dict):
            log_warning(
                _LOGGER,
                "Managed process registry payload was not an object",
                path=str(path),
            )
            return None
        try:
            return ManagedProcessMetadata.from_payload(payload)
        except (KeyError, TypeError, ValueError):
            log_warning(
                _LOGGER,
                "Managed process registry payload was invalid",
                path=str(path),
            )
            return None

    def save(self, metadata: ManagedProcessMetadata) -> ManagedProcessMetadata:
        """Persist the supplied managed ownership record."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(metadata.to_payload(), indent=2),
            encoding="utf-8",
        )
        return metadata

    def update_validation_timestamp(
        self,
        timestamp: str,
    ) -> ManagedProcessMetadata | None:
        """Persist the last successful validation timestamp when metadata exists."""

        current = self.load()
        if current is None:
            return None
        return self.save(current.with_validation_timestamp(timestamp))

    def clear(self) -> None:
        """Remove any persisted managed ownership record."""

        path = self._path()
        if path.exists():
            path.unlink()

    def clear_if_pid_matches(self, pid: int | None) -> None:
        """Remove the persisted record only when it still belongs to the supplied pid."""

        if pid is None:
            return
        current = self.load()
        if current is not None and current.pid == pid:
            self.clear()

    def _path(self) -> Path:
        """Return the persisted ownership record path."""

        return self.runtime_state_dir / _REGISTRY_FILE_NAME


__all__ = ["ManagedProcessRegistry"]
