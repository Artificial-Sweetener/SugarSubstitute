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

"""Render eight real installer upscalers and mixed-provider link results headlessly."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

from substitute.app.bootstrap.persistent_cache_composition import (  # noqa: E402
    build_openmodeldb_catalog,
    build_recommendation_thumbnail_cache,
)
from substitute.app.bootstrap.persistent_cache_runtime import (  # noqa: E402
    prepare_persistent_cache_runtime,
)
from substitute.application.execution import CancellationSource  # noqa: E402
from substitute.application.model_recommendations import (  # noqa: E402
    FamilyRecommendationPage,
    ModelOnboardingApplicationService,
    RecommendationCardAsset,
    RecommendationLinkStatus,
)
from substitute.application.model_recommendations.onboarding_service import (  # noqa: E402
    ModelFamilyScanner,
)
from substitute.domain.model_recommendations import (  # noqa: E402
    ModelFamilyId,
    ModelRecommendationQuery,
)
from substitute.infrastructure.model_recommendations import (  # noqa: E402
    CachedRecommendationThumbnailFetcher,
    CivitaiFamilyRecommendationGateway,
    CivitaiThumbnailFetcher,
    ProviderRecommendationGateway,
    ProviderRecommendationThumbnailFetcher,
)
from substitute.infrastructure.model_suggestions import (  # noqa: E402
    CachedOpenModelDbThumbnailFetcher,
    OpenModelDbThumbnailFetcher,
)
from substitute.presentation.onboarding.model_onboarding_session import (  # noqa: E402
    ModelOnboardingSession,
)
from substitute.presentation.onboarding.onboarding_model_link_import import (  # noqa: E402
    ModelLinkImportOverlay,
)
from substitute.presentation.onboarding.onboarding_models import (  # noqa: E402
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_recommendation_pages import (  # noqa: E402
    ModelRecommendationPage,
)
from substitute.presentation.onboarding.onboarding_style_sheet import (  # noqa: E402
    build_onboarding_style_sheet,
)
from sugarsubstitute_shared.presentation.installer_surface import (  # noqa: E402
    build_installer_surface_style_sheet,
)
from tools.install_experience_capture import (  # noqa: E402
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)

_ARTIFACT_ROOT = (
    Path(__file__).resolve().parents[1] / "build" / "qualification" / "openmodeldb"
)
_OPENMODELDB_LINK = "https://openmodeldb.info/models/4x-UltraSharpV2"
_CIVITAI_LINK = "https://civitai.com/models/116225?modelVersionId=125843"


def run_headless_installer_qualification(
    *, artifact_root: Path = _ARTIFACT_ROOT
) -> dict[str, object]:
    """Capture live catalog cards and both exact-file link import sources."""

    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    _register_font(application)
    setTheme(Theme.DARK)
    runtime = prepare_persistent_cache_runtime(artifact_root / "installer-cache")
    try:
        cache = build_recommendation_thumbnail_cache(runtime)
        gateway = ProviderRecommendationGateway(
            civitai=CivitaiFamilyRecommendationGateway(),
            openmodeldb=build_openmodeldb_catalog(runtime.prepared),
        )
        thumbnails = ProviderRecommendationThumbnailFetcher(
            civitai=CachedRecommendationThumbnailFetcher(
                fetcher=CivitaiThumbnailFetcher(),
                preparer=cache.preparer,
                asset_store=cache.assets,
            ),
            openmodeldb=CachedOpenModelDbThumbnailFetcher(
                fetcher=OpenModelDbThumbnailFetcher(),
                preparer=cache.preparer,
                asset_store=cache.assets,
            ),
        )
        recommendations = gateway.discover(
            ModelRecommendationQuery(ModelFamilyId.UPSCALERS), limit=8
        )
        if len(recommendations) != 8:
            raise AssertionError("The live catalog did not resolve eight upscalers.")
        cards: list[RecommendationCardAsset] = []
        for recommendation in recommendations:
            if recommendation.thumbnail_url is None:
                cards.append(
                    RecommendationCardAsset(recommendation, thumbnail_failed=True)
                )
            else:
                cards.append(
                    RecommendationCardAsset(
                        recommendation, thumbnail=thumbnails.fetch(recommendation)
                    )
                )
        upscaler_page = FamilyRecommendationPage(ModelFamilyId.UPSCALERS, tuple(cards))
        session = ModelOnboardingSession(
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        )
        session.answer_existing_folder(False)
        session.select_missing_families(frozenset())
        pages = (
            FamilyRecommendationPage(ModelFamilyId.SDXL, ()),
            FamilyRecommendationPage(ModelFamilyId.ANIMA, ()),
            upscaler_page,
        )
        if not session.accept_recommendations(pages):
            raise AssertionError("The installer rejected the real recommendation page.")
        session.set_page_index(2)
        selected_ids = session.state.selected_version_ids
        if len(selected_ids) != 8:
            raise AssertionError(
                "Eight missing upscalers were not selected by default."
            )

        page = ModelRecommendationPage()
        page.resize(1180, 860)
        prepare_opaque_dark_capture_surface(page)
        page.setStyleSheet(
            page.styleSheet()
            + build_onboarding_style_sheet()
            + build_installer_surface_style_sheet()
        )
        page.set_recommendations(
            upscaler_page,
            selected_version_ids=selected_ids,
            use_own_model=False,
        )
        page.show()
        _settle(application)
        picker_path = artifact_root / "openmodeldb-installer-eight-selected.png"
        save_opaque_dark_widget_capture(page, picker_path)

        service = ModelOnboardingApplicationService(
            scanner=cast(ModelFamilyScanner, object()),
            gateway=gateway,
            thumbnail_fetcher=thumbnails,
        )
        links = (_OPENMODELDB_LINK, _CIVITAI_LINK)
        results = service.resolve_model_links(
            ModelFamilyId.UPSCALERS,
            links,
            cancellation=CancellationSource(generation=1),
            excluded_version_ids=selected_ids,
        )
        if len(results) != 2 or any(
            item.status is not RecommendationLinkStatus.READY for item in results
        ):
            raise AssertionError(f"Mixed-provider link validation failed: {results!r}")
        page.import_card.activated.emit()
        overlay = page.findChild(ModelLinkImportOverlay)
        if overlay is None:
            raise AssertionError("The installer did not open its link overlay.")
        overlay.link_edit.setPlainText("\n".join(links))
        overlay.set_results(results)
        _settle(application)
        links_path = artifact_root / "openmodeldb-installer-mixed-links.png"
        save_opaque_dark_widget_capture(page, links_path)
        evidence: dict[str, object] = {
            "result": "passed",
            "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
            "production_surface": f"{type(page).__module__}.{type(page).__name__}",
            "picker_screenshot": str(picker_path),
            "links_screenshot": str(links_path),
            "cards": len(page.visible_cards()),
            "selected_by_default": len(selected_ids),
            "models": [
                {
                    "name": item.model_name,
                    "sha256": item.sha256,
                    "provider": item.provider_name,
                    "thumbnail_rendered": card.thumbnail is not None,
                }
                for item, card in zip(recommendations, cards, strict=True)
            ],
            "imported_links": [
                {
                    "source_url": result.source_url,
                    "provider": result.card.recommendation.provider_name
                    if result.card is not None
                    else None,
                    "model": result.card.recommendation.model_name
                    if result.card is not None
                    else None,
                    "status": result.status.value,
                }
                for result in results
            ],
        }
        (artifact_root / "installer-evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        page.close()
        page.deleteLater()
        application.processEvents()
        return evidence
    finally:
        runtime.close()


def _register_font(application: QApplication) -> None:
    """Use the installed Windows Fluent font in offscreen capture."""

    windows_root = os.environ.get("WINDIR")
    if windows_root is None:
        raise RuntimeError("WINDIR is required for the Windows installer render.")
    font_id = QFontDatabase.addApplicationFont(
        str(Path(windows_root) / "Fonts" / "segoeui.ttf")
    )
    families = QFontDatabase.applicationFontFamilies(font_id)
    if font_id < 0 or not families:
        raise RuntimeError("Could not load the installer render font.")
    application.setFont(QFont(families[0], 10))


def _settle(application: QApplication) -> None:
    """Complete queued layout and Fluent animations before capture."""

    application.processEvents()
    QTest.qWait(180)
    application.processEvents()


def main() -> int:
    """Render both installer states and report the evidence path."""

    run_headless_installer_qualification()
    print(_ARTIFACT_ROOT / "installer-evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["run_headless_installer_qualification"]
