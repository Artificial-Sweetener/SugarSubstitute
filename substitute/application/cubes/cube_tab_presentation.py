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

"""Build display text for cube stack tabs from cube identity metadata."""

from __future__ import annotations

from dataclasses import dataclass
import re

_SEPARATOR = " · "


@dataclass(frozen=True)
class CubeTabPresentation:
    """Describe presentation text for one cube stack item."""

    primary_text: str
    secondary_text: str
    tooltip_text: str


def build_cube_tab_presentation(
    *,
    alias: str,
    cube_id: str,
    version: str,
) -> CubeTabPresentation:
    """Return stack-tab display text for one cube alias."""

    primary_text = alias.strip()
    version_text = _format_version(version)
    pack_text = _pack_name_from_cube_id(cube_id)
    secondary_parts = [part for part in (version_text, pack_text) if part]
    return CubeTabPresentation(
        primary_text=primary_text,
        secondary_text=_SEPARATOR.join(secondary_parts),
        tooltip_text=primary_text,
    )


def _format_version(version: str) -> str:
    """Return display-ready cube version text."""

    stripped = version.strip()
    if not stripped:
        return ""
    if stripped.lower().startswith("v"):
        return stripped
    return f"v{stripped}"


def _pack_name_from_cube_id(cube_id: str) -> str:
    """Return normalized repository segment from a canonical cube id."""

    parts = [part.strip() for part in cube_id.replace("\\", "/").split("/")]
    meaningful_parts = [part for part in parts if part]
    if len(meaningful_parts) < 2:
        return ""
    if len(meaningful_parts) >= 3:
        return _normalize_pack_segment(meaningful_parts[1])
    return _normalize_pack_segment(meaningful_parts[-2])


def _normalize_pack_segment(segment: str) -> str:
    """Return a compact lowercase pack name for toolbar metadata."""

    normalized = re.sub(r"[\s_]+", "-", segment.strip())
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-").lower()


__all__ = ["CubeTabPresentation", "build_cube_tab_presentation"]
