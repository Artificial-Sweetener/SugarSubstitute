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

"""Verify headless picker evidence with deterministic provider boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtGui import QImage

from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
    ModelSuggestionReference,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from tools.render_openmodeldb_upscaler_picker import run_headless_qualification


def test_headless_upscaler_picker_renders_real_model_identity(
    tmp_path: Path,
) -> None:
    """The production card shows one real hash and both provider sources."""

    sha256 = "f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da"
    context = ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS)
    suggestion = ModelSuggestion(
        context=context,
        model_name="RealESRGAN_x4Plus Anime 6B",
        version_name="4× · ESRGAN",
        creator="xinntao",
        sha256=sha256,
        offers=(
            ModelAcquisitionOffer(
                reference=ModelSuggestionReference(
                    "openmodeldb",
                    "OpenModelDB",
                    "4x-realesrgan-x4plus-anime-6b",
                    sha256,
                ),
                file_name="RealESRGAN_x4plus_anime_6B.pth",
                size_bytes=17_000_000,
                download_url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
                model_page_url="https://openmodeldb.info/models/4x-realesrgan-x4plus-anime-6b",
                thumbnail_url=None,
                provider_rank=1,
                access=ModelSuggestionAccess.PUBLIC,
            ),
            ModelAcquisitionOffer(
                reference=ModelSuggestionReference(
                    "civitai", "CivitAI", "147821", "164904"
                ),
                file_name="realesrganX4plusAnime_v1.pt",
                size_bytes=17_000_000,
                download_url="https://civitai.com/api/download/models/164904?fileId=124735",
                model_page_url="https://civitai.com/models/147821?modelVersionId=164904",
                thumbnail_url=None,
                provider_rank=1,
                access=ModelSuggestionAccess.PUBLIC,
            ),
        ),
    )
    plan = ModelSuggestionPlan(
        context=context,
        suggestions=(suggestion,),
        destination=tmp_path / "upscale_models",
        browse_urls=(
            ("openmodeldb", "https://openmodeldb.info/"),
            ("civitai", "https://civitai.com/models?types=Upscaler"),
        ),
    )

    evidence = run_headless_qualification(
        artifact_root=tmp_path, plan=plan, thumbnail_assets={}
    )

    assert evidence["result"] == "passed"
    assert evidence["headless"] is True
    assert evidence["artifact_kind"] == "upscale_models"
    assert evidence["cards"] == 1
    assert evidence["source_mode"] == "injected_plan"
    assert evidence["download_enabled"] is True
    assert evidence["provider_order"] == [["openmodeldb", "civitai"]]
    assert evidence["provider_menu_actions"] == [
        [
            "model_provider.view.openmodeldb",
            "model_provider.view.civitai",
            "model_provider.acquire.openmodeldb",
            "model_provider.acquire.civitai",
        ]
    ]
    models = cast(list[dict[str, object]], evidence["models"])
    assert models[0]["sha256"] == sha256
    assert models[0]["thumbnail_rendered"] is False
    screenshot = Path(cast(str, evidence["screenshot"]))
    image = QImage(str(screenshot))
    assert screenshot.is_file()
    assert not image.isNull()
    assert image.width() >= 1000
    assert image.height() >= 700
    alternate_screenshot = Path(cast(str, evidence["civitai_source_screenshot"]))
    assert alternate_screenshot.is_file()
    assert not QImage(str(alternate_screenshot)).isNull()
    assert evidence["downloads_performed"] == 0
