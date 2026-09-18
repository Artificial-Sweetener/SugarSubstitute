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

"""Describe complete and partial model metadata refresh outcomes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelMetadataRefreshSummary:
    """Summarize the effects of one metadata refresh run."""

    discovered: int = 0
    fingerprint_requested: int = 0
    enriched: int = 0
    thumbnails_cached: int = 0
    not_found: int = 0
    skipped: int = 0
    no_sfw_thumbnail: int = 0
    failed: int = 0
    cancelled: bool = False
