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

"""Define the application boundary for probing host appearance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.domain.appearance.system_appearance import SystemAppearanceSnapshot


@dataclass(frozen=True, slots=True)
class SystemAppearanceProbe:
    """Pair normalized appearance values with adapter diagnostics."""

    snapshot: SystemAppearanceSnapshot
    adapter_name: str
    color_scheme_source: str | None = None
    accent_color_source: str | None = None


class SystemAppearanceProvider(Protocol):
    """Probe one fresh system appearance snapshot on demand."""

    def probe(self) -> SystemAppearanceProbe:
        """Return current system appearance values and their sources."""

        ...


__all__ = ["SystemAppearanceProbe", "SystemAppearanceProvider"]
