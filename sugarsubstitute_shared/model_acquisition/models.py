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

"""Define immutable progress and results for verified model downloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ModelAcquisitionError(RuntimeError):
    """Report an unsafe, unavailable, incomplete, or hash-mismatched download."""


class ModelAcquisitionCancelled(ModelAcquisitionError):
    """Report explicit cancellation after partial artifacts are cleaned up."""


@dataclass(frozen=True, slots=True)
class AcquisitionProgress:
    """Describe verified transfer progress without exposing authentication data."""

    bytes_received: int
    expected_bytes: int


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    """Describe one existing or newly committed SafeTensor file."""

    path: Path
    sha256: str
    size_bytes: int
    reused_existing: bool


__all__ = [
    "AcquisitionProgress",
    "AcquisitionResult",
    "ModelAcquisitionCancelled",
    "ModelAcquisitionError",
]
