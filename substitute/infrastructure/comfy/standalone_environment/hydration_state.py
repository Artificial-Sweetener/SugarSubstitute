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

"""Persist authoritative runtime-construction state across process interruption.

This is installation transaction state, not disposable cache. A created Python
executable does not establish that its package hydration has completed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from substitute.infrastructure.comfy.managed_setup_evidence import (
    load_json_object,
    write_json_object_atomic,
)


_LOGGER = logging.getLogger(__name__)


class StandaloneHydrationState:
    """Own the commit boundary for a standalone workspace's active environment."""

    def __init__(self, workspace: Path) -> None:
        """Bind construction evidence to its exact owning workspace."""

        self._path = workspace / ".substitute" / "standalone-hydration.json"

    @property
    def incomplete(self) -> bool:
        """Reject pending or unreadable transactions while retaining legacy access."""

        if not self._path.exists():
            return False
        record = load_json_object(self._path)
        if record is None:
            _LOGGER.warning(
                "Standalone hydration state is unreadable; runtime requires recovery"
            )
        return record != {"schema_version": 1, "phase": "complete"}

    @property
    def recorded(self) -> bool:
        """Distinguish legacy installations from transaction-aware installations."""

        return self._path.exists()

    def begin(self) -> None:
        """Persist intent before exposing any partially constructed runtime."""

        self._write("hydrating")

    def complete(self) -> None:
        """Publish completion only after every package has been hydrated."""

        self._write("complete")

    def _write(self, phase: str) -> None:
        """Replace the authoritative phase durably and record its transition."""

        write_json_object_atomic(self._path, {"schema_version": 1, "phase": phase})
        _LOGGER.info("Standalone hydration transaction transitioned | phase=%s", phase)
