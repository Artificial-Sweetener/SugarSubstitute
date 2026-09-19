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

"""Expose the shared report severity glyph to app presentation."""

from sugarsubstitute_shared.presentation.error_report_glyph import (
    ReportSeverity,
    ReportSeverityGlyphWidget,
    header_glyph_size,
    header_icon_top_offset,
)

__all__ = [
    "ReportSeverity",
    "ReportSeverityGlyphWidget",
    "header_glyph_size",
    "header_icon_top_offset",
]
