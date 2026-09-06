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

"""Open validated onboarding provider links through the desktop shell."""

from __future__ import annotations

from urllib.parse import urlencode

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from substitute.domain.model_recommendations import (
    ModelFamilyId,
    SUPPORTED_MODEL_FAMILIES,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.onboarding.external_link_opener")
_CIVITAI_HOSTS = frozenset(
    {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}
)


def civitai_model_search_url(family_id: ModelFamilyId) -> str:
    """Return the family-filtered CivitAI checkpoint search page."""

    mapping = SUPPORTED_MODEL_FAMILIES.get(family_id).civitai
    additional_base_models = sorted(
        mapping.linked_base_models - {mapping.recommendation_base_model}
    )
    query = urlencode(
        [
            ("baseModel", mapping.recommendation_base_model),
            *(("baseModel", value) for value in additional_base_models),
            ("modelType", mapping.model_type),
        ]
    )
    return f"https://civitai.com/search/models?{query}"


def open_civitai_model_page(url: str) -> bool:
    """Open one validated HTTPS CivitAI model page in the default browser."""

    parsed = QUrl(url)
    path = parsed.path()
    if (
        parsed.scheme().casefold() != "https"
        or parsed.host().casefold() not in _CIVITAI_HOSTS
        or parsed.userInfo()
        or parsed.port(-1) not in {-1, 443}
        or not (
            path == "/models" or path.startswith("/models/") or path == "/search/models"
        )
    ):
        log_warning(
            _LOGGER,
            "Rejected unexpected onboarding model-page URL",
            host=parsed.host(),
        )
        return False
    if not QDesktopServices.openUrl(parsed):
        log_warning(
            _LOGGER,
            "The system could not open an onboarding model page",
            host=parsed.host(),
        )
        return False
    return True


__all__ = ["civitai_model_search_url", "open_civitai_model_page"]
