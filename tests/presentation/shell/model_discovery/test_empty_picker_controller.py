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

import hashlib
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QWidget

from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
    ModelSuggestionReference,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.model_discovery import (
    ModelDiscoveryModal,
    ModelSuggestionCredentialCoordinator,
)
from substitute.presentation.model_discovery.discovery_modal import ModelSuggestionCard
from substitute.presentation.shell.empty_model_picker_discovery_controller import (
    EmptyModelPickerDiscoveryController,
)
from sugarsubstitute_shared.model_acquisition import AcquisitionResult
from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from substitute.domain.model_recommendations import ModelFamilyId
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _Catalog:
    """Record targeted catalog invalidation."""

    def __init__(self) -> None:
        """Initialize no invalidations."""

        self.invalidated: list[str | None] = []
        self.refreshed: list[str] = []

    def invalidate(self, kind: str | None = None) -> None:
        """Record one invalidation."""

        self.invalidated.append(kind)

    def refresh_models(self, kind: str) -> object:
        """Record one authoritative catalog refresh."""

        self.refreshed.append(kind)
        return ()


class _FailingCatalog(_Catalog):
    """Reject one post-download authoritative refresh."""

    def refresh_models(self, kind: str) -> object:
        """Record and fail a synthetic backend refresh."""

        super().refresh_models(kind)
        raise OSError("synthetic catalog refresh failure")


class _Credentials:
    """Expose deterministic credential state."""

    provider_id = "civitai"

    def __init__(
        self,
        *,
        configured: bool = False,
        approved: bool = True,
        prompts: list[QWidget] | None = None,
    ) -> None:
        """Store initial key state."""

        self.configured = configured
        self.approved = approved
        self.prompts = prompts if prompts is not None else []

    def has_credential(self) -> bool:
        """Return current test key state."""

        return self.configured

    def request_credential(self, parent: QWidget) -> bool:
        """Record an explicit protected selection and return configured consent."""

        self.prompts.append(parent)
        return self.approved


def _credential_coordinator(
    handler: _Credentials | None = None,
) -> ModelSuggestionCredentialCoordinator:
    """Return the provider-neutral coordinator with one CivitAI handler."""

    return ModelSuggestionCredentialCoordinator((handler or _Credentials(),))


class _Service:
    """Return one suggestion and materialize its exact backend value."""

    def __init__(self, plan: ModelSuggestionPlan, destination_file: Path) -> None:
        """Store deterministic discovery and acquisition results."""

        self.plan = plan
        self.destination_file = destination_file
        self.contexts: list[ModelSuggestionContext] = []
        self.acquired: list[str] = []

    def plan_empty_picker(self, context: ModelSuggestionContext) -> ModelSuggestionPlan:
        """Return the prepared plan."""

        self.contexts.append(context)
        return self.plan

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> object:
        """Reject unexpected preview requests in this no-thumbnail fixture."""

        raise AssertionError(suggestion)

    def acquire(
        self,
        plan: ModelSuggestionPlan,
        suggestion_identity: str,
        *,
        cancellation: object | None = None,
    ) -> tuple[ModelSuggestion, AcquisitionResult]:
        """Create the reviewed file and return its verified result."""

        _ = cancellation
        self.acquired.append(suggestion_identity)
        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        payload = b"verified"
        self.destination_file.write_bytes(payload)
        return (
            plan.suggestions[0],
            AcquisitionResult(
                path=self.destination_file,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                reused_existing=False,
            ),
        )


class _ThumbnailService(_Service):
    """Fail one thumbnail while settling every remaining card."""

    def __init__(self, plan: ModelSuggestionPlan, destination_file: Path) -> None:
        """Store deterministic work and preview calls."""

        super().__init__(plan, destination_file)
        self.thumbnail_calls: list[str] = []

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> object:
        """Fail the first card and return a deliberately undecodable second asset."""

        self.thumbnail_calls.append(suggestion.identity)
        if len(self.thumbnail_calls) == 1:
            raise OSError("synthetic thumbnail failure")
        return ThumbnailAsset("synthetic", 1, 1, 0, 4, "png", b"invalid")


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
        reference=ModelSuggestionReference("civitai", "CivitAI", "11", "12"),
        context=context,
        model_name="Popular model",
        version_name="v12",
        creator="Creator",
        file_name="popular.safetensors",
        size_bytes=8,
        sha256="a" * 64,
        download_url="https://civitai.com/api/download/models/12",
        model_page_url="https://civitai.com/models/11",
        thumbnail_url=None,
        provider_rank=1,
        access=access,
    )
    return context, ModelSuggestionPlan(
        context=context,
        suggestions=(suggestion,),
        destination=destination,
        browse_urls=(("civitai", "https://civitai.com/models"),),
    )


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
    controller.close()
    parent.deleteLater()


def test_public_selection_downloads_refreshes_and_selects_exact_value(
    tmp_path: Path,
) -> None:
    """A public choice should flow from open modal to the mounted picker value."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(destination)
    service = _Service(plan, destination / "Anima" / "popular.safetensors")
    catalog = _Catalog()
    selected_values: list[str] = []
    parent = QWidget()
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=parent,
        service=service,  # type: ignore[arg-type]
        catalog=catalog,
        credentials=_credential_coordinator(),
    )

    assert controller.request_for_empty_picker(context, selected_values.append)
    modal = parent.findChild(ModelDiscoveryModal)
    assert modal is not None and modal.isVisible()
    wait_for_qt_condition(
        lambda: modal.selected_identity is None and bool(service.contexts)
    )
    wait_for_qt_condition(lambda: bool(plan.suggestions) and not controller.running)
    modal.download_requested.emit(plan.suggestions[0].identity)
    wait_for_qt_condition(lambda: selected_values == ["Anima/popular.safetensors"])

    assert service.acquired == [plan.suggestions[0].identity]
    assert catalog.invalidated == ["diffusion_models"]
    assert catalog.refreshed == ["diffusion_models"]
    wait_for_qt_condition(lambda: parent.findChild(ModelDiscoveryModal) is None)
    controller.close()
    parent.deleteLater()


def test_protected_selection_prompts_only_when_no_key_is_configured(
    tmp_path: Path,
) -> None:
    """Authentication should be requested after—not before—the explicit choice."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = _Service(plan, destination / "protected.safetensors")
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
    modal.download_requested.emit(plan.suggestions[0].identity)
    wait_for_qt_condition(lambda: bool(service.acquired))

    assert prompts == [modal]
    controller.close()
    parent.deleteLater()


def test_protected_selection_uses_existing_key_without_prompt(
    tmp_path: Path,
) -> None:
    """A configured key should let an explicit protected choice continue directly."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = _Service(plan, destination / "protected.safetensors")
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
    card.portrait.checkbox.click()
    modal.download_requested.emit(plan.suggestions[0].identity)
    wait_for_qt_condition(lambda: bool(service.acquired))

    assert prompts == []
    controller.close()
    parent.deleteLater()


def test_cancelled_credential_prompt_never_starts_download(tmp_path: Path) -> None:
    """Declining credentials must leave the reviewed gallery open and unchanged."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(
        destination,
        access=ModelSuggestionAccess.API_KEY_REQUIRED,
    )
    service = _Service(plan, destination / "protected.safetensors")
    parent = QWidget()
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
    modal.download_requested.emit(plan.suggestions[0].identity)

    assert service.acquired == []
    assert modal.isVisible()
    controller.close()
    parent.deleteLater()


def test_one_thumbnail_failure_does_not_abort_remaining_gallery_work(
    tmp_path: Path,
) -> None:
    """Preview transport failures must settle per card without replacing the plan."""

    destination = tmp_path / "models" / "diffusion_models"
    context, initial_plan = _suggestion(destination)
    first = replace(initial_plan.suggestions[0], thumbnail_url="https://example/1")
    second = replace(
        initial_plan.suggestions[0],
        reference=ModelSuggestionReference("civitai", "CivitAI", "21", "22"),
        sha256="b" * 64,
        thumbnail_url="https://example/2",
    )
    plan = replace(initial_plan, suggestions=(first, second))
    service = _ThumbnailService(plan, destination / "popular.safetensors")
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
        lambda: not controller.running and len(service.thumbnail_calls) == 2
    )

    assert service.thumbnail_calls == [first.identity, second.identity]
    assert "Choose a model" in modal.status_label.text()
    controller.close()
    parent.deleteLater()


def test_catalog_refresh_failure_never_publishes_unconfirmed_picker_value(
    tmp_path: Path,
) -> None:
    """A downloaded file should remain retryable until Comfy confirms its catalog."""

    destination = tmp_path / "models" / "diffusion_models"
    context, plan = _suggestion(destination)
    downloaded = destination / "popular.safetensors"
    service = _Service(plan, downloaded)
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
    modal.download_requested.emit(plan.suggestions[0].identity)
    wait_for_qt_condition(lambda: not controller.running)

    assert downloaded.read_bytes() == b"verified"
    assert selected_values == []
    assert modal.cancel_button.isEnabled()
    assert modal.download_button.isEnabled()
    controller.close()
    parent.deleteLater()
