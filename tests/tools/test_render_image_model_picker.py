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

"""Verify full-shell image-model discovery captures without network access."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtGui import QImage

from substitute.domain.model_recommendations import (
    ModelFamilyId,
    SUPPORTED_MODEL_FAMILIES,
)
from substitute.domain.model_metadata.models import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
    ModelSuggestionReference,
)
from tools.render_image_model_picker import run_headless_image_model_qualification


def test_sdxl_and_anima_render_in_contained_shell(tmp_path: Path) -> None:
    """Show both production modal contexts over real-shaped family offers."""

    content: dict[
        ModelFamilyId, tuple[ModelSuggestionPlan, dict[str, ThumbnailAsset]]
    ] = {
        family_id: (_plan(tmp_path, family_id), {})
        for family_id in (ModelFamilyId.SDXL, ModelFamilyId.ANIMA)
    }

    evidence = run_headless_image_model_qualification(
        artifact_root=tmp_path, content=content
    )

    assert evidence["result"] == "passed"
    assert evidence["source_mode"] == "injected_plan"
    assert evidence["downloads_performed"] == 0
    families = cast(dict[str, dict[str, object]], evidence["families"])
    for family_id in (ModelFamilyId.SDXL, ModelFamilyId.ANIMA):
        family = families[family_id.value]
        assert family["title"] == "Download an image model?"
        assert family["explanation"] == (
            "Image models create new images from your prompts."
        )
        assert family["cards"] == 1
        screenshot = Path(cast(str, family["screenshot"]))
        image = QImage(str(screenshot))
        assert screenshot.is_file()
        assert not image.isNull()
        assert image.width() >= 1000
        assert image.height() >= 700


def _plan(root: Path, family_id: ModelFamilyId) -> ModelSuggestionPlan:
    """Describe one exact family-compatible CivitAI offer for the render test."""

    context = ModelSuggestionContext(
        SUPPORTED_MODEL_FAMILIES.get(family_id).primary_artifact_kind,
        family_id,
    )
    name = "SDXL example" if family_id is ModelFamilyId.SDXL else "Anima example"
    suggestion = ModelSuggestion(
        context=context,
        model_name=name,
        version_name="v1",
        creator="creator",
        sha256=f"{1 if family_id is ModelFamilyId.SDXL else 2:064x}",
        offers=(
            ModelAcquisitionOffer(
                reference=ModelSuggestionReference("civitai", "CivitAI", "123", "456"),
                file_name="example.safetensors",
                size_bytes=100,
                download_url="https://civitai.com/api/download/models/456",
                model_page_url="https://civitai.com/models/123?modelVersionId=456",
                thumbnail_url=None,
                provider_rank=1,
                access=ModelSuggestionAccess.API_KEY_REQUIRED,
            ),
        ),
    )
    return ModelSuggestionPlan(
        context=context,
        suggestions=(suggestion,),
        destination=root / context.artifact_kind.value,
        browse_urls=(("civitai", "https://civitai.com/models"),),
    )
