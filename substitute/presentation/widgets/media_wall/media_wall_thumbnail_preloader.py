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

"""Preload reusable media wall thumbnails away from foreground paint paths."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import count

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage

from substitute.application.execution import (
    ExecutionContext,
    ExecutionLaneSaturatedError,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.shared.logging.logger import get_logger, log_warning_exception
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload

from .media_wall_item import ThumbnailVariantReference
from .media_wall_thumbnail_cache import MediaWallPixmapCacheKey, MediaWallThumbnailCache
from .thumbnail_readiness import (
    MediaThumbnailReadiness,
    MediaThumbnailReadinessStatus,
    unavailable_thumbnail_readiness,
)

_LOGGER = get_logger("presentation.widgets.media_wall.thumbnail_preloader")
_MAX_PENDING_REQUESTS = 32
_MAX_IN_FLIGHT_REQUESTS = 2
_SATURATION_RETRY_INTERVAL_MS = 25


@dataclass(frozen=True, slots=True)
class MediaWallThumbnailPreloadResult:
    """Carry one decoded media-wall thumbnail to GUI publication."""

    cache_key: MediaWallPixmapCacheKey
    storage_key: str
    image: QImage | None
    device_pixel_ratio: float
    generation: int
    error: BaseException | None = None


@dataclass(frozen=True, slots=True)
class _QueuedThumbnailPreload:
    """Retain one request until thumbnail execution capacity is available."""

    request: TaskRequest[MediaWallThumbnailPreloadResult]
    cache_key: MediaWallPixmapCacheKey
    storage_key: str
    device_pixel_ratio: float
    generation: int


class MediaWallThumbnailPreloader(QObject):
    """Own media-wall thumbnail reads, decodes, scaling, and cache publication."""

    thumbnailReady = Signal(str)

    _publishRequested = Signal(object)

    def __init__(
        self,
        *,
        cache: MediaWallThumbnailCache,
        asset_repository: ThumbnailAssetRepository | None,
        submitter: TaskSubmitter | None = None,
        close_submitter: Callable[[], None] | None = None,
        parent: QObject | None = None,
        maximum_pending_requests: int = _MAX_PENDING_REQUESTS,
        maximum_in_flight_requests: int = _MAX_IN_FLIGHT_REQUESTS,
    ) -> None:
        """Bind a cache to bounded thumbnail preload requests."""

        super().__init__(parent)
        if maximum_pending_requests <= 0:
            raise ValueError("maximum_pending_requests must be positive.")
        if maximum_in_flight_requests <= 0:
            raise ValueError("maximum_in_flight_requests must be positive.")
        if maximum_in_flight_requests > maximum_pending_requests:
            raise ValueError(
                "maximum_in_flight_requests must not exceed maximum_pending_requests."
            )
        self._cache = cache
        self._asset_repository = asset_repository
        self._maximum_pending_requests = maximum_pending_requests
        self._maximum_in_flight_requests = maximum_in_flight_requests
        self._pending_cache_keys: set[MediaWallPixmapCacheKey] = set()
        self._in_flight_cache_keys: set[MediaWallPixmapCacheKey] = set()
        self._queued_preloads: dict[
            MediaWallPixmapCacheKey, _QueuedThumbnailPreload
        ] = {}
        self._failed_storage_keys: set[str] = set()
        self._request_ids = count(1)
        self._close_submitter = close_submitter
        self._is_shutdown = False
        self._task_scope = (
            TaskScope(
                submitter=submitter,
                scope_id=f"media_wall_thumbnail_preloader_{id(self):x}",
            )
            if submitter is not None
            else None
        )
        self._publishRequested.connect(self._publish_preload_result)
        self._submission_retry_timer = QTimer(self)
        self._submission_retry_timer.setSingleShot(True)
        self._submission_retry_timer.setInterval(_SATURATION_RETRY_INTERVAL_MS)
        self._submission_retry_timer.timeout.connect(self._drain_queued_preloads)

    def preload_pixmap_for_variants(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Queue a thumbnail preload when storage is available and needed."""

        asset_repository = self._asset_repository
        if self._is_shutdown or asset_repository is None:
            return False
        cache_key = self._cache.cache_key_for_variants(
            variants,
            size,
            device_pixel_ratio=device_pixel_ratio,
        )
        variant = self._cache.variant_for_cache_request(variants, size)
        if cache_key is None or variant is None:
            return False
        if variant.storage_key in self._failed_storage_keys:
            return False
        if self._cache.has_pixmap(cache_key) or cache_key in self._pending_cache_keys:
            return False
        if len(self._pending_cache_keys) >= self._maximum_pending_requests:
            return False
        task_scope = self._task_scope
        if task_scope is None:
            return False
        self._pending_cache_keys.add(cache_key)
        target_size = QSize(
            max(1, round(size.width() * device_pixel_ratio)),
            max(1, round(size.height() * device_pixel_ratio)),
        )
        generation = self._cache.generation
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._request_ids),
                domain="media_wall_thumbnail_preload",
                parts=(
                    ("cache_key", cache_key),
                    ("storage_key", variant.storage_key),
                ),
            ),
            context=ExecutionContext(
                operation="media_wall_thumbnail_preload",
                reason="visible_media_wall_tile",
                lane="thumbnail_decode",
                safe_fields=(
                    ("cache_key", str(hash(cache_key))),
                    ("generation", generation),
                ),
            ),
            work=lambda _token: _load_thumbnail_image(
                asset_repository=asset_repository,
                variant=variant,
                target_size=target_size,
                cache_key=cache_key,
                generation=generation,
                device_pixel_ratio=device_pixel_ratio,
            ),
        )
        self._queued_preloads[cache_key] = _QueuedThumbnailPreload(
            request=request,
            cache_key=cache_key,
            storage_key=variant.storage_key,
            device_pixel_ratio=device_pixel_ratio,
            generation=generation,
        )
        self._drain_queued_preloads()
        return True

    def install_pixmap_for_variants_now(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Synchronously decode and install one local cached thumbnail pixmap."""

        asset_repository = self._asset_repository
        if asset_repository is None:
            return False
        cache_key = self._cache.cache_key_for_variants(
            variants,
            size,
            device_pixel_ratio=device_pixel_ratio,
        )
        variant = self._cache.variant_for_cache_request(variants, size)
        if cache_key is None or variant is None:
            return False
        if self._cache.has_pixmap(cache_key):
            return True
        if variant.storage_key in self._failed_storage_keys:
            return False
        target_size = QSize(
            max(1, round(size.width() * device_pixel_ratio)),
            max(1, round(size.height() * device_pixel_ratio)),
        )
        generation = self._cache.generation
        result = _load_thumbnail_image(
            asset_repository=asset_repository,
            variant=variant,
            target_size=target_size,
            cache_key=cache_key,
            generation=generation,
            device_pixel_ratio=device_pixel_ratio,
        )
        if result.image is None:
            self._failed_storage_keys.add(result.storage_key)
            return False
        installed = self._cache.install_ready_image(
            cache_key=result.cache_key,
            image=result.image,
            device_pixel_ratio=result.device_pixel_ratio,
            generation=result.generation,
        )
        if not installed:
            self._failed_storage_keys.add(result.storage_key)
            return False
        self.thumbnailReady.emit(result.storage_key)
        return True

    def preload_pixmap_for_role(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        role: str,
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Queue a thumbnail preload for the best variant matching one role."""

        return self.preload_pixmap_for_variants(
            self._cache.role_variants(variants, role),
            size,
            device_pixel_ratio=device_pixel_ratio,
        )

    def install_pixmap_for_role_now(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        role: str,
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Synchronously install the best local cached thumbnail for one role."""

        return self.install_pixmap_for_variants_now(
            self._cache.role_variants(variants, role),
            size,
            device_pixel_ratio=device_pixel_ratio,
        )

    def readiness_for_variants(
        self,
        variants: tuple[ThumbnailVariantReference, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> MediaThumbnailReadiness:
        """Return foreground-safe thumbnail readiness for one cache request."""

        if self._asset_repository is None:
            return unavailable_thumbnail_readiness("thumbnail_repository_unavailable")
        cache_key = self._cache.cache_key_for_variants(
            variants,
            size,
            device_pixel_ratio=device_pixel_ratio,
        )
        variant = self._cache.variant_for_cache_request(variants, size)
        if cache_key is None or variant is None:
            return unavailable_thumbnail_readiness("thumbnail_variant_unavailable")
        if self._cache.has_pixmap(cache_key):
            return MediaThumbnailReadiness(
                status=MediaThumbnailReadinessStatus.READY,
                storage_key=variant.storage_key,
                cache_generation=self._cache.generation,
            )
        if variant.storage_key in self._failed_storage_keys:
            return MediaThumbnailReadiness(
                status=MediaThumbnailReadinessStatus.FAILED,
                storage_key=variant.storage_key,
                cache_generation=self._cache.generation,
                unavailable_reason="thumbnail_load_failed",
            )
        return MediaThumbnailReadiness(
            status=MediaThumbnailReadinessStatus.PENDING,
            storage_key=variant.storage_key,
            cache_generation=self._cache.generation,
        )

    def has_pending_work(self) -> bool:
        """Return whether thumbnail work is queued or publishing."""

        task_scope = self._task_scope
        return bool(self._pending_cache_keys) or (
            task_scope is not None and task_scope.has_pending_work()
        )

    def clear(self) -> None:
        """Forget pending and failed preload state after cache reset."""

        self._submission_retry_timer.stop()
        task_scope = self._task_scope
        if task_scope is not None:
            task_scope.cancel_all(reason="media_wall_thumbnail_preloader_clear")
        self._pending_cache_keys.clear()
        self._in_flight_cache_keys.clear()
        self._queued_preloads.clear()
        self._failed_storage_keys.clear()

    def shutdown(self) -> None:
        """Stop accepting preload tasks when an owning test or widget is done."""

        if self._is_shutdown:
            return
        self._is_shutdown = True
        self._submission_retry_timer.stop()
        self._pending_cache_keys.clear()
        self._in_flight_cache_keys.clear()
        self._queued_preloads.clear()
        task_scope = self._task_scope
        if task_scope is not None:
            task_scope.close(reason="media_wall_thumbnail_preloader_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _publish_preload_result(self, result: object) -> None:
        """Install one completed thumbnail preload on the GUI thread."""

        if not isinstance(result, MediaWallThumbnailPreloadResult):
            return
        self._pending_cache_keys.discard(result.cache_key)
        self._in_flight_cache_keys.discard(result.cache_key)
        if self._is_shutdown:
            return
        if result.error is not None or result.image is None:
            self._failed_storage_keys.add(result.storage_key)
            if result.error is not None:
                log_warning_exception(
                    _LOGGER,
                    "Media wall thumbnail asset load failed",
                    error=result.error,
                    storage_key=result.storage_key,
                )
            else:
                _LOGGER.warning(
                    "Media wall thumbnail asset load failed | storage_key=%s",
                    result.storage_key,
                )
            self._drain_queued_preloads()
            return
        installed = self._cache.install_ready_image(
            cache_key=result.cache_key,
            image=result.image,
            device_pixel_ratio=result.device_pixel_ratio,
            generation=result.generation,
        )
        if not installed:
            self._failed_storage_keys.add(result.storage_key)
            self._drain_queued_preloads()
            return
        self.thumbnailReady.emit(result.storage_key)
        self._drain_queued_preloads()

    def _drain_queued_preloads(self) -> None:
        """Submit retained thumbnail work while this owner has execution headroom."""

        if self._is_shutdown:
            return
        task_scope = self._task_scope
        if task_scope is None:
            return
        while (
            self._queued_preloads
            and len(self._in_flight_cache_keys) < self._maximum_in_flight_requests
        ):
            cache_key = next(iter(self._queued_preloads))
            queued = self._queued_preloads.pop(cache_key)
            try:
                handle = task_scope.submit(queued.request)
            except ExecutionLaneSaturatedError:
                self._queued_preloads[cache_key] = queued
                self._schedule_submission_retry()
                return
            except Exception as error:
                self._pending_cache_keys.discard(cache_key)
                log_warning_exception(
                    _LOGGER,
                    "Media wall thumbnail preload submission failed",
                    error=error,
                    storage_key=queued.storage_key,
                )
                continue
            self._in_flight_cache_keys.add(cache_key)

            def publish_outcome(
                outcome: TaskOutcome[MediaWallThumbnailPreloadResult],
                preload: _QueuedThumbnailPreload = queued,
            ) -> None:
                """Forward one settled request through the GUI publication signal."""

                self._publishRequested.emit(
                    _result_from_outcome(
                        outcome,
                        cache_key=preload.cache_key,
                        storage_key=preload.storage_key,
                        device_pixel_ratio=preload.device_pixel_ratio,
                        generation=preload.generation,
                    )
                )

            handle.add_done_callback(
                publish_outcome,
                reason="media_wall_thumbnail_preload_complete",
            )

    def _schedule_submission_retry(self) -> None:
        """Coalesce one retry after shared thumbnail execution capacity returns."""

        if not self._submission_retry_timer.isActive():
            self._submission_retry_timer.start()


def _load_thumbnail_image(
    *,
    asset_repository: ThumbnailAssetRepository,
    variant: ThumbnailVariantReference,
    target_size: QSize,
    cache_key: MediaWallPixmapCacheKey,
    generation: int,
    device_pixel_ratio: float,
) -> MediaWallThumbnailPreloadResult:
    """Read, decode, and scale one thumbnail asset away from the GUI thread."""

    asset = asset_repository.read_thumbnail_asset(variant.storage_key)
    if asset is None:
        return MediaWallThumbnailPreloadResult(
            cache_key=cache_key,
            storage_key=variant.storage_key,
            image=None,
            device_pixel_ratio=device_pixel_ratio,
            generation=generation,
        )
    image = image_from_qt_thumbnail_payload(
        width=asset.width,
        height=asset.height,
        qt_format=asset.qt_format,
        bytes_per_line=asset.bytes_per_line,
        payload=asset.payload,
    )
    if image is None:
        return MediaWallThumbnailPreloadResult(
            cache_key=cache_key,
            storage_key=variant.storage_key,
            image=None,
            device_pixel_ratio=device_pixel_ratio,
            generation=generation,
        )
    return MediaWallThumbnailPreloadResult(
        cache_key=cache_key,
        storage_key=variant.storage_key,
        image=_cover_scaled_image(image, target_size),
        device_pixel_ratio=device_pixel_ratio,
        generation=generation,
    )


def _cover_scaled_image(image: QImage, target_size: QSize) -> QImage:
    """Return an exact-size image produced with proportional cover scaling."""

    scaled = image.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    left = max(0, (scaled.width() - target_size.width()) // 2)
    top = max(0, (scaled.height() - target_size.height()) // 2)
    return scaled.copy(left, top, target_size.width(), target_size.height())


def _result_from_outcome(
    outcome: TaskOutcome[MediaWallThumbnailPreloadResult],
    *,
    cache_key: MediaWallPixmapCacheKey,
    storage_key: str,
    device_pixel_ratio: float,
    generation: int,
) -> MediaWallThumbnailPreloadResult:
    """Translate one execution outcome into the preloader publication DTO."""

    if outcome.status == "succeeded" and outcome.result is not None:
        return outcome.result
    if outcome.status == "failed":
        return MediaWallThumbnailPreloadResult(
            cache_key=cache_key,
            storage_key=storage_key,
            image=None,
            device_pixel_ratio=device_pixel_ratio,
            generation=generation,
            error=outcome.error,
        )
    return MediaWallThumbnailPreloadResult(
        cache_key=cache_key,
        storage_key=storage_key,
        image=None,
        device_pixel_ratio=device_pixel_ratio,
        generation=generation,
    )


__all__ = [
    "MediaWallThumbnailPreloadResult",
    "MediaWallThumbnailPreloader",
]
