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

"""Define immutable presentation state for installer and repair experience pages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExperiencePage(str, Enum):
    """Identify one production page in the setup and recovery experience."""

    INSTALL_LOCATION = "install_location"
    REPAIR_SCOPE = "repair_scope"
    REVIEW = "review"
    PROGRESS = "progress"
    COMPLETE = "complete"
    FAILURE = "failure"


class RepairChoice(str, Enum):
    """Identify the two user-authorized repair boundaries."""

    APPLICATION = "application"
    FULL_MANAGED_COMFY = "full_managed_comfy"


@dataclass(frozen=True, slots=True)
class ExperienceSnapshot:
    """Capture semantic UI evidence without relying on pixels."""

    page: ExperiencePage
    title: str
    primary_action: str
    secondary_action: str | None
    repair_choice: RepairChoice | None


__all__ = [
    "ExperiencePage",
    "ExperienceSnapshot",
    "RepairChoice",
]
