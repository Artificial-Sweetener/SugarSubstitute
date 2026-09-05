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

"""Adapt model scans and recommendations to generation-safe Qt signals."""

from __future__ import annotations

from collections.abc import Callable
from itertools import count
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    LatestWinsRequestChannel,
    TaskScope,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskSubmitter,
)
from substitute.application.model_recommendations import FamilyRecommendationPage
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelRecommendation,
)
from substitute.shared.logging.logger import get_logger, log_warning_exception

_LOGGER = get_logger("presentation.onboarding.model_onboarding_coordinator")


class ModelOnboardingServiceLike(Protocol):
    """Describe application model-onboarding work used by presentation."""

    def scan(
        self,
        root: Path,
        *,
        cancellation: CancellationToken,
    ) -> ModelFamilyScanResult:
        """Scan one selected local model root."""

    def recommend(
        self,
        families: tuple[ModelFamilyId, ...],
        *,
        cancellation: CancellationToken,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[FamilyRecommendationPage, ...]:
        """Return provider metadata without blocking on thumbnail downloads."""

    def fetch_thumbnail(
        self,
        recommendation: ModelRecommendation,
        *,
        cancellation: CancellationToken,
    ) -> ThumbnailAsset:
        """Load one governed recommendation thumbnail."""


class ModelOnboardingCoordinator(QObject):
    """Own cancellable model-onboarding work for one onboarding window."""

    scan_started = Signal(int)
    scan_finished = Signal(int, object)
    recommendation_started = Signal(int)
    recommendation_finished = Signal(int, object)
    thumbnail_finished = Signal(int, int, object)
    thumbnail_failed = Signal(int, int)
    task_failed = Signal(int, str, object)

    def __init__(
        self,
        *,
        service: ModelOnboardingServiceLike,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        """Store work services and latest-wins execution channels."""

        super().__init__(parent)
        self._service = service
        self._close_submitter = close_submitter
        self._scan_channel: LatestWinsRequestChannel[ModelFamilyScanResult] = (
            LatestWinsRequestChannel(submitter=submitter)
        )
        self._recommendation_channel: LatestWinsRequestChannel[
            tuple[FamilyRecommendationPage, ...]
        ] = LatestWinsRequestChannel(submitter=submitter)
        self._thumbnail_scope = TaskScope(
            submitter=submitter,
            scope_id=f"onboarding_model_thumbnails_{id(self):x}",
        )
        self._thumbnail_request_ids = count(1)
        self._scan_generation = 0
        self._recommendation_generation = 0
        self._closed = False
        self.destroyed.connect(self.shutdown)

    def start_scan(self, root: Path) -> int:
        """Start a latest-wins scan and return its generation."""

        self._scan_generation += 1
        generation = self._scan_generation
        self.scan_started.emit(generation)
        request = TaskRequest(
            identity=TaskIdentity(
                generation, "onboarding_model_scan", (("root", str(root)),)
            ),
            context=ExecutionContext(
                operation="onboarding_model_scan",
                reason="existing_folder_selected",
                lane="onboarding_models",
                owner_id="onboarding_model_coordinator",
                safe_fields=(("generation", generation),),
            ),
            work=lambda cancellation: self._service.scan(
                root,
                cancellation=cancellation,
            ),
        )
        handle = self._scan_channel.submit_latest(request)
        handle.add_done_callback(
            lambda outcome: self._deliver_scan(generation, outcome),
            reason="onboarding_model_scan_complete",
        )
        return generation

    def start_recommendations(
        self,
        families: tuple[ModelFamilyId, ...],
        *,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> int:
        """Start latest-wins catalog-ordered recommendation loading."""

        self._thumbnail_scope.cancel_all(
            reason="onboarding_recommendation_generation_changed"
        )
        self._recommendation_generation += 1
        generation = self._recommendation_generation
        self.recommendation_started.emit(generation)
        request = TaskRequest(
            identity=TaskIdentity(
                generation,
                "onboarding_model_recommendations",
                (("families", ",".join(family.value for family in families)),),
            ),
            context=ExecutionContext(
                operation="onboarding_model_recommendations",
                reason="families_selected",
                lane="onboarding_models",
                owner_id="onboarding_model_coordinator",
                safe_fields=(("generation", generation),),
            ),
            work=lambda cancellation: self._service.recommend(
                families,
                cancellation=cancellation,
                excluded_sha256=excluded_sha256,
            ),
        )
        handle = self._recommendation_channel.submit_latest(request)
        handle.add_done_callback(
            lambda outcome: self._deliver_recommendations(generation, outcome),
            reason="onboarding_model_recommendations_complete",
        )
        return generation

    def cancel(self) -> None:
        """Cancel active model work while keeping the coordinator reusable."""

        self._scan_channel.cancel_pending(reason="onboarding_model_choices_changed")
        self._recommendation_channel.cancel_pending(
            reason="onboarding_model_choices_changed"
        )
        self._thumbnail_scope.cancel_all(reason="onboarding_model_choices_changed")

    def shutdown(self) -> None:
        """Cancel work and release the owner-scoped runtime submitter."""

        if self._closed:
            return
        self._closed = True
        self.cancel()
        self._thumbnail_scope.close(reason="onboarding_model_coordinator_shutdown")
        self._close_submitter()

    def _deliver_scan(
        self,
        generation: int,
        outcome: TaskOutcome[ModelFamilyScanResult],
    ) -> None:
        """Publish only the latest non-cancelled scan outcome."""

        if self._closed or generation != self._scan_generation or outcome.cancelled:
            return
        if outcome.error is not None:
            self.task_failed.emit(generation, "scan", outcome.error)
        elif outcome.result is not None:
            self.scan_finished.emit(generation, outcome.result)

    def _deliver_recommendations(
        self,
        generation: int,
        outcome: TaskOutcome[tuple[FamilyRecommendationPage, ...]],
    ) -> None:
        """Publish only the latest non-cancelled recommendation outcome."""

        if (
            self._closed
            or generation != self._recommendation_generation
            or outcome.cancelled
        ):
            return
        if outcome.error is not None:
            self.task_failed.emit(generation, "recommendations", outcome.error)
        elif outcome.result is not None:
            self.recommendation_finished.emit(generation, outcome.result)
            self._start_thumbnail_loads(generation, outcome.result)

    def _start_thumbnail_loads(
        self,
        generation: int,
        pages: tuple[FamilyRecommendationPage, ...],
    ) -> None:
        """Start independent image requests after metadata has been published."""

        for page in pages:
            for card in page.cards:
                recommendation = card.recommendation
                request = TaskRequest(
                    identity=TaskIdentity(
                        next(self._thumbnail_request_ids),
                        "onboarding_model_thumbnail",
                        (
                            ("generation", generation),
                            ("version_id", recommendation.version_id),
                        ),
                    ),
                    context=ExecutionContext(
                        operation="onboarding_model_thumbnail",
                        reason="recommendation_card_visible",
                        lane="onboarding_models",
                        owner_id="onboarding_model_coordinator",
                        safe_fields=(
                            ("generation", generation),
                            ("target_id", recommendation.version_id),
                        ),
                    ),
                    work=self._thumbnail_work(recommendation),
                )
                try:
                    handle = self._thumbnail_scope.submit(request)
                except Exception as error:
                    log_warning_exception(
                        _LOGGER,
                        "Recommendation thumbnail submission failed",
                        error=error,
                        model_id=recommendation.model_id,
                        version_id=recommendation.version_id,
                        generation=generation,
                    )
                    self.thumbnail_failed.emit(generation, recommendation.version_id)
                    continue
                handle.add_done_callback(
                    self._thumbnail_delivery(generation, recommendation.version_id),
                    reason="onboarding_model_thumbnail_complete",
                )

    def _thumbnail_work(
        self,
        recommendation: ModelRecommendation,
    ) -> Callable[[CancellationToken], ThumbnailAsset]:
        """Bind one recommendation to its cancellable image request."""

        def work(cancellation: CancellationToken) -> ThumbnailAsset:
            """Load the bound recommendation thumbnail."""

            return self._service.fetch_thumbnail(
                recommendation,
                cancellation=cancellation,
            )

        return work

    def _thumbnail_delivery(
        self,
        generation: int,
        version_id: int,
    ) -> Callable[[TaskOutcome[ThumbnailAsset]], None]:
        """Bind thumbnail identity to its GUI-thread completion callback."""

        def deliver(outcome: TaskOutcome[ThumbnailAsset]) -> None:
            """Publish the bound thumbnail outcome."""

            self._deliver_thumbnail(generation, version_id, outcome)

        return deliver

    def _deliver_thumbnail(
        self,
        generation: int,
        version_id: int,
        outcome: TaskOutcome[ThumbnailAsset],
    ) -> None:
        """Publish one current thumbnail without affecting other cards."""

        if (
            self._closed
            or generation != self._recommendation_generation
            or outcome.cancelled
        ):
            return
        if outcome.error is not None or outcome.result is None:
            if outcome.error is not None:
                log_warning_exception(
                    _LOGGER,
                    "Recommendation thumbnail load failed",
                    error=outcome.error,
                    version_id=version_id,
                    generation=generation,
                )
            self.thumbnail_failed.emit(generation, version_id)
            return
        self.thumbnail_finished.emit(generation, version_id, outcome.result)


__all__ = ["ModelOnboardingCoordinator", "ModelOnboardingServiceLike"]
