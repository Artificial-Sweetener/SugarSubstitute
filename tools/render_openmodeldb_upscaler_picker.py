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

"""Render real catalog upscalers in the production discovery picker headlessly."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Mapping, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

from substitute.app.bootstrap.lazy_civitai_client import LazyCivitaiClient  # noqa: E402
from substitute.app.bootstrap.persistent_cache_composition import (  # noqa: E402
    build_openmodeldb_catalog,
    build_recommendation_thumbnail_cache,
)
from substitute.app.bootstrap.persistent_cache_runtime import (  # noqa: E402
    prepare_persistent_cache_runtime,
)
from substitute.application.model_suggestions import ModelSuggestionEngine  # noqa: E402
from substitute.application.model_metadata import RichChoiceResolution  # noqa: E402
from substitute.domain.model_metadata import (  # noqa: E402
    CivitaiThumbnailPolicy,
    ThumbnailAsset,
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
    CachedOpenModelDbThumbnailFetcher,
    CivitaiModelSuggestionProvider,
    OpenModelDbSuggestionProvider,
    OpenModelDbThumbnailFetcher,
    require_openmodeldb_download_url,
)
from substitute.presentation.model_discovery import ModelDiscoveryModal  # noqa: E402
from substitute.presentation.model_discovery.discovery_overlay import (  # noqa: E402
    ModelDiscoveryOverlay,
)
from substitute.presentation.model_discovery.discovery_card import (  # noqa: E402
    ModelSuggestionCard,
)
from substitute.presentation.widgets.menu_model import MenuItem  # noqa: E402
from substitute.presentation.widgets.model_picker import ModelPickerField  # noqa: E402
from substitute.presentation.localization import (  # noqa: E402
    LocalizedBodyLabel,
    LocalizedSubtitleLabel,
)
from substitute.presentation.shell.window_frame import (  # noqa: E402
    SubstituteWindowFrame,
)
from sugarsubstitute_shared.localization import app_text  # noqa: E402
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService  # noqa: E402
from sugarsubstitute_shared.model_discovery import ModelArtifactKind  # noqa: E402
from tools.install_experience_capture import (  # noqa: E402
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ARTIFACT_ROOT = _REPO_ROOT / "build" / "qualification" / "openmodeldb"


class _EmptyChoiceSource:
    """Represent an empty connected picker in the visual qualification."""

    def __init__(self, artifact_kind: ModelArtifactKind) -> None:
        """Retain the model role presented by the empty picker."""

        self._artifact_kind = artifact_kind

    def current_resolution(self) -> RichChoiceResolution:
        """Return a stable empty rich-choice projection."""

        return RichChoiceResolution(
            items=(),
            should_use_rich_picker=True,
            matched_kinds=(self._artifact_kind.value,),
            option_count=0,
            enriched_count=0,
            ambiguous_count=0,
            unmatched_count=0,
            reason="qualification-empty-model-picker",
        )

    def refresh(self) -> RichChoiceResolution:
        """Keep the qualification picker empty without a backend."""

        return self.current_resolution()


def run_headless_qualification(
    *,
    artifact_root: Path = _DEFAULT_ARTIFACT_ROOT,
    plan: ModelSuggestionPlan | None = None,
    thumbnail_assets: Mapping[str, ThumbnailAsset] | None = None,
) -> dict[str, object]:
    """Render catalog-backed cards, allowing injected boundaries in UI tests."""

    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    register_qualification_font(application)
    setTheme(Theme.DARK)
    if (plan is None) != (thumbnail_assets is None):
        raise ValueError("Plan and thumbnail assets must be injected together.")
    source_mode = "live_catalog" if plan is None else "injected_plan"
    if plan is None:
        plan, thumbnail_assets = _load_live_content(artifact_root)
    assert thumbnail_assets is not None
    suggestions = plan.suggestions
    opened_urls: list[str] = []

    def record_url(url: str) -> bool:
        """Record unexpected navigation without opening an external browser."""

        opened_urls.append(url)
        return True

    modal = ModelDiscoveryModal(open_url=record_url)
    prepare_opaque_dark_capture_surface(modal)
    modal.show_plan(plan)
    modal.show()
    _settle(application)
    cards = modal.findChildren(ModelSuggestionCard)
    if len(cards) != len(suggestions):
        raise AssertionError("The production picker did not render every upscaler.")
    for card, suggestion in zip(cards, suggestions, strict=True):
        thumbnail = thumbnail_assets.get(suggestion.sha256)
        if thumbnail is not None and not card.set_thumbnail(thumbnail):
            raise AssertionError("The production card rejected its thumbnail.")
    cards[0].portrait.checkbox.click()
    _settle(application)
    screenshot_path = artifact_root / "openmodeldb-upscaler-picker.png"
    save_opaque_dark_widget_capture(modal, screenshot_path)
    menu_actions = [
        [
            entry.action_id
            for entry in card.provider_menu_model().entries
            if isinstance(entry, MenuItem)
        ]
        for card in cards
    ]
    civitai_source_screenshot: Path | None = None
    for card, actions in zip(cards, menu_actions, strict=True):
        if "model_provider.acquire.civitai" not in actions:
            continue
        civitai_action = next(
            entry
            for entry in card.provider_menu_model().entries
            if isinstance(entry, MenuItem)
            and entry.action_id == "model_provider.acquire.civitai"
        )
        assert civitai_action.callback is not None
        civitai_action.callback()
        if card.selected_provider_id != "civitai":
            raise AssertionError("The real card did not switch acquisition sources.")
        _settle(application)
        civitai_source_screenshot = (
            artifact_root / "openmodeldb-upscaler-civitai-source.png"
        )
        save_opaque_dark_widget_capture(modal, civitai_source_screenshot)
        break
    shell_screenshot, shell_civitai_screenshot = render_contained_shell(
        application,
        plan,
        thumbnail_assets,
        artifact_root,
    )
    evidence: dict[str, object] = {
        "schema_version": 1,
        "result": "passed",
        "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "production_surface": (
            f"{ModelDiscoveryModal.__module__}.{ModelDiscoveryModal.__name__}"
        ),
        "screenshot": str(screenshot_path),
        "contained_shell_screenshot": str(shell_screenshot),
        "contained_shell_civitai_screenshot": (
            str(shell_civitai_screenshot)
            if shell_civitai_screenshot is not None
            else None
        ),
        "civitai_source_screenshot": (
            str(civitai_source_screenshot)
            if civitai_source_screenshot is not None
            else None
        ),
        "artifact_kind": plan.context.artifact_kind.value,
        "cards": len(cards),
        "source_mode": source_mode,
        "selected_model": suggestions[0].model_name,
        "download_enabled": modal.download_button.isEnabled(),
        "provider_order": [
            [offer.reference.provider_id for offer in suggestion.offers]
            for suggestion in suggestions
        ],
        "provider_menu_actions": menu_actions,
        "models": [
            {
                "name": suggestion.model_name,
                "sha256": suggestion.sha256,
                "model_pages": [offer.model_page_url for offer in suggestion.offers],
                "thumbnail_url": suggestion.primary_offer.thumbnail_url,
                "thumbnail_rendered": suggestion.sha256 in thumbnail_assets,
            }
            for suggestion in suggestions
        ],
        "downloads_performed": 0,
        "external_urls_opened": len(opened_urls),
    }
    report_path = artifact_root / "evidence.json"
    report_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    modal.close()
    modal.deleteLater()
    application.processEvents()
    return evidence


def _load_live_content(
    artifact_root: Path,
) -> tuple[ModelSuggestionPlan, dict[str, ThumbnailAsset]]:
    """Resolve real offers and images through the application's provider stack."""

    runtime = prepare_persistent_cache_runtime(artifact_root / "cache")
    try:
        thumbnail_cache = build_recommendation_thumbnail_cache(runtime)
        catalog = build_openmodeldb_catalog(runtime.prepared)
        model_root = artifact_root / "managed-model-root"
        acquisition = ModelAcquisitionService(
            allowed_roots=(model_root,),
            allowed_extensions=(".safetensors", ".pth", ".pt"),
        )
        openmodeldb = OpenModelDbSuggestionProvider(
            catalog=catalog,
            thumbnails=CachedOpenModelDbThumbnailFetcher(
                fetcher=OpenModelDbThumbnailFetcher(),
                preparer=thumbnail_cache.preparer,
                asset_store=thumbnail_cache.assets,
            ),
            acquisition=ModelAcquisitionService(
                allowed_roots=(model_root,),
                download_url_validator=require_openmodeldb_download_url,
                allowed_extensions=(".safetensors", ".pth"),
            ),
        )
        thumbnail_policy = CivitaiThumbnailPolicy()
        civitai = CivitaiModelSuggestionProvider(
            recommendations=CivitaiFamilyRecommendationGateway(
                api_key_provider=lambda: None,
                thumbnail_policy_provider=lambda: thumbnail_policy,
            ),
            thumbnails=CachedRecommendationThumbnailFetcher(
                fetcher=CivitaiThumbnailFetcher(),
                preparer=thumbnail_cache.preparer,
                asset_store=thumbnail_cache.assets,
            ),
            acquisition=acquisition,
            upscaler_catalog=catalog,
            metadata=LazyCivitaiClient(api_key_provider=lambda: None),
            thumbnail_policy=thumbnail_policy,
        )
        engine = ModelSuggestionEngine((openmodeldb, civitai))
        context = ModelSuggestionContext(ModelArtifactKind.UPSCALE_MODELS)
        suggestions = engine.suggest(
            context,
            access_policy=ModelSuggestionAccessPolicy.CURRENT_USER,
            limit=8,
        )
        if len(suggestions) != 8:
            raise AssertionError("The live catalog lacks a curated upscaler.")
        plan = ModelSuggestionPlan(
            context=context,
            suggestions=suggestions,
            destination=model_root / "upscale_models",
            browse_urls=engine.browse_urls(context),
        )
        thumbnails = {
            suggestion.sha256: engine.fetch_thumbnail(suggestion)
            for suggestion in suggestions
            if suggestion.primary_offer.thumbnail_url is not None
        }
        return plan, thumbnails
    finally:
        runtime.close()


def render_contained_shell(
    application: QApplication,
    plan: ModelSuggestionPlan,
    thumbnails: Mapping[str, ThumbnailAsset],
    artifact_root: Path,
    *,
    capture_layer: (
        Callable[[QApplication, QWidget, ModelDiscoveryModal, Path], None] | None
    ) = None,
    select_first_protected: bool = False,
) -> tuple[Path, Path | None]:
    """Click the production empty picker and capture its full-shell modal wash."""

    family_id = plan.context.family_id
    role = family_id.value if family_id is not None else "upscaler"
    label = "Upscaler" if family_id is None else family_id.value.upper()
    screenshot_prefix = (
        "openmodeldb-upscaler" if family_id is None else f"civitai-{role}"
    )

    frame = SubstituteWindowFrame(backdrop_mode=None)
    frame.resize(1280, 820)
    prepare_opaque_dark_capture_surface(frame)
    body = QWidget(frame)
    body.setStyleSheet("QWidget { background-color: #181818; }")
    body_layout = QHBoxLayout(body)
    body_layout.setContentsMargins(20, 16, 20, 20)
    sidebar = QFrame(body)
    sidebar.setFixedWidth(380)
    sidebar.setStyleSheet("QFrame { background-color: #242222; border-radius: 8px; }")
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(22, 18, 22, 18)
    sidebar_layout.setSpacing(12)
    sidebar_layout.addWidget(LocalizedSubtitleLabel(app_text("Models"), sidebar))
    sidebar_layout.addWidget(LocalizedBodyLabel(app_text(label), sidebar))
    overlay = ModelDiscoveryOverlay(owner=frame)
    contained_modal = ModelDiscoveryModal(parent=overlay)
    overlay.attach(contained_modal)

    def open_discovery() -> None:
        """Follow the field's real empty-picker activation into the child modal."""

        overlay.present()
        contained_modal.show_loading()
        contained_modal.show_plan(plan)
        for suggestion in plan.suggestions:
            thumbnail = thumbnails.get(suggestion.sha256)
            if thumbnail is not None:
                contained_modal.set_thumbnail(suggestion.identity, thumbnail)

    picker = ModelPickerField(
        sidebar,
        choice_source=_EmptyChoiceSource(plan.context.artifact_kind),
        empty_model_action=open_discovery,
    )
    sidebar_layout.addWidget(picker)
    sidebar_layout.addStretch(1)
    body_layout.addWidget(sidebar)
    body_layout.addStretch(1)
    frame.add_body_widget(body)
    frame.show()
    _settle(application)
    button = picker.findChild(QAbstractButton, "modelPickerEmptyActionButton")
    if button is None or not picker.is_empty_action_visible():
        raise AssertionError("The empty model picker did not offer discovery.")
    button.click()
    _settle(application)
    if not overlay.isVisible() or contained_modal.isWindow():
        raise AssertionError("Model discovery escaped the owning shell.")
    if select_first_protected:
        protected_card = next(
            (
                card
                for card in contained_modal.findChildren(ModelSuggestionCard)
                if not card.key_indicator.isHidden()
            ),
            None,
        )
        if protected_card is None:
            raise AssertionError("The offer lacks a protected card to select.")
        protected_card.portrait.checkbox.click()
        _settle(application)
    screenshot = artifact_root / f"{screenshot_prefix}-contained-shell.png"
    save_opaque_dark_widget_capture(frame, screenshot)
    civitai_screenshot: Path | None = None
    for card in contained_modal.findChildren(ModelSuggestionCard):
        for entry in card.provider_menu_model().entries:
            if not isinstance(entry, MenuItem):
                continue
            if entry.action_id != "model_provider.acquire.civitai":
                continue
            assert entry.callback is not None
            entry.callback()
            _settle(application)
            civitai_screenshot = (
                artifact_root / f"{screenshot_prefix}-contained-shell-civitai.png"
            )
            save_opaque_dark_widget_capture(frame, civitai_screenshot)
            break
        if civitai_screenshot is not None:
            break
    if capture_layer is not None:
        capture_layer(application, frame, contained_modal, artifact_root)
    contained_modal.reject()
    overlay.hide()
    frame.close()
    frame.deleteLater()
    application.processEvents()
    return screenshot, civitai_screenshot


def register_qualification_font(application: QApplication) -> None:
    """Register Segoe UI for deterministic offscreen Fluent rendering."""

    windows_root = os.environ.get("WINDIR")
    if not windows_root:
        raise RuntimeError("WINDIR is required for headless Fluent rendering.")
    font_path = Path(windows_root) / "Fonts" / "segoeui.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if font_id < 0 or not families:
        raise RuntimeError(f"Could not register the render font: {font_path}")
    application.setFont(QFont(families[0], 10))


def _settle(application: QApplication) -> None:
    """Let layout and Fluent animation state settle before inspection."""

    application.processEvents()
    QTest.qWait(180)
    application.processEvents()


def main() -> int:
    """Render the picker and print the evidence path."""

    run_headless_qualification()
    print(_DEFAULT_ARTIFACT_ROOT / "evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "register_qualification_font",
    "render_contained_shell",
    "run_headless_qualification",
]
