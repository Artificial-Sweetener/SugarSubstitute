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

"""Expose localization infrastructure adapters."""

from substitute.infrastructure.localization.comfy_i18n_client import (
    ComfyI18nCatalogClient,
    ComfyI18nLanguageSelection,
)
from substitute.infrastructure.localization.comfy_frontend_i18n_client import (
    ComfyFrontendI18nClient,
)

__all__ = [
    "ComfyI18nCatalogClient",
    "ComfyI18nLanguageSelection",
    "ComfyFrontendI18nClient",
]
