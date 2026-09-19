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

"""Define immutable application-payload staging and installation results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PayloadInstallError(RuntimeError):
    """Report an application payload that cannot be staged or promoted safely."""


@dataclass(frozen=True, slots=True)
class StagedAppPayload:
    """Describe one verified application payload without installed mutations."""

    version: str
    staging_dir: Path


@dataclass(frozen=True, slots=True)
class AppPayloadInstallResult:
    """Describe an installed application payload version."""

    version: str
    app_dir: Path


__all__ = [
    "AppPayloadInstallResult",
    "PayloadInstallError",
    "StagedAppPayload",
]
