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

"""Define output organization preferences and path-rendering value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_OUTPUT_PATH_PATTERN = "{date}\\{run}_{cube#}_{workflow}_{source}"


@dataclass(frozen=True)
class OutputPathPattern:
    """Describe one user-editable output path template."""

    value: str


@dataclass(frozen=True)
class OutputPathToken:
    """Describe one supported output path template token."""

    name: str
    description: str

    @property
    def placeholder(self) -> str:
        """Return the literal placeholder inserted into editable patterns."""

        return f"{{{self.name}}}"


@dataclass(frozen=True)
class OutputPathRenderContext:
    """Provide concrete values used to render output path templates."""

    workflow_name: str
    source: str
    cube: str
    output_run_number: int | None
    cube_number: int | None
    folder_image_number: int | None
    job_started_at: datetime
    width: int
    height: int
    index: int
    set_index: int
    seed: str = ""


@dataclass(frozen=True)
class OutputPathRenderResult:
    """Return a rendered output path and user-visible diagnostics."""

    path: Path
    display_path: str


@dataclass(frozen=True, slots=True)
class OutputRunBucket:
    """Describe the directory namespace used for `{run}` allocation."""

    key: str
    directory: Path
    display_label: str


SUPPORTED_OUTPUT_PATH_TOKENS: tuple[OutputPathToken, ...] = (
    OutputPathToken("run", "Committed generation run number"),
    OutputPathToken("cube#", "Cube order in workflow"),
    OutputPathToken("image#", "Folder-wide image number"),
    OutputPathToken("seed", "Generation seed"),
    OutputPathToken("workflow", "Workflow display name"),
    OutputPathToken("source", "Output source label"),
    OutputPathToken("cube", "Cube alias"),
    OutputPathToken("date", "Job start date"),
    OutputPathToken("time", "Job start time"),
    OutputPathToken("day", "Job start weekday"),
    OutputPathToken("width", "Output image width"),
    OutputPathToken("height", "Output image height"),
    OutputPathToken("index", "Output index within source"),
    OutputPathToken("set", "Output set number"),
)

SUPPORTED_OUTPUT_PATH_TOKEN_NAMES = frozenset(
    token.name for token in SUPPORTED_OUTPUT_PATH_TOKENS
)


__all__ = [
    "DEFAULT_OUTPUT_PATH_PATTERN",
    "OutputPathPattern",
    "OutputPathRenderContext",
    "OutputPathRenderResult",
    "OutputPathToken",
    "OutputRunBucket",
    "SUPPORTED_OUTPUT_PATH_TOKEN_NAMES",
    "SUPPORTED_OUTPUT_PATH_TOKENS",
]
