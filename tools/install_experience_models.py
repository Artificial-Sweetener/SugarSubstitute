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

"""Provide deterministic model-onboarding adapters for installer qualification."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QImage

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
    RecommendationLinkResult,
    RecommendationLinkStatus,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    DetectedModelFamily,
    ModelFamilyEvidenceKind,
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelFamilyScanStatus,
    ModelRecommendation,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail


class SyntheticModelOnboardingCoordinator(QObject):
    """Return recorded-equivalent scans and three-card family pages synchronously."""

    scan_finished = Signal(int, object)
    recommendation_finished = Signal(int, object)
    thumbnail_finished = Signal(int, int, object)
    thumbnail_failed = Signal(int, int)
    link_import_finished = Signal(int, object)
    task_failed = Signal(int, str, object)

    def __init__(
        self,
        *,
        detected_families: tuple[ModelFamilyId, ...] = (),
        recommendation_failure: bool = False,
        thumbnail_failure: bool = False,
        scan_failure: bool = False,
        scan_unknown_count: int = 0,
        parent: QObject | None = None,
    ) -> None:
        """Store deterministic outcomes without filesystem or network access."""

        super().__init__(parent)
        self._detected_families = detected_families
        self._recommendation_failures_remaining = int(recommendation_failure)
        self._thumbnail_failures_remaining = int(thumbnail_failure)
        self._scan_failure = scan_failure
        self._scan_unknown_count = scan_unknown_count
        self._generation = 0

    def start_scan(self, root: Path) -> int:
        """Publish a complete read-only synthetic family scan."""

        self._generation += 1
        generation = self._generation
        if self._scan_failure:
            self.task_failed.emit(
                generation,
                "scan",
                OSError("Synthetic model folder scan failure."),
            )
            return generation
        detected = tuple(
            DetectedModelFamily(
                family_id=family_id,
                path=root / f"synthetic-{family_id.value}.safetensors",
                evidence_kind=ModelFamilyEvidenceKind.SAFETENSOR_METADATA,
            )
            for family_id in self._detected_families
        )
        self.scan_finished.emit(
            generation,
            ModelFamilyScanResult(
                root=root,
                status=ModelFamilyScanStatus.COMPLETED,
                detected=detected,
                inspected_count=len(detected),
                unreadable_count=0,
                unknown_count=self._scan_unknown_count,
            ),
        )
        return generation

    def start_recommendations(self, families: tuple[ModelFamilyId, ...]) -> int:
        """Publish eight safe exact-family cards or one configured provider failure."""

        self._generation += 1
        generation = self._generation
        if self._recommendation_failures_remaining:
            self._recommendation_failures_remaining -= 1
            self.task_failed.emit(
                generation,
                "recommendations",
                RuntimeError("Synthetic CivitAI unavailability."),
            )
            return generation
        thumbnail_failure = self._thumbnail_failures_remaining > 0
        self._thumbnail_failures_remaining = max(
            0, self._thumbnail_failures_remaining - 1
        )
        pages = tuple(
            FamilyRecommendationPage(family_id, _family_cards(family_id))
            for family_id in families
        )
        self.recommendation_finished.emit(generation, pages)
        for page in pages:
            for card in page.cards:
                version_id = card.recommendation.version_id
                if thumbnail_failure:
                    self.thumbnail_failed.emit(generation, version_id)
                else:
                    self.thumbnail_finished.emit(
                        generation,
                        version_id,
                        _thumbnail_asset(
                            page.family_id,
                            card.recommendation.popularity_rank,
                        ),
                    )
        return generation

    def start_link_import(
        self,
        family_id: ModelFamilyId,
        urls: tuple[str, ...],
        *,
        excluded_version_ids: frozenset[int] = frozenset(),
    ) -> int:
        """Publish deterministic validated link previews for qualification."""

        _ = excluded_version_ids
        self._generation += 1
        generation = self._generation
        card = _linked_card(family_id)
        results = tuple(
            RecommendationLinkResult(
                source_url=url,
                status=RecommendationLinkStatus.READY,
                card=card,
            )
            for url in urls
        )
        self.link_import_finished.emit(generation, results)
        return generation

    def cancel(self) -> None:
        """Invalidate no work because synthetic results are synchronous."""

    def shutdown(self) -> None:
        """Release no resources because this adapter owns none."""


def _family_cards(family_id: ModelFamilyId) -> tuple[RecommendationCardAsset, ...]:
    """Return eight deterministic portrait cards in provider order."""

    family_offset = 100 if family_id is ModelFamilyId.SDXL else 200
    return tuple(
        RecommendationCardAsset(
            recommendation=ModelRecommendation(
                family_id=family_id,
                model_id=family_offset + rank,
                version_id=family_offset * 10 + rank,
                model_name=f"{family_id.value.upper()} Popular {rank}",
                version_name=f"v{rank}",
                creator=f"creator-{rank}",
                file_name=f"{family_id.value}-{rank}.safetensors",
                size_bytes=(2 * 1024**3) + rank,
                sha256=f"{family_offset + rank:064x}",
                download_url=(
                    f"https://civitai.com/api/download/models/{family_offset * 10 + rank}"
                ),
                model_page_url=(
                    f"https://civitai.com/models/{family_offset + rank}"
                    f"?modelVersionId={family_offset * 10 + rank}"
                ),
                thumbnail_image_id=family_offset * 100 + rank,
                thumbnail_url=f"https://image.civitai.com/synthetic/{family_offset + rank}.png",
                popularity_rank=rank,
            ),
        )
        for rank in range(1, 9)
    )


def _linked_card(family_id: ModelFamilyId) -> RecommendationCardAsset:
    """Return one distinct resolved link with a completed preview thumbnail."""

    family_offset = 100 if family_id is ModelFamilyId.SDXL else 200
    model_id = family_offset + 99
    version_id = family_offset * 10 + 99
    return RecommendationCardAsset(
        recommendation=ModelRecommendation(
            family_id=family_id,
            model_id=model_id,
            version_id=version_id,
            model_name=f"Imported {family_id.value.upper()} model",
            version_name="linked version",
            creator="community-creator",
            file_name=f"imported-{family_id.value}.safetensors",
            size_bytes=3 * 1024**3,
            sha256=f"{model_id:064x}",
            download_url=f"https://civitai.com/api/download/models/{version_id}",
            model_page_url=(
                f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
            ),
            thumbnail_image_id=model_id * 100,
            thumbnail_url=f"https://image.civitai.com/synthetic/{model_id}.png",
            popularity_rank=0,
        ),
        thumbnail=_thumbnail_asset(family_id, 1),
    )


def _thumbnail_asset(family_id: ModelFamilyId, rank: int) -> ThumbnailAsset:
    """Return one distinct Qt-ready thumbnail without reading an external asset."""

    image = QImage(800, 1200, QImage.Format.Format_ARGB32_Premultiplied)
    colors = (
        QColor("#6C5CE7"),
        QColor("#0984E3"),
        QColor("#00B894"),
        QColor("#E17055"),
        QColor("#D63031"),
    )
    image.fill(colors[(rank - 1) % len(colors)])
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=f"synthetic:{family_id.value}:{rank}",
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )


__all__ = ["SyntheticModelOnboardingCoordinator"]
