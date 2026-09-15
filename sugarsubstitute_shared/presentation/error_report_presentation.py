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

"""Describe shared report content independently from its window container."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from sugarsubstitute_shared.presentation.localization import ApplicationText
from sugarsubstitute_shared.presentation.error_report_glyph import ReportSeverity


@dataclass(frozen=True, slots=True)
class ErrorReportPresentation:
    """Describe everything rendered by the shared report surface."""

    title: ApplicationText
    message: ApplicationText
    severity: ReportSeverity
    summary_rows: tuple[tuple[ApplicationText, str], ...]
    report_text: str
    issue_action: Callable[[], None] | None = None
    dismiss_on_mask: bool = False
