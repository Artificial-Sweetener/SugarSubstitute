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

"""Verify visible picker discovery, credentials, transfer, and selection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QAbstractAnimation, QThread
from PySide6.QtWidgets import QWidget

from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
    ModelSuggestionReference,
)
from substitute.presentation.model_discovery import (
    ModelDiscoveryModal,
    ModelSuggestionCredentialCoordinator,
)
from substitute.presentation.model_discovery.credential_prompt import (
    CredentialPromptChoice,
)
from substitute.presentation.model_discovery.discovery_card import ModelSuggestionCard
from substitute.presentation.model_discovery.discovery_overlay import (
    ModelDiscoveryOverlay,
)
from substitute.presentation.shell.empty_model_picker_discovery_controller import (
    EmptyModelPickerDiscoveryController,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from substitute.domain.model_recommendations import ModelFamilyId
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition
from tests.presentation.shell.model_discovery.support import (
    CatalogFixture as _Catalog,
    DiscoveryServiceFixture,
    FailingCatalogFixture as _FailingCatalog,
    FailingThumbnailServiceFixture,
)


class _Credentials:
    """Expose deterministic credential state."""

    provider_id = "civitai"

    def __init__(
        self,
        *,
        configured: bool = False,
        approved: bool = True,
        public_only: bool = False,
        prompts: list[QWidget] | None = None,
    ) -> None:
        """Store initial key state."""

        self.configured = configured
        self.approved = approved
        self.public_only = public_only
        self.prompts = prompts if prompts is not None else []

    def has_credential(self) -> bool:
        """Return current test key state."""

        return self.configured

    def request_credential(self, parent: QWidget) -> bool:
        """Record an explicit protected selection and return configured consent."""

        self.prompts.append(parent)
        if self.approved:
            self.configured = True
        return self.approved

    def request_choice(
        self, parent: QWidget, *, protected_model_count: int
    ) -> CredentialPromptChoice:
        """Choose a stored key, key-free results, or cancellation."""

        assert protected_model_count == 1
        self.prompts.append(parent)
        if self.public_only:
            return CredentialPromptChoice.PUBLIC_ONLY
        if self.approved:
            self.configured = True
            return CredentialPromptChoice.SAVED
        return CredentialPromptChoice.CANCELLED


def _credential_coordinator(
    handler: _Credentials | None = None,
) -> ModelSuggestionCredentialCoordinator:
    """Return the provider-neutral coordinator with one CivitAI handler."""

    return ModelSuggestionCredentialCoordinator((handler or _Credentials(),))


def _suggestion(
    destination: Path,
    *,
    access: ModelSuggestionAccess = ModelSuggestionAccess.PUBLIC,
) -> tuple[ModelSuggestionContext, ModelSuggestionPlan]:
    """Return one exact Anima suggestion plan."""

    context = ModelSuggestionContext(
        ModelArtifactKind.DIFFUSION_MODELS,
        ModelFamilyId.ANIMA,
    )
    suggestion = ModelSuggestion(
        context=context,
        model_name="Popular model",
        version_name="v12",
        creator="Creator",
        sha256="a" * 64,
        offers=(
            ModelAcquisitionOffer(
                reference=ModelSuggestionReference("civitai", "CivitAI", "11", "12"),
                file_name="popular.safetensors",
                size_bytes=8,
                download_url="https://civitai.com/api/download/models/12",
                model_page_url="https://civitai.com/models/11",
                thumbnail_url=None,
                provider_rank=1,
                access=access,
            ),
        ),
    )
    return context, ModelSuggestionPlan(
        context=context,
        suggestions=(suggestion,),
        destination=destination,
        browse_urls=(("civitai", "https://civitai.com/models"),),
    )


def _dispose_controller(
    controller: EmptyModelPickerDiscoveryController,
    parent: QWidget,
) -> None:
    """Synchronously settle worker, modal, and parent native ownership."""

    controller.close()
    wait_for_qt_condition(lambda: not controller.running)
    wait_for_qt_condition(lambda: parent.findChild(ModelDiscoveryModal) is None)
    destroy_qt_object(parent)


def test_unavailable_target_does_not_open_discovery() -> None:
    """A target without acquisition support should fail before opening a modal."""

    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=None,
        catalog=_Catalog(),
        credentials=_credential_coordinator(),
    )
    context = ModelSuggestionContext(
        ModelArtifactKind.DIFFUSION_MODELS,
        ModelFamilyId.ANIMA,
    )

    assert controller.request_for_empty_picker(context, lambda _value: None) is False
    assert parent.findChild(ModelDiscoveryModal) is None
    _dispose_controller(controller, parent)


def test_discovery_lifecycle_remains_animation_graph_free(tmp_path: Path) -> None:
    """Keep native Qt animation objects out of every discovery modal."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(destination)
    service = DiscoveryServiceFixture(plan, destination / "popular.safetensors")
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    assert modal.findChildren(QAbstractAnimation) == []
    modal.reject()
    wait_for_qt_condition(lambda: not modal.isVisible())
    _dispose_controller(controller, parent)


@pytest.mark.platforms("windows")
def test_repeated_discovery_lifecycles_remain_animation_graph_free(
    tmp_path: Path,
) -> None:
    """Abuse the Windows gallery without rebuilding native animation graphs."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(destination)
    service = DiscoveryServiceFixture(plan, destination / "popular.safetensors")
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(),
    )

    retained_modal: ModelDiscoveryModal | None = None
    retained_card: ModelSuggestionCard | None = None
    task_threads = tuple(parent.findChildren(QThread))
    assert len(task_threads) == 1
    for _cycle in range(128):
        assert controller.request_for_empty_picker(context, lambda _value: None)
        modal = parent.findChild(ModelDiscoveryModal)
        assert modal is not None
        wait_for_qt_condition(lambda: not controller.running)
        assert modal.findChildren(QAbstractAnimation) == []
        assert tuple(parent.findChildren(QThread)) == task_threads
        card = modal.findChild(ModelSuggestionCard)
        assert card is not None
        if retained_modal is None:
            retained_modal = modal
            retained_card = card
        else:
            assert modal is retained_modal
            assert card is retained_card
        modal.reject()
        wait_for_qt_condition(lambda: not modal.isVisible())

    assert len(service.contexts) == 128
    _dispose_controller(controller, parent)


def test_public_selection_downloads_refreshes_and_selects_exact_value(
    tmp_path: Path,
) -> None:
    """A public choice should flow from open modal to the mounted picker value."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(destination)
    service = DiscoveryServiceFixture(
        plan, destination / "Anima" / "popular.safetensors"
    )
    catalog = _Catalog()
    selected_values: list[str] = []
    parent = QWidget()
    parent.show()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=catalog,
        credentials=_credential_coordinator(),
    )

    assert controller.request_for_empty_picker(context, selected_values.append)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None and modal.isVisible()
    assert modal.title_label.text() == "Download an image model?"
    overlay = parent.findChild(ModelDiscoveryOverlay)
    assert overlay is not None and overlay.isVisible()
    assert not modal.isWindow()
    assert not overlay.isWindow()
    assert overlay.geometry() == parent.rect()
    wait_for_qt_condition(
        lambda: modal.selected_identity is None and bool(service.contexts)
    )
    wait_for_qt_condition(lambda: bool(plan.suggestions) and not controller.running)
    assert modal.findChildren(QAbstractAnimation) == []
    modal.download_requested.emit(plan.suggestions[0].identity, "civitai")
    wait_for_qt_condition(lambda: selected_values == ["Anima/popular.safetensors"])

    assert service.acquired == [plan.suggestions[0].identity]
    assert catalog.invalidated == ["diffusion_models"]
    assert catalog.refreshed == ["diffusion_models"]
    wait_for_qt_condition(lambda: not modal.isVisible())
    assert not overlay.isVisible()
    _dispose_controller(controller, parent)


def test_protected_selection_prompts_only_when_no_key_is_configured(
    tmp_path: Path,
) -> None:
    """Authentication should be requested after—not before—the explicit choice."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = DiscoveryServiceFixture(plan, destination / "protected.safetensors")
    prompts: list[QWidget] = []
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(_Credentials(prompts=prompts)),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    assert prompts == []
    modal.download_requested.emit(plan.suggestions[0].identity, "civitai")
    wait_for_qt_condition(lambda: bool(service.acquired))

    assert prompts == [modal]
    _dispose_controller(controller, parent)


def test_footer_key_action_configures_provider_and_continues_download(
    tmp_path: Path,
) -> None:
    """Keep credential entry in the footer and continue the reviewed transfer."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = DiscoveryServiceFixture(plan, destination / "protected.safetensors")
    prompts: list[QWidget] = []
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(_Credentials(prompts=prompts)),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    card = modal.findChild(ModelSuggestionCard)
    assert card is not None
    assert not card.key_indicator.isHidden()
    card.portrait.checkbox.click()
    assert modal.download_button.text() == "Add CivitAI key"
    modal.download_button.click()

    assert prompts == [modal]
    wait_for_qt_condition(lambda: bool(service.acquired))
    assert service.acquired == [plan.suggestions[0].identity]
    _dispose_controller(controller, parent)


def test_key_layer_can_switch_to_models_without_a_key(tmp_path: Path) -> None:
    """A key-free choice refreshes suggestions and can return to all models."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    public_model = replace(
        plan.suggestions[0],
        sha256="b" * 64,
        offers=(
            replace(
                plan.suggestions[0].primary_offer,
                access=ModelSuggestionAccess.PUBLIC,
            ),
        ),
    )
    service = DiscoveryServiceFixture(plan, destination / "public.safetensors")
    service.public_plan = replace(plan, suggestions=(public_model,))
    prompts: list[QWidget] = []
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(
            _Credentials(public_only=True, prompts=prompts)
        ),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    protected_card = modal.findChild(ModelSuggestionCard)
    assert protected_card is not None
    protected_card.portrait.checkbox.click()
    modal.download_button.click()
    wait_for_qt_condition(
        lambda: (
            not controller.running
            and (card := modal.findChild(ModelSuggestionCard)) is not None
            and card.identity == public_model.identity
        )
    )

    assert prompts == [modal]
    public_card = modal.findChild(ModelSuggestionCard)
    assert public_card is not None
    assert public_card.key_indicator.isHidden()
    assert not modal.show_all_button.isHidden()
    public_card.portrait.checkbox.click()
    assert modal.download_button.text() == "Download and use"
    modal.show_all_button.click()
    wait_for_qt_condition(
        lambda: (
            not controller.running
            and (card := modal.findChild(ModelSuggestionCard)) is not None
            and card.identity == plan.suggestions[0].identity
        )
    )
    _dispose_controller(controller, parent)


def test_protected_selection_uses_existing_key_without_prompt(
    tmp_path: Path,
) -> None:
    """A configured key should let an explicit protected choice continue directly."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = DiscoveryServiceFixture(plan, destination / "protected.safetensors")
    prompts: list[QWidget] = []
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(
            _Credentials(configured=True, prompts=prompts)
        ),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    card = modal.findChild(ModelSuggestionCard)
    assert card is not None
    assert not card.key_indicator.isHidden()
    card.portrait.checkbox.click()
    modal.download_requested.emit(plan.suggestions[0].identity, "civitai")
    wait_for_qt_condition(lambda: bool(service.acquired))

    assert prompts == []
    _dispose_controller(controller, parent)


def test_cancelled_credential_prompt_never_starts_download(tmp_path: Path) -> None:
    """Declining credentials must leave the reviewed gallery open and unchanged."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = DiscoveryServiceFixture(plan, destination / "protected.safetensors")
    parent = QWidget()
    parent.show()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(_Credentials(approved=False)),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    modal.download_requested.emit(plan.suggestions[0].identity, "civitai")

    assert service.acquired == []
    assert modal.isVisible()
    _dispose_controller(controller, parent)


def test_one_thumbnail_failure_does_not_abort_remaining_gallery_work(
    tmp_path: Path,
) -> None:
    """Preview transport failures must settle per card without replacing the plan."""

    destination = tmp_path / "models" / "diffusion_models"
    context, initial_plan = _suggestion(destination)
    original = initial_plan.suggestions[0]
    first = replace(
        original,
        offers=(replace(original.primary_offer, thumbnail_url="https://example/1"),),
    )
    second = replace(
        original,
        offers=(
            replace(
                original.primary_offer,
                reference=ModelSuggestionReference("civitai", "CivitAI", "21", "22"),
                thumbnail_url="https://example/2",
            ),
        ),
        sha256="b" * 64,
    )
    plan = replace(initial_plan, suggestions=(first, second))
    service = FailingThumbnailServiceFixture(plan, destination / "popular.safetensors")
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_Catalog(),
        credentials=_credential_coordinator(),
    )

    assert controller.request_for_empty_picker(context, lambda _value: None)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(
        lambda: (
            not controller.running
            and len(service.thumbnail_calls) == 2
            and modal.status_label.isHidden()
        )
    )

    assert service.thumbnail_calls == [first.identity, second.identity]
    assert len(modal.findChildren(ModelSuggestionCard)) == 2
    _dispose_controller(controller, parent)


def test_catalog_refresh_failure_never_publishes_unconfirmed_picker_value(
    tmp_path: Path,
) -> None:
    """A downloaded file should remain retryable until Comfy confirms its catalog."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(destination)
    downloaded = destination / "popular.safetensors"
    service = DiscoveryServiceFixture(plan, downloaded)
    selected_values: list[str] = []
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=_FailingCatalog(),
        credentials=_credential_coordinator(),
    )

    assert controller.request_for_empty_picker(context, selected_values.append)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None
    wait_for_qt_condition(lambda: not controller.running)
    card = modal.findChild(ModelSuggestionCard)
    assert card is not None
    card.portrait.checkbox.click()
    modal.download_requested.emit(plan.suggestions[0].identity, "civitai")
    wait_for_qt_condition(lambda: not controller.running)

    assert downloaded.read_bytes() == b"verified"
    assert selected_values == []
    assert modal.cancel_button.isEnabled()
    assert modal.download_button.isEnabled()
    _dispose_controller(controller, parent)
