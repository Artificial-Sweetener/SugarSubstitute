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

"""Preload LoRA thumbnail images and publish fresh pixmaps to the GUI cache."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.shared.logging.logger import (
    get_logger,
    log_warning_exception,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload

from ..lora_thumbnail_cache import (
    PromptLoraPixmapCacheKey,
    PromptLoraThumbnailCache,
)
from ..projection.model import PromptProjectionThumbnailVariant
from .cancellation import PromptEditorCancellationController
from .execution import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorTaskHandle,
)
from .main_thread_dispatcher import (
    PromptEditorMainThreadDispatcher,
    QtPromptEditorMainThreadDispatcher,
)
from .task_executor import PromptEditorTaskExecutor

_LOGGER = get_logger("presentation.editor.prompt_editor.async_work.thumbnail")
_MAX_PENDING_REQUESTS = 32


@dataclass(frozen=True, slots=True)
class PromptLoraThumbnailPreloadResult:
    """Carry one decoded thumbnail image to GUI publication."""

    cache_key: PromptLoraPixmapCacheKey
    storage_key: str
    image: QImage | None
    device_pixel_ratio: float
    generation: int


class PromptLoraThumbnailPreloader:
    """Own LoRA thumbnail task dispatch and stale-safe cache publication."""

    def __init__(
        self,
        *,
        cache: PromptLoraThumbnailCache,
        asset_repository: ThumbnailAssetRepository | None = None,
        parent: object | None = None,
        dispatcher: PromptEditorMainThreadDispatcher | None = None,
        executor: PromptEditorTaskExecutor | None = None,
        maximum_pending_requests: int = _MAX_PENDING_REQUESTS,
    ) -> None:
        """Bind a thumbnail cache to explicit async preload requests."""

        self._cache = cache
        self._asset_repository = asset_repository or cache.asset_repository
        self._dispatcher = dispatcher or QtPromptEditorMainThreadDispatcher(
            cast(Any, parent)
        )
        if self._asset_repository is not None and executor is None:
            raise RuntimeError("executor is required for LoRA thumbnail preloads.")
        self._executor = executor
        self._cancellation_controller = PromptEditorCancellationController()
        self._maximum_pending_requests = maximum_pending_requests
        self._pending_cache_keys: set[PromptLoraPixmapCacheKey] = set()
        self._failed_storage_keys: set[str] = set()
        self._idle_callbacks: list[Callable[[], None]] = []
        self._handles: dict[
            PromptLoraPixmapCacheKey,
            PromptEditorTaskHandle[PromptLoraThumbnailPreloadResult],
        ] = {}
        self._request_id = 0
        self._is_shutdown = False
        if parent is not None:
            destroyed = getattr(parent, "destroyed", None)
            connect = getattr(destroyed, "connect", None)
            if callable(connect):
                connect(self.shutdown)

    def preload_banner_pixmap_for_variants(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Queue one banner thumbnail preload request when not already cached."""

        return self.preload_pixmap_for_variants(
            self._cache.banner_variants(variants),
            size,
            device_pixel_ratio=device_pixel_ratio,
        )

    def install_banner_pixmap_for_variants_now(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Install one local cached banner thumbnail immediately when possible."""

        return self.install_pixmap_for_variants_now(
            self._cache.banner_variants(variants),
            size,
            device_pixel_ratio=device_pixel_ratio,
        )

    def install_pixmap_for_variants_now(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
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
        generation = self._cache.generation
        target_size = QSize(
            max(1, round(size.width() * device_pixel_ratio)),
            max(1, round(size.height() * device_pixel_ratio)),
        )
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
        return installed

    def preload_pixmap_for_variants(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Queue one thumbnail preload request when not already cached or pending."""

        if self._is_shutdown:
            return False
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
        if variant.storage_key in self._failed_storage_keys:
            return False
        if self._cache.has_pixmap(cache_key) or cache_key in self._pending_cache_keys:
            return False
        if len(self._pending_cache_keys) >= self._maximum_pending_requests:
            return False
        self._pending_cache_keys.add(cache_key)
        self._request_id += 1
        generation = self._cache.generation
        target_size = QSize(
            max(1, round(size.width() * device_pixel_ratio)),
            max(1, round(size.height() * device_pixel_ratio)),
        )
        request = PromptAsyncRequest(
            identity=PromptAsyncResultIdentity(
                request_id=self._request_id,
                query_identity=cache_key,
                cancellation_generation=generation,
            ),
            context=PromptAsyncRequestContext(
                operation="lora_thumbnail_preload",
                reason="visible_lora_banner",
                safe_fields=(
                    ("storage_key", variant.storage_key),
                    ("target_width", target_size.width()),
                    ("target_height", target_size.height()),
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
        source = self._cancellation_controller.next_source()
        try:
            executor = self._executor
            if executor is None:
                return False
            handle = executor.submit(request, cancellation=source)
        except Exception as error:
            self._pending_cache_keys.discard(cache_key)
            log_warning_exception(
                _LOGGER,
                "LoRA thumbnail preload submission failed",
                error=error,
                storage_key=variant.storage_key,
            )
            return False
        self._handles[cache_key] = handle
        handle.add_done_callback(
            self._handle_preload_outcome,
            reason="lora_thumbnail_preload_completed",
        )
        return True

    def has_pending_work(self) -> bool:
        """Return whether thumbnail work is still queued or publishing."""

        return bool(self._pending_cache_keys)

    def run_when_idle(self, callback: Callable[[], None]) -> None:
        """Run the callback after currently queued thumbnail work settles."""

        if not self.has_pending_work():
            self._dispatcher.publish(callback, reason="lora_thumbnail_idle")
            return
        self._idle_callbacks.append(callback)

    def clear(self) -> None:
        """Forget pending and failed thumbnail preload state after cache reset."""

        self._pending_cache_keys.clear()
        self._failed_storage_keys.clear()
        self._idle_callbacks.clear()

    def shutdown(self, *_args: object) -> None:
        """Cancel thumbnail preload work and release owned execution resources."""

        if self._is_shutdown:
            return
        self._is_shutdown = True
        self._pending_cache_keys.clear()
        self._idle_callbacks.clear()
        for handle in tuple(self._handles.values()):
            handle.cancel(reason="lora_thumbnail_preloader_shutdown")
        self._handles.clear()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _handle_preload_outcome(
        self,
        outcome: PromptAsyncTaskOutcome[PromptLoraThumbnailPreloadResult],
    ) -> None:
        """Publish a completed thumbnail preload outcome to the GUI cache."""

        if self._is_shutdown:
            return
        result = outcome.result
        cache_key = _cache_key_from_outcome(outcome)
        if cache_key is not None:
            self._pending_cache_keys.discard(cache_key)
            self._handles.pop(cache_key, None)
        if outcome.cancelled:
            self._run_idle_callbacks_if_ready()
            return
        if outcome.error is not None or result is None or result.image is None:
            storage_key = _storage_key_from_outcome(outcome, result)
            if storage_key:
                self._failed_storage_keys.add(storage_key)
            if outcome.error is not None:
                log_warning_exception(
                    _LOGGER,
                    "LoRA thumbnail asset load failed",
                    error=outcome.error,
                    storage_key=storage_key or "unknown",
                )
            else:
                _LOGGER.warning(
                    "LoRA thumbnail asset load failed | storage_key=%s",
                    storage_key or "unknown",
                )
            self._run_idle_callbacks_if_ready()
            return
        installed = self._cache.install_ready_image(
            cache_key=result.cache_key,
            image=result.image,
            device_pixel_ratio=result.device_pixel_ratio,
            generation=result.generation,
        )
        if not installed:
            self._failed_storage_keys.add(result.storage_key)
        self._run_idle_callbacks_if_ready()

    def _run_idle_callbacks_if_ready(self) -> None:
        """Deliver queued idle callbacks once all current requests have settled."""

        if self.has_pending_work() or not self._idle_callbacks:
            return
        callbacks = self._idle_callbacks
        self._idle_callbacks = []
        for callback in callbacks:
            self._dispatcher.publish(callback, reason="lora_thumbnail_idle")


def _load_thumbnail_image(
    *,
    asset_repository: ThumbnailAssetRepository,
    variant: PromptProjectionThumbnailVariant,
    target_size: QSize,
    cache_key: PromptLoraPixmapCacheKey,
    generation: int,
    device_pixel_ratio: float,
) -> PromptLoraThumbnailPreloadResult:
    """Read, decode, and scale one thumbnail asset away from the GUI thread."""

    asset = asset_repository.read_thumbnail_asset(variant.storage_key)
    if asset is None:
        return PromptLoraThumbnailPreloadResult(
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
        return PromptLoraThumbnailPreloadResult(
            cache_key=cache_key,
            storage_key=variant.storage_key,
            image=None,
            device_pixel_ratio=device_pixel_ratio,
            generation=generation,
        )
    scaled_image = _cover_scaled_image(image, target_size)
    return PromptLoraThumbnailPreloadResult(
        cache_key=cache_key,
        storage_key=variant.storage_key,
        image=scaled_image,
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


def _cache_key_from_outcome(
    outcome: PromptAsyncTaskOutcome[PromptLoraThumbnailPreloadResult],
) -> PromptLoraPixmapCacheKey | None:
    """Return the cache key carried by an outcome when available."""

    result = outcome.result
    if result is not None:
        return result.cache_key
    query_identity = outcome.identity.query_identity
    if isinstance(query_identity, tuple):
        return query_identity
    return None


def _storage_key_from_outcome(
    outcome: PromptAsyncTaskOutcome[PromptLoraThumbnailPreloadResult],
    result: PromptLoraThumbnailPreloadResult | None,
) -> str | None:
    """Return a prompt-safe storage key for preload failure logging."""

    if result is not None:
        return result.storage_key
    cache_key = _cache_key_from_outcome(outcome)
    if cache_key is None:
        return None
    return str(cache_key[0])


__all__ = [
    "PromptLoraThumbnailPreloadResult",
    "PromptLoraThumbnailPreloader",
]
