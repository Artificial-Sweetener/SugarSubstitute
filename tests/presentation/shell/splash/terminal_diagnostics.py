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

"""Persist narrow splash evidence beside JUnit output before native event delivery."""

from __future__ import annotations

import json
from pathlib import Path


class TerminalDiagnostics:
    """Retain each stage even when native Qt terminates the pytest worker."""

    def __init__(self, destination: Path | None, *, nodeid: str) -> None:
        """Use the runner's evidence destination without creating shared test state."""
        self._destination = destination
        self._nodeid = nodeid
        self._stages: list[dict[str, object]] = []

    def record(self, stage: str, state: dict[str, object]) -> None:
        """Flush one layout snapshot without dispatching or changing Qt state."""
        self._stages.append({"stage": stage, "state": state})
        if self._destination is None:
            return
        self._destination.parent.mkdir(parents=True, exist_ok=True)
        self._destination.write_text(
            json.dumps({"nodeid": self._nodeid, "stages": self._stages}, indent=2),
            encoding="utf-8",
        )
