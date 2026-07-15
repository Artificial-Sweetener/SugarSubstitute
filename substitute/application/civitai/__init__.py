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

"""Expose CivitAI application services."""

from substitute.application.civitai.cache_service import CivitaiCacheService
from substitute.application.civitai.preference_service import CivitaiPreferenceService
from substitute.application.civitai.preference_service import (
    CivitaiPreferenceSaveResult,
)
from substitute.application.civitai.credential_service import CivitaiCredentialService
from substitute.application.civitai.download_path_template_renderer import (
    CivitaiDownloadPathTemplateError,
    CivitaiDownloadPathTemplateRenderer,
    normalize_base_model_bucket,
)

__all__ = [
    "CivitaiCacheService",
    "CivitaiCredentialService",
    "CivitaiDownloadPathTemplateError",
    "CivitaiDownloadPathTemplateRenderer",
    "CivitaiPreferenceSaveResult",
    "CivitaiPreferenceService",
    "normalize_base_model_bucket",
]
