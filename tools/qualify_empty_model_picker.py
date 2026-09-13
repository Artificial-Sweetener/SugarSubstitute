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

"""Qualify empty-model discovery through production Qt surfaces without pytest."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import cast

from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from substitute.application.model_metadata import (
    ModelCatalogService,
    ModelChoiceCatalogIndex,
    RichChoiceResolver,
)
from substitute.application.model_suggestions import (
    ModelSuggestionEngine,
    ModelSuggestionProvider,
    ModelSuggestionService,
)
from substitute.application.model_suggestions.service import ModelDestinationPolicy
from substitute.application.node_behavior import FieldBehavior
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
    ModelSuggestionReference,
)
from substitute.presentation.editor.panel.factories.choice_factory import (
    ChoiceFieldBuildRequest,
    ChoiceFieldFactory,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.model_choice_snapshots import (
    PanelModelChoiceSnapshotRequest,
)
from substitute.presentation.model_discovery import (
    ModelDiscoveryModal,
    ModelSuggestionCredentialCoordinator,
)
from substitute.presentation.model_discovery.discovery_modal import ModelSuggestionCard
from substitute.presentation.shell.empty_model_picker_discovery_controller import (
    EmptyModelPickerDiscoveryController,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from sugarsubstitute_shared.model_acquisition import (
    AcquisitionResult,
    CancellationProbe,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind
from tools.model_lifecycle_qualification import (
    new_filesystem_catalog,
    runtime_evidence,
    wait_until,
)


_PAYLOAD = b"synthetic model qualification payload"


class _DestinationPolicy(ModelDestinationPolicy):
    """Keep every qualification artifact inside one synthetic model root."""

    def __init__(self, destination: Path) -> None:
        """Store the disposable model destination."""

        self._destination = destination

    def destination_for(self, artifact_kind: ModelArtifactKind) -> Path:
        """Return the synthetic diffusion-model folder."""

        if artifact_kind is not ModelArtifactKind.DIFFUSION_MODELS:
            raise ValueError(artifact_kind)
        return self._destination


class _SyntheticProvider(ModelSuggestionProvider):
    """Exercise provider-neutral discovery and verified acquisition locally."""

    provider_id = "synthetic"

    def __init__(self, *, access: ModelSuggestionAccess, file_name: str) -> None:
        """Store one deterministic suggestion without external network access."""

        self._access = access
        self._file_name = file_name

    def supports(self, context: ModelSuggestionContext) -> bool:
        """Support the exact Anima diffusion-model contract."""

        return context == _context()

    def suggest(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str],
    ) -> tuple[ModelSuggestion, ...]:
        """Return one compatible suggestion when its access policy permits it."""

        digest = hashlib.sha256(_PAYLOAD).hexdigest()
        if (
            limit < 1
            or digest in excluded_sha256
            or (
                self._access is ModelSuggestionAccess.API_KEY_REQUIRED
                and access_policy is ModelSuggestionAccessPolicy.PUBLIC_ONLY
            )
        ):
            return ()
        return (
            ModelSuggestion(
                reference=ModelSuggestionReference(
                    self.provider_id,
                    "Synthetic Registry",
                    "model-1",
                    "version-1",
                ),
                context=context,
                model_name="Synthetic Anima",
                version_name="v1",
                creator="Qualification",
                file_name=self._file_name,
                size_bytes=len(_PAYLOAD),
                sha256=digest,
                download_url="https://invalid.example/model",
                model_page_url="https://invalid.example/models/1",
                thumbnail_url=None,
                provider_rank=1,
                access=self._access,
            ),
        )

    def browse_url(self, context: ModelSuggestionContext) -> str:
        """Return a provider-owned compatibility browse route."""

        if not self.supports(context):
            raise ValueError(context)
        return "https://invalid.example/models?family=anima"

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Reject thumbnail work because this fixture publishes no thumbnail URL."""

        raise AssertionError(suggestion)

    def acquire(
        self,
        suggestion: ModelSuggestion,
        *,
        destination: Path,
        cancellation: CancellationProbe | None,
    ) -> AcquisitionResult:
        """Persist and verify one synthetic model exactly like a provider adapter."""

        if cancellation is not None and cancellation.is_cancelled():
            raise InterruptedError("Synthetic model acquisition was cancelled.")
        model_path = destination / "Anima" / suggestion.file_name
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(_PAYLOAD)
        return AcquisitionResult(
            path=model_path,
            sha256=hashlib.sha256(_PAYLOAD).hexdigest(),
            size_bytes=len(_PAYLOAD),
            reused_existing=False,
        )


class _CredentialHandler:
    """Record prompts caused only by explicit protected-model selection."""

    provider_id = "synthetic"

    def __init__(self) -> None:
        """Initialize with no configured credential and no prompts."""

        self.prompt_count = 0

    def has_credential(self) -> bool:
        """Return false so protected acquisition must request authorization."""

        return False

    def request_credential(self, parent: QWidget) -> bool:
        """Record a user-driven prompt and approve the synthetic qualification."""

        if not isinstance(parent, ModelDiscoveryModal):
            raise AssertionError("Credential prompt lost the discovery parent.")
        self.prompt_count += 1
        return True


def main(argv: Sequence[str] | None = None) -> int:
    """Run public and protected empty-picker flows and write durable evidence."""

    _ = argv
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    artifact_dir = Path("build/qualification/empty-model-picker").resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="SugarSubstitute-model-picker-") as root:
        model_root = Path(root) / "models"
        public_root = model_root / "public" / "diffusion_models"
        protected_root = model_root / "protected" / "diffusion_models"
        public = _qualify_flow(
            application,
            destination=public_root,
            access=ModelSuggestionAccess.PUBLIC,
            file_name="public.safetensors",
            screenshot_path=artifact_dir / "empty-model-picker.png",
        )
        protected = _qualify_flow(
            application,
            destination=protected_root,
            access=ModelSuggestionAccess.API_KEY_REQUIRED,
            file_name="protected.safetensors",
            screenshot_path=None,
        )
        restarted = {
            "public": _qualify_restart(
                application,
                destination=public_root,
                expected_values=("Anima/public.safetensors",),
            ),
            "protected": _qualify_restart(
                application,
                destination=protected_root,
                expected_values=("Anima/protected.safetensors",),
            ),
        }
    evidence = {
        "result": "passed",
        "public_flow": public,
        "protected_flow": protected,
        "persisted_after_application_restart": restarted,
        "runtime": runtime_evidence(),
        "external_network_used": False,
    }
    report_path = artifact_dir / "empty-model-picker-qualification.json"
    report_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(report_path)
    return 0


def _qualify_flow(
    application: QApplication,
    *,
    destination: Path,
    access: ModelSuggestionAccess,
    file_name: str,
    screenshot_path: Path | None,
) -> dict[str, object]:
    """Drive one actual field, modal, credential decision, and catalog refresh."""

    catalog, backend = new_filesystem_catalog(destination)
    if catalog.list_models("diffusion_models"):
        raise AssertionError("Qualification model catalog was not initially empty.")
    credential = _CredentialHandler()
    provider = _SyntheticProvider(access=access, file_name=file_name)
    service = ModelSuggestionService(
        destinations=_DestinationPolicy(destination),
        engine=ModelSuggestionEngine((provider,)),
    )
    root = QWidget()
    root.resize(420, 72)
    layout = QVBoxLayout(root)
    controller = EmptyModelPickerDiscoveryController(
        parent_widget=root,
        service=service,
        catalog=catalog,
        credentials=ModelSuggestionCredentialCoordinator((credential,)),
    )
    picker = _build_empty_picker(
        root,
        catalog=catalog,
        request=lambda context, receiver: _request_discovery(
            controller, context, receiver
        ),
    )
    layout.addWidget(picker)
    root.show()
    wait_until(application, picker.is_empty_action_visible, "empty action visibility")
    button = picker.findChild(QPushButton, "modelPickerEmptyActionButton")
    if button is None or button.size() != picker.contentsRect().size():
        raise AssertionError(
            "Empty discovery action does not fill the picker surface: "
            f"button={button.size() if button is not None else None}, "
            f"picker={picker.contentsRect().size()}."
        )
    if screenshot_path is not None and not root.grab().save(
        str(screenshot_path), "PNG"
    ):
        raise OSError(f"Could not save picker evidence to {screenshot_path}")
    button.click()
    modal = root.findChild(ModelDiscoveryModal)
    if modal is None or not modal.isVisible():
        raise AssertionError("The empty-picker action did not open its modal.")
    wait_until(application, lambda: not controller.running, "suggestion plan")
    if credential.prompt_count != 0:
        raise AssertionError("Credentials were requested before explicit selection.")
    card = modal.findChild(ModelSuggestionCard)
    if card is None:
        raise AssertionError("The suggestion modal did not render a model card.")
    card.portrait.checkbox.click()
    modal.download_button.click()
    expected_value = f"Anima/{file_name}"
    wait_until(
        application,
        lambda: picker.currentText() == expected_value and not controller.running,
        "verified model selection",
    )
    expected_prompts = 1 if access is ModelSuggestionAccess.API_KEY_REQUIRED else 0
    if credential.prompt_count != expected_prompts:
        raise AssertionError("Credential prompt policy disagreed with model access.")
    discovered_values = tuple(
        item.backend_value for item in catalog.list_models("diffusion_models")
    )
    if discovered_values != (expected_value,):
        raise AssertionError(
            "The refreshed production catalog did not expose the downloaded model: "
            f"{discovered_values}."
        )
    refresh_calls = tuple(
        (kinds, refresh) for kinds, refresh in backend.list_model_calls if refresh
    )
    if refresh_calls != ((("diffusion_models",), True),):
        raise AssertionError(f"Catalog refresh routing was not exact: {refresh_calls}.")
    if picker.is_empty_action_visible():
        raise AssertionError("Downloaded selection left the empty action visible.")
    controller.close()
    root.close()
    root.deleteLater()
    application.processEvents()
    return {
        "access": access.value,
        "credential_prompts_before_selection": 0,
        "credential_prompts_after_selection": credential.prompt_count,
        "selected_backend_value": expected_value,
        "catalog_values_after_refresh": discovered_values,
        "backend_refresh_calls": refresh_calls,
        "same_size_action": True,
    }


def _qualify_restart(
    application: QApplication,
    *,
    destination: Path,
    expected_values: tuple[str, ...],
) -> dict[str, object]:
    """Reconstruct catalog and picker owners and prove durable rediscovery."""

    catalog, backend = new_filesystem_catalog(destination)
    discovered_values = tuple(
        item.backend_value for item in catalog.list_models("diffusion_models")
    )
    if discovered_values != expected_values:
        raise AssertionError(
            "A fresh production catalog did not rediscover downloaded models: "
            f"expected={expected_values}, actual={discovered_values}."
        )
    root = QWidget()
    root.resize(420, 72)
    layout = QVBoxLayout(root)
    picker = _build_empty_picker(
        root,
        catalog=catalog,
        request=_reject_discovery_request,
        current_value=expected_values[0],
    )
    layout.addWidget(picker)
    root.show()
    application.processEvents()
    if picker.is_empty_action_visible():
        raise AssertionError("A freshly reconstructed populated picker stayed empty.")
    if picker.currentText() != expected_values[0]:
        raise AssertionError("A freshly reconstructed picker lost its selected value.")
    root.close()
    root.deleteLater()
    application.processEvents()
    return {
        "catalog_values": discovered_values,
        "picker_value": expected_values[0],
        "empty_action_visible": False,
        "backend_load_calls": backend.list_model_calls,
    }


def _reject_discovery_request(
    context: ModelSuggestionContext,
    receiver: Callable[[str], None],
) -> None:
    """Fail if a reconstructed populated picker exposes empty discovery."""

    _ = (context, receiver)
    raise AssertionError("A populated picker exposed empty-model discovery.")


def _build_empty_picker(
    parent: QWidget,
    *,
    catalog: ModelCatalogService,
    request: Callable[[ModelSuggestionContext, Callable[[str], None]], None],
    current_value: str = "",
) -> ModelPickerField:
    """Build the production SimpleLoadAnima field from its real empty identity."""

    resolver = RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=catalog)
    )
    snapshot = PanelModelChoiceSnapshotController(
        model_catalog_service=catalog,
        model_choice_resolver=resolver,
    ).snapshot_for_field(
        PanelModelChoiceSnapshotRequest(
            field_behavior=FieldBehavior(field_key="diffusion_model"),
            node_name="models",
            key="diffusion_model",
            value=current_value,
            node_type="SimpleSyrup.SimpleLoadAnima",
            field_type="LIST",
            field_info=[[], {}],
            node_definition_gateway=None,
            target_model="Anima",
        )
    )
    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent=parent,
            field_behavior=FieldBehavior(field_key="diffusion_model"),
            node_name="models",
            key="diffusion_model",
            value=current_value,
            field_meta={},
            model_choice_snapshot=snapshot,
            empty_model_picker_action=request,
            node_type="SimpleSyrup.SimpleLoadAnima",
            field_type="LIST",
            field_info=[[], {}],
        )
    )
    if not isinstance(widget, ModelPickerField):
        raise AssertionError(f"Empty Anima field built {type(widget).__name__}.")
    return widget


def _request_discovery(
    controller: EmptyModelPickerDiscoveryController,
    context: ModelSuggestionContext,
    receiver: Callable[[str], None],
) -> None:
    """Open discovery while keeping the widget callback contract void-returning."""

    if not controller.request_for_empty_picker(context, receiver):
        raise AssertionError("Configured model discovery refused an empty picker.")


def _context() -> ModelSuggestionContext:
    """Return the exact Anima diffusion-model compatibility request."""

    return ModelSuggestionContext(
        artifact_kind=ModelArtifactKind.DIFFUSION_MODELS,
        family_id=ModelFamilyId.ANIMA,
    )


if __name__ == "__main__":
    raise SystemExit(main())
