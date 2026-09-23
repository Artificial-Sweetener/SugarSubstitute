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

"""Render SDXL and Anima discovery inside the production shell modal."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

from substitute.app.bootstrap.persistent_cache_composition import (  # noqa: E402
    build_recommendation_thumbnail_cache,
)
from substitute.app.bootstrap.persistent_cache_runtime import (  # noqa: E402
    prepare_persistent_cache_runtime,
)
from substitute.application.civitai import CivitaiCredentialService  # noqa: E402
from substitute.application.ports.civitai_credential_store import (  # noqa: E402
    CredentialStoreStatus,
)
from substitute.application.model_suggestions import ModelSuggestionEngine  # noqa: E402
from substitute.domain.model_metadata import (  # noqa: E402
    CivitaiThumbnailPolicy,
    ThumbnailAsset,
)
from substitute.domain.model_recommendations import (  # noqa: E402
    ModelFamilyId,
    SUPPORTED_MODEL_FAMILIES,
)
from substitute.domain.model_suggestions import (  # noqa: E402
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
    ModelSuggestionPlan,
)
from substitute.infrastructure.model_recommendations import (  # noqa: E402
    CachedRecommendationThumbnailFetcher,
    CivitaiFamilyRecommendationGateway,
    CivitaiThumbnailFetcher,
)
from substitute.infrastructure.model_suggestions import (  # noqa: E402
    CivitaiModelSuggestionProvider,
)
from substitute.presentation.model_discovery.discovery_copy import (  # noqa: E402
    discovery_copy,
)
from substitute.presentation.model_discovery.credential_prompt import (  # noqa: E402
    CivitaiApiKeyPromptDialog,
)
from substitute.presentation.model_discovery.discovery_modal import (  # noqa: E402
    ModelDiscoveryModal,
)
from sugarsubstitute_shared.model_acquisition import (  # noqa: E402
    ModelAcquisitionService,
)
from sugarsubstitute_shared.presentation.localization import (  # noqa: E402
    render_application_text,
)
from tools.render_openmodeldb_upscaler_picker import (  # noqa: E402
    register_qualification_font,
    render_contained_shell,
)
from tools.install_experience_capture import (  # noqa: E402
    save_opaque_dark_widget_capture,
)

_ARTIFACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "qualification"
    / "image-model-picker"
)
_FAMILIES = (ModelFamilyId.SDXL, ModelFamilyId.ANIMA)
type ImageModelContent = Mapping[
    ModelFamilyId, tuple[ModelSuggestionPlan, Mapping[str, ThumbnailAsset]]
]


class _InMemoryCredentialStore:
    """Keep qualification credentials in memory and outside user settings."""

    def __init__(self) -> None:
        """Start without a configured key."""

        self._key: str | None = None

    def status(self) -> CredentialStoreStatus:
        """Describe the test-only in-memory storage boundary."""

        return CredentialStoreStatus(
            available=True, backend_name="Qualification memory"
        )

    def has_api_key(self) -> bool:
        """Return whether qualification stored a key."""

        return self._key is not None

    def load_api_key(self) -> str | None:
        """Return the test-owned in-memory key."""

        return self._key

    def save_api_key(self, api_key: str) -> None:
        """Keep a synthetic key in memory only."""

        self._key = api_key

    def clear_api_key(self) -> None:
        """Forget the synthetic key."""

        self._key = None


def run_headless_image_model_qualification(
    *,
    artifact_root: Path = _ARTIFACT_ROOT,
    content: ImageModelContent | None = None,
) -> dict[str, object]:
    """Capture both real-family modal offers with no acquisition side effects."""

    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    register_qualification_font(application)
    setTheme(Theme.DARK)
    source_mode = "live_civitai" if content is None else "injected_plan"
    if content is None:
        content = _load_live_content(artifact_root)
    family_evidence: dict[str, object] = {}
    for family_id in _FAMILIES:
        plan, thumbnails = content[family_id]
        if plan.context.family_id is not family_id or not plan.suggestions:
            raise AssertionError(f"The {family_id.value} picker has no family cards.")
        if source_mode == "live_civitai" and len(plan.suggestions) != 8:
            raise AssertionError(
                f"The {family_id.value} picker lacks eight real cards."
            )
        screenshot, _ = render_contained_shell(
            application,
            plan,
            thumbnails,
            artifact_root,
            capture_layer=lambda app, frame, modal, root: _capture_credential_layer(
                app,
                frame,
                modal,
                root,
                family_id,
                min(len(plan.suggestions), 5),
            ),
            select_first_protected=True,
        )
        credential_screenshot = (
            artifact_root / f"civitai-{family_id.value}-credential-layer.png"
        )
        multiple_model_screenshot = (
            artifact_root / f"civitai-{family_id.value}-credential-count-stress.png"
        )
        title, explanation = discovery_copy(plan.context)
        family_evidence[family_id.value] = {
            "screenshot": str(screenshot),
            "credential_layer_screenshot": str(credential_screenshot),
            "credential_count_stress_screenshot": (
                str(multiple_model_screenshot) if len(plan.suggestions) > 1 else None
            ),
            "title": render_application_text(title),
            "explanation": render_application_text(explanation),
            "cards": len(plan.suggestions),
            "rendered_thumbnails": len(thumbnails),
            "models": [
                {
                    "name": suggestion.model_name,
                    "sha256": suggestion.sha256,
                    "provider": suggestion.primary_offer.reference.provider_name,
                    "thumbnail_rendered": suggestion.sha256 in thumbnails,
                }
                for suggestion in plan.suggestions
            ],
        }
    evidence: dict[str, object] = {
        "result": "passed",
        "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "source_mode": source_mode,
        "downloads_performed": 0,
        "families": family_evidence,
    }
    (artifact_root / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


def _capture_credential_layer(
    application: QApplication,
    frame: QWidget,
    modal: ModelDiscoveryModal,
    artifact_root: Path,
    family_id: ModelFamilyId,
    stress_model_count: int,
) -> None:
    """Capture singular and plural key prompts without storing a credential."""

    credential = CivitaiCredentialService(_InMemoryCredentialStore())
    scenarios: list[tuple[int, Path]] = [
        (1, artifact_root / f"civitai-{family_id.value}-credential-layer.png")
    ]
    if stress_model_count > 1:
        scenarios.append(
            (
                stress_model_count,
                artifact_root
                / f"civitai-{family_id.value}-credential-count-stress.png",
            )
        )
    for protected_model_count, screenshot in scenarios:
        prompt = CivitaiApiKeyPromptDialog(
            credential_service=credential,
            parent=modal,
            open_url=lambda _url: True,
            protected_model_count=protected_model_count,
        )

        def capture_and_close() -> None:
            """Record the visible layer and cancel without storing a key."""

            application.processEvents()
            actions = (
                prompt.cancel_button,
                prompt.public_only_button,
                prompt.save_button,
            )
            if len({button.geometry().center().y() for button in actions}) != 1:
                raise AssertionError("Credential choices are not in one action row.")
            if any(
                left.geometry().right() >= right.geometry().left()
                for left, right in zip(actions, actions[1:])
            ):
                raise AssertionError("Credential choices overlap.")
            if (
                actions[0].geometry().top() - prompt.api_key_edit.geometry().bottom()
                < 24
            ):
                raise AssertionError("Credential choices crowd the key input.")
            save_opaque_dark_widget_capture(frame, screenshot)
            prompt.reject()

        QTimer.singleShot(0, capture_and_close)
        if prompt.request_key():
            raise AssertionError("Credential qualification unexpectedly stored a key.")
        prompt.deleteLater()


def _load_live_content(artifact_root: Path) -> ImageModelContent:
    """Resolve provider-ranked recommendations and real previews for both families."""

    runtime = prepare_persistent_cache_runtime(artifact_root / "cache")
    try:
        thumbnail_cache = build_recommendation_thumbnail_cache(runtime)
        model_root = artifact_root / "managed-model-root"
        provider = CivitaiModelSuggestionProvider(
            recommendations=CivitaiFamilyRecommendationGateway(
                api_key_provider=lambda: None,
                thumbnail_policy_provider=CivitaiThumbnailPolicy,
            ),
            thumbnails=CachedRecommendationThumbnailFetcher(
                fetcher=CivitaiThumbnailFetcher(),
                preparer=thumbnail_cache.preparer,
                asset_store=thumbnail_cache.assets,
            ),
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                allowed_extensions=(".safetensors", ".ckpt"),
            ),
        )
        engine = ModelSuggestionEngine((provider,))
        content: dict[
            ModelFamilyId, tuple[ModelSuggestionPlan, Mapping[str, ThumbnailAsset]]
        ] = {}
        for family_id in _FAMILIES:
            definition = SUPPORTED_MODEL_FAMILIES.get(family_id)
            context = ModelSuggestionContext(
                definition.primary_artifact_kind, family_id
            )
            suggestions = engine.suggest(
                context,
                access_policy=ModelSuggestionAccessPolicy.CURRENT_USER,
                limit=8,
            )
            plan = ModelSuggestionPlan(
                context=context,
                suggestions=suggestions,
                destination=model_root / context.artifact_kind.value,
                browse_urls=engine.browse_urls(context),
            )
            thumbnails: dict[str, ThumbnailAsset] = {}
            for suggestion in suggestions:
                if suggestion.primary_offer.thumbnail_url is not None:
                    thumbnails[suggestion.sha256] = engine.fetch_thumbnail(suggestion)
            content[family_id] = plan, thumbnails
        return content
    finally:
        runtime.close()


if __name__ == "__main__":
    run_headless_image_model_qualification()
    print(_ARTIFACT_ROOT / "evidence.json")


__all__ = ["run_headless_image_model_qualification"]
