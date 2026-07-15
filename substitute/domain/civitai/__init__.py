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

"""Expose CivitAI integration preferences and policy models."""

from substitute.domain.civitai.preferences import (
    CIVITAI_PREFERENCES_SCHEMA_VERSION,
    CivitaiPreferences,
    CivitaiThumbnailSafetyPolicy,
    default_civitai_preferences,
)
from substitute.domain.civitai.download_organization import (
    DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN,
    CivitaiDownloadPathRenderContext,
    CivitaiDownloadPathRenderResult,
    CivitaiDownloadPathToken,
    SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKEN_NAMES,
    SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS,
)

__all__ = [
    "CIVITAI_PREFERENCES_SCHEMA_VERSION",
    "DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN",
    "CivitaiDownloadPathRenderContext",
    "CivitaiDownloadPathRenderResult",
    "CivitaiDownloadPathToken",
    "CivitaiPreferences",
    "CivitaiThumbnailSafetyPolicy",
    "SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKEN_NAMES",
    "SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS",
    "default_civitai_preferences",
]
