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

"""Verify the onboarding CivitAI browser boundary."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.onboarding.external_link_opener import (
    civitai_model_search_url,
    open_civitai_model_page,
)


def test_opener_accepts_only_civitai_https_model_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Open trusted model pages and reject origins, ports, and unrelated paths."""

    opened: list[str] = []

    def record_opened_url(url: QUrl) -> bool:
        """Record one trusted URL and report successful dispatch."""

        opened.append(url.toString())
        return True

    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        record_opened_url,
    )

    assert open_civitai_model_page("https://civitai.com/models/123/example")
    assert open_civitai_model_page("https://www.civitai.com/models")
    assert open_civitai_model_page(
        "https://civitai.red/models/934764/miaomiao-harem?modelVersionId=1142097"
    )
    assert open_civitai_model_page(civitai_model_search_url(ModelFamilyId.SDXL))
    assert not open_civitai_model_page("http://civitai.com/models/123")
    assert not open_civitai_model_page("https://civitai.example/models/123")
    assert not open_civitai_model_page("https://civitai.com:444/models/123")
    assert not open_civitai_model_page("https://user@civitai.com/models/123")
    assert not open_civitai_model_page("https://civitai.com/api/download/models/123")
    assert opened == [
        "https://civitai.com/models/123/example",
        "https://www.civitai.com/models",
        "https://civitai.red/models/934764/miaomiao-harem?modelVersionId=1142097",
        (
            "https://civitai.com/search/models?baseModel=Illustrious"
            "&baseModel=NoobAI&baseModel=Playground+v2&baseModel=Pony"
            "&baseModel=SDXL+0.9&baseModel=SDXL+1.0"
            "&baseModel=SDXL+1.0+LCM&baseModel=SDXL+Distilled"
            "&baseModel=SDXL+Hyper&baseModel=SDXL+Lightning"
            "&baseModel=SDXL+Turbo&modelType=Checkpoint"
        ),
    ]


def test_search_url_uses_each_family_provider_mapping() -> None:
    """Open browse actions on the compatible checkpoint catalog."""

    assert civitai_model_search_url(ModelFamilyId.ANIMA) == (
        "https://civitai.com/search/models?baseModel=Anima&modelType=Checkpoint"
    )
