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

"""Define About Settings read models and static acknowledgement copy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sugarsubstitute_shared.localization import ApplicationText, app_text

ABOUT_PROJECT_SUMMARY: ApplicationText = app_text(
    "SugarSubstitute provides a focused PySide6 workspace for ComfyUI, with "
    "cube-based workflow composition, managed model metadata, prompt tooling, "
    "and integrated image canvas workflows."
)
ABOUT_SUPPORTERS: tuple[str, ...] = ()
ABOUT_SPECIAL_THANKS: tuple[str, ...] = ()


class AboutVersionStatus(Enum):
    """Identify whether an About version row is resolved or degraded."""

    AVAILABLE = "available"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    NOT_CONNECTED = "not_connected"


@dataclass(frozen=True, slots=True)
class AboutVersionRow:
    """Describe one component version displayed on the About Settings page."""

    component_key: str
    label: ApplicationText
    value: ApplicationText
    status: AboutVersionStatus
    subtitle: ApplicationText = ""
    authors: str = ""
    external_url: str = ""
    detail: ApplicationText = ""


@dataclass(frozen=True, slots=True)
class AboutInfoSnapshot:
    """Collect project and runtime facts for the About Settings page."""

    versions: tuple[AboutVersionRow, ...]
    project_summary: ApplicationText
    supporters: tuple[str, ...]
    special_thanks: tuple[str, ...]


__all__ = [
    "ABOUT_PROJECT_SUMMARY",
    "ABOUT_SPECIAL_THANKS",
    "ABOUT_SUPPORTERS",
    "AboutInfoSnapshot",
    "AboutVersionRow",
    "AboutVersionStatus",
]
