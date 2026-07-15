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

"""Define the application runtime mode used by compatibility policy."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum


class ApplicationRuntimeMode(Enum):
    """Identify whether Substitute is running from source or as a release build."""

    DEVELOPMENT = "development"
    RELEASE = "release"


@dataclass(frozen=True)
class ApplicationRuntimeModeService:
    """Resolve runtime mode once so policy checks do not infer it ad hoc."""

    mode: ApplicationRuntimeMode

    @classmethod
    def from_environment(cls) -> "ApplicationRuntimeModeService":
        """Build the service from explicit environment or packaging evidence."""

        configured = os.environ.get("SUBSTITUTE_RUNTIME_MODE", "").strip().lower()
        if configured in {"release", "packaged"}:
            return cls(ApplicationRuntimeMode.RELEASE)
        if configured in {"development", "dev", "source"}:
            return cls(ApplicationRuntimeMode.DEVELOPMENT)
        if bool(getattr(sys, "frozen", False)):
            return cls(ApplicationRuntimeMode.RELEASE)
        return cls(ApplicationRuntimeMode.DEVELOPMENT)

    def is_development(self) -> bool:
        """Return whether development-only compatibility allowances apply."""

        return self.mode is ApplicationRuntimeMode.DEVELOPMENT
