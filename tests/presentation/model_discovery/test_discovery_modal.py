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

from dataclasses import replace
from pathlib import Path

from qfluentwidgets import CheckBox  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    styleSheetManager,
)

from substitute.domain.model_recommendations import ModelFamilyId
from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
    ModelSuggestionReference,
)
from substitute.presentation.model_discovery.discovery_card import ModelSuggestionCard
from substitute.presentation.model_discovery.discovery_modal import ModelDiscoveryModal
from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from substitute.presentation.widgets.menu_model import MenuItem


def _suggestion(index: int, context: ModelSuggestionContext) -> ModelSuggestion:
    """Build one provider-neutral modal card."""

    return ModelSuggestion(
        context=context,
        model_name=f"Model {index}",
        version_name=f"Version {index}",
        creator="Synthetic",
        sha256=f"{index:064x}",
        offers=(
            ModelAcquisitionOffer(
                reference=ModelSuggestionReference(
                    "provider",
                    "Synthetic Provider",
                    str(index),
                    str(index * 10),
                ),
                file_name=f"model-{index}.safetensors",
                size_bytes=index,
                download_url=f"https://provider.example/download/{index}",
                model_page_url=f"https://provider.example/models/{index}",
                thumbnail_url=None,
                provider_rank=index,
                access=(
                    ModelSuggestionAccess.API_KEY_REQUIRED
                    if index == 2
                    else ModelSuggestionAccess.PUBLIC
                ),
            ),
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
    registered_card_widgets = [
        widget
        for widget in list(styleSheetManager.widgets)
        if any(widget is card or card.isAncestorOf(widget) for card in cards)
    ]
    assert set(registered_card_widgets) == {card.portrait.checkbox for card in cards}
    assert all(isinstance(widget, CheckBox) for widget in registered_card_widgets)
    assert modal.selected_identity is None
    assert not modal.download_button.isEnabled()

    cards[0].portrait.checkbox.click()
    assert modal.selected_identity == suggestions[0].identity
    downloads: list[tuple[str, str]] = []
    modal.download_requested.connect(
        lambda identity, provider_id: downloads.append((identity, provider_id))
    )
    modal.download_button.click()
    assert downloads == [(suggestions[0].identity, "provider")]
    cards[1].portrait.checkbox.click()
    assert modal.selected_identity == suggestions[1].identity
    assert not cards[0].portrait.is_selected()
    assert cards[1].portrait.is_selected()
    assert modal.download_button.isEnabled()
    assert modal.download_button.text() == "Add Synthetic Provider key"

    credentials: list[tuple[str, str]] = []
    modal.credential_requested.connect(
        lambda identity, provider_id: credentials.append((identity, provider_id))
    )
    modal.download_button.click()
    modal.browse_button.click()

    assert credentials == [(suggestions[1].identity, "provider")]
    assert opened_urls == ["https://provider.example/sdxl"]
    modal.set_provider_credential_available("provider")
    assert modal.download_button.text() == "Download and use"
    modal.download_button.click()
    assert downloads[-1] == (suggestions[1].identity, "provider")
    modal.deleteLater()


def test_protected_card_uses_only_a_small_key_indicator(
    tmp_path: Path,
) -> None:
    """Keep credential entry in the footer and off the model thumbnail."""

    context = ModelSuggestionContext(ModelArtifactKind.CHECKPOINTS, ModelFamilyId.SDXL)
    suggestion = _suggestion(2, context)
    modal = ModelDiscoveryModal()
    modal.show_plan(ModelSuggestionPlan(context, (suggestion,), tmp_path, ()))
    card = modal.findChild(ModelSuggestionCard)
    assert card is not None
    assert not card.key_indicator.isHidden()
    assert card.key_indicator.width() <= 24
    assert modal.selected_identity is None
    assert not modal.download_button.isEnabled()
    card.portrait.checkbox.click()
    assert modal.download_button.text() == "Add Synthetic Provider key"
    modal.deleteLater()


def test_replaced_cards_leave_the_visible_gallery_immediately(tmp_path: Path) -> None:
    """Retire old controls before deferred Qt destruction processes them."""

    context = ModelSuggestionContext(ModelArtifactKind.CHECKPOINTS, ModelFamilyId.SDXL)
    first = _suggestion(1, context)
    second = _suggestion(2, context)
    modal = ModelDiscoveryModal()
    modal.show_plan(ModelSuggestionPlan(context, (first,), tmp_path, ()))
    retired_card = modal.findChild(ModelSuggestionCard)
    assert retired_card is not None

    modal.show_plan(ModelSuggestionPlan(context, (second,), tmp_path, ()))

    assert retired_card.isHidden()
    current_card = modal.findChildren(ModelSuggestionCard)[-1]
    assert current_card.identity == second.identity
    assert not current_card.isHidden()
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


def test_gallery_only_shows_status_when_it_adds_information(tmp_path: Path) -> None:
    """Keep cards free of repeated instructions while preserving state feedback."""

    context = ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS)
    suggestion = _suggestion(1, context)
    modal = ModelDiscoveryModal()

    modal.show_loading()
    assert not modal.status_label.isHidden()
    assert "Finding compatible models" in modal.status_label.text()

    modal.show_plan(
        ModelSuggestionPlan(context, (suggestion,), tmp_path, browse_urls=())
    )
    assert modal.status_label.isHidden()

    modal.set_downloading(suggestion)
    assert not modal.status_label.isHidden()
    assert "Downloading and verifying" in modal.status_label.text()

    modal.show_failure("Download failed")
    assert not modal.status_label.isHidden()
    assert modal.status_label.text() == "Download failed"

    modal.show_plan(ModelSuggestionPlan(context, (), tmp_path, browse_urls=()))
    assert not modal.status_label.isHidden()
    assert modal.status_label.text() == "No compatible models are available right now."
    modal.show_plan(
        ModelSuggestionPlan(context, (), tmp_path, browse_urls=()),
        public_only=True,
    )
    assert (
        modal.status_label.text()
        == "No models that can be downloaded without a key are available right now."
    )
    modal.reject()
    modal.deleteLater()


def test_discovery_names_and_explains_the_requested_model_type() -> None:
    """The reused offer should describe the model's purpose without UI jargon."""

    modal = ModelDiscoveryModal()
    modal.set_context(ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS))
    modal.show_loading()

    assert modal.title_label.text() == "Download an upscaler model?"
    assert (
        modal.description_label.text()
        == "Upscalers enlarge existing images and refine details."
    )

    modal.set_context(
        ModelSuggestionContext(ModelArtifactKind.DIFFUSION_MODELS, ModelFamilyId.ANIMA)
    )
    assert modal.title_label.text() == "Download an image model?"
    assert (
        modal.description_label.text()
        == "Image models create new images from your prompts."
    )
    modal.reject()
    modal.deleteLater()


def test_card_exposes_all_provider_links_and_selects_alternate_download() -> None:
    """A deduplicated card should identify and select every exact provider offer."""

    context = ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS)
    primary = _suggestion(1, context)
    openmodeldb_offer = replace(
        primary.primary_offer,
        reference=ModelSuggestionReference(
            "openmodeldb",
            "OpenModelDB",
            "4x-model",
            "a" * 64,
        ),
        model_page_url="https://openmodeldb.info/models/4x-model",
    )
    civitai_offer = replace(
        primary.primary_offer,
        reference=ModelSuggestionReference("civitai", "CivitAI", "20", "21"),
        model_page_url="https://civitai.com/models/20?modelVersionId=21",
    )
    suggestion = replace(primary, offers=(openmodeldb_offer, civitai_offer))
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record provider navigation without opening a browser."""

        opened_urls.append(url)
        return True

    parent = ModelDiscoveryModal()
    card = ModelSuggestionCard(
        suggestion,
        open_url=open_url,
        parent=parent,
    )

    menu = card.provider_menu_model()
    actions = tuple(entry for entry in menu.entries if isinstance(entry, MenuItem))

    assert [action.action_id for action in actions] == [
        "model_provider.view.openmodeldb",
        "model_provider.view.civitai",
        "model_provider.acquire.openmodeldb",
        "model_provider.acquire.civitai",
    ]
    assert card.selected_provider_id == "openmodeldb"
    assert actions[-1].callback is not None
    actions[-1].callback()
    assert card.selected_provider_id == "civitai"
    assert actions[1].callback is not None
    actions[1].callback()
    assert opened_urls == ["https://civitai.com/models/20?modelVersionId=21"]
    parent.deleteLater()
