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

"""Define extension metadata lookup ports for startup diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ComfyExtensionMetadata:
    """Describe installed extension metadata from ComfyUI or local sources."""

    key: str
    version: str | None = None
    cnr_id: str | None = None
    aux_id: str | None = None
    repository_url: str | None = None
    issues_url: str | None = None
    source: str | None = None


class ComfyExtensionMetadataProvider(Protocol):
    """Resolve extension metadata for startup diagnostics."""

    def installed_extensions(self) -> Mapping[str, ComfyExtensionMetadata]:
        """Return metadata keyed by installed extension name."""


__all__ = ["ComfyExtensionMetadata", "ComfyExtensionMetadataProvider"]
