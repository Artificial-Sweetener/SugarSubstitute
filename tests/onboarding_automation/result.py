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

"""Represent and serialize one onboarding automation result."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class ScenarioResult:
    """Capture the observable result of one onboarding automation run."""

    scenario: str
    success: bool
    current_page: str
    status_text: str
    detail_text: str
    launch_command: tuple[str, ...]
    screenshot_dir: str

    def to_json(self) -> str:
        """Return the result as stable JSON."""

        return json.dumps(asdict(self), indent=2)


__all__ = ["ScenarioResult"]
