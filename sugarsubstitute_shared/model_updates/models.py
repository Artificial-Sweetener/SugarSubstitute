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

"""Define authoritative usage and compatible update values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelCategory,
)


@dataclass(frozen=True, slots=True)
class ModelUpdatePreferences:
    """Capture explicit user consent for provider update checks."""

    enabled: bool = False


@dataclass(frozen=True, slots=True)
class ModelUsageRecord:
    """Record durable usage identity needed for relevant update checks."""

    sha256: str
    path: Path
    category: ModelCategory
    model_id: int | None
    version_id: int | None
    base_model: str | None
    usage_count: int
    last_used_at: datetime


@dataclass(frozen=True, slots=True)
class ModelUpdateProposal:
    """Offer one compatible version without replacing the current local file."""

    current: ModelUsageRecord
    candidate: DiscoveredModel


__all__ = [
    "ModelUpdatePreferences",
    "ModelUpdateProposal",
    "ModelUsageRecord",
]
