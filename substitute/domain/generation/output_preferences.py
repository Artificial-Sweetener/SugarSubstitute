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

"""Define the complete generated-output preference aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .output_organization import DEFAULT_OUTPUT_PATH_PATTERN

OUTPUT_PREFERENCES_SCHEMA_VERSION = "2"


class OutputPersistenceMode(StrEnum):
    """Choose which workflow sources receive durable output files."""

    ALL = "all"
    FINAL_CUBE = "final_cube"


class JpegSizingMode(StrEnum):
    """Choose how JPEG companion encoding is constrained."""

    QUALITY = "quality"
    TARGET_SIZE = "target_size"


@dataclass(frozen=True, slots=True)
class OutputOrganizationSettings:
    """Configure the durable output root and relative path template."""

    output_root: Path | None = None
    path_pattern: str = DEFAULT_OUTPUT_PATH_PATTERN


@dataclass(frozen=True, slots=True)
class JpegOutputSettings:
    """Configure optional JPEG companions while PNG remains canonical."""

    enabled: bool = False
    sizing_mode: JpegSizingMode = JpegSizingMode.QUALITY
    quality: int = 100
    target_size_kib: int = 1024


@dataclass(frozen=True, slots=True)
class OutputPreferences:
    """Own every user-configurable durable output policy."""

    schema_version: str = OUTPUT_PREFERENCES_SCHEMA_VERSION
    organization: OutputOrganizationSettings = OutputOrganizationSettings()
    jpeg: JpegOutputSettings = JpegOutputSettings()
    persistence_mode: OutputPersistenceMode = OutputPersistenceMode.ALL


def default_output_preferences() -> OutputPreferences:
    """Return preferences that preserve durable PNG output for every source."""

    return OutputPreferences()


__all__ = [
    "default_output_preferences",
    "JpegOutputSettings",
    "JpegSizingMode",
    "OUTPUT_PREFERENCES_SCHEMA_VERSION",
    "OutputOrganizationSettings",
    "OutputPersistenceMode",
    "OutputPreferences",
]
