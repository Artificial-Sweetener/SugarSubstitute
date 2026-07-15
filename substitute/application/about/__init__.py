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

"""Expose About Settings application services and models."""

from substitute.application.about.about_info_service import AboutInfoService
from substitute.application.about.license_text import (
    ABOUT_LICENSE_PREAMBLE,
    GPL_V3_LICENSE_HTML,
)
from substitute.application.about.models import (
    ABOUT_PROJECT_SUMMARY,
    ABOUT_SPECIAL_THANKS,
    ABOUT_SUPPORTERS,
    AboutInfoSnapshot,
    AboutVersionRow,
    AboutVersionStatus,
)

__all__ = [
    "ABOUT_LICENSE_PREAMBLE",
    "ABOUT_PROJECT_SUMMARY",
    "ABOUT_SPECIAL_THANKS",
    "ABOUT_SUPPORTERS",
    "AboutInfoService",
    "AboutInfoSnapshot",
    "AboutVersionRow",
    "AboutVersionStatus",
    "GPL_V3_LICENSE_HTML",
]
