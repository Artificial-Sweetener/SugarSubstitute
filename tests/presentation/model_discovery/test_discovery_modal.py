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

"""Verify the reusable model suggestion gallery through its real controls."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.model_recommendations import ModelFamilyId
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
    ModelSuggestionReference,
)
from substitute.presentation.model_discovery.discovery_modal import (
    ModelDiscoveryModal,
    ModelSuggestionCard,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


def _suggestion(index: int, context: ModelSuggestionContext) -> ModelSuggestion:
    """Build one provider-neutral modal card."""

    return ModelSuggestion(
        reference=ModelSuggestionReference(
            "provider",
            "Synthetic Provider",
            str(index),
            str(index * 10),
        ),
        context=context,
        model_name=f"Model {index}",
        version_name=f"Version {index}",
        creator="Synthetic",
        file_name=f"model-{index}.safetensors",
        size_bytes=index,
        sha256=f"{index:064x}",
        download_url=f"https://provider.example/download/{index}",
        model_page_url=f"https://provider.example/models/{index}",
        thumbnail_url=None,
        provider_rank=index,
        access=(
            ModelSuggestionAccess.API_KEY_REQUIRED
            if index == 2
            else ModelSuggestionAccess.PUBLIC
        ),
    )


def test_gallery_requires_one_explicit_exclusive_selection(tmp_path: Path) -> None:
    """Cards should start unchecked and publish only the final reviewed choice."""

    context = ModelSuggestionContext(
        ModelArtifactKind.CHECKPOINTS,
        ModelFamilyId.SDXL,
    )
    suggestions = (_suggestion(1, context), _suggestion(2, context))
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record one provider browse request."""

        opened_urls.append(url)
        return True

    modal = ModelDiscoveryModal(open_url=open_url)
    modal.show_plan(
        ModelSuggestionPlan(
            context=context,
            suggestions=suggestions,
            destination=tmp_path,
            browse_urls=(("provider", "https://provider.example/sdxl"),),
        )
    )
    cards = modal.findChildren(ModelSuggestionCard)
    assert len(cards) == 2
    assert modal.selected_identity is None
    assert not modal.download_button.isEnabled()

    cards[0].portrait.checkbox.click()
    assert modal.selected_identity == suggestions[0].identity
    cards[1].portrait.checkbox.click()
    assert modal.selected_identity == suggestions[1].identity
    assert not cards[0].portrait.is_selected()
    assert cards[1].portrait.is_selected()
    assert modal.download_button.isEnabled()

    requests: list[str] = []
    modal.download_requested.connect(requests.append)
    modal.download_button.click()
    modal.browse_button.click()

    assert requests == [suggestions[1].identity]
    assert opened_urls == ["https://provider.example/sdxl"]
    modal.deleteLater()


def test_download_failure_restores_review_controls(tmp_path: Path) -> None:
    """A failed transfer must leave the selected card retryable or cancellable."""

    context = ModelSuggestionContext(
        ModelArtifactKind.CHECKPOINTS,
        ModelFamilyId.SDXL,
    )
    suggestion = _suggestion(1, context)
    modal = ModelDiscoveryModal()
    modal.show_plan(
        ModelSuggestionPlan(
            context=context,
            suggestions=(suggestion,),
            destination=tmp_path,
            browse_urls=(),
        )
    )
    card = modal.findChild(ModelSuggestionCard)
    assert card is not None
    card.portrait.checkbox.click()
    modal.set_downloading(suggestion)

    modal.show_failure("Synthetic transfer failure")

    assert card.isEnabled()
    assert modal.cancel_button.isEnabled()
    assert modal.download_button.isEnabled()
    modal.deleteLater()
