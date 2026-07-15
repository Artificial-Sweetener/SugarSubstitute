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

"""Tests for LoRA thumbnail preload readiness boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage

from substitute.application.execution import CancellationToken, TaskHandle, TaskRequest
from tests.execution_testing import (
    ImmediateTaskSubmitter,
    ManualTaskHandle,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptLoraThumbnailPreloadResult,
    PromptEditorTaskExecutor,
)
from substitute.presentation.editor.prompt_editor.async_work.thumbnail_preloader import (
    _load_thumbnail_image,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptLoraThumbnailPreloader,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraPixmapCacheKey,
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionThumbnailVariant,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail

TResult = TypeVar("TResult")


class _ThumbnailRepository:
    """Record thumbnail asset reads for preloader tests."""

    def __init__(self, asset: ThumbnailAsset | None = None) -> None:
        """Store the asset returned for every storage key."""

        self.asset = asset
        self.reads: list[str] = []

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return the configured asset and record the storage key."""

        self.reads.append(storage_key)
        return self.asset


def test_thumbnail_preloader_without_repository_reports_no_pending_work() -> None:
    """Foreground thumbnail consumers should get a cheap no-repository state."""

    preloader = PromptLoraThumbnailPreloader(
        cache=PromptLoraThumbnailCache(),
    )

    queued = preloader.preload_pixmap_for_variants(
        (_variant("missing:standard:128"),),
        QSize(96, 96),
    )

    assert queued is False
    assert preloader.has_pending_work() is False


def test_thumbnail_preloader_shutdown_closes_runtime_submitter() -> None:
    """Shutdown should release the prompt thumbnail owner execution route."""

    closed_count = 0

    def record_close() -> None:
        """Record one executor close."""

        nonlocal closed_count
        closed_count += 1

    preloader = PromptLoraThumbnailPreloader(
        cache=PromptLoraThumbnailCache(),
        asset_repository=_ThumbnailRepository(),
        executor=PromptEditorTaskExecutor(
            submitter=ImmediateTaskSubmitter(),
            shutdown_callback=record_close,
        ),
    )

    preloader.shutdown()
    preloader.shutdown()

    assert closed_count == 1


def test_thumbnail_preloader_shutdown_suppresses_late_publication() -> None:
    """Shutdown should cancel pending work without publishing late pixmaps."""

    asset = _thumbnail_asset()
    repository = _ThumbnailRepository(asset)
    runtime = _ManualExecutionRuntime()
    cache = PromptLoraThumbnailCache(repository)
    preloader = PromptLoraThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        executor=PromptEditorTaskExecutor(
            submitter=runtime.submitter_instance,
            shutdown_callback=runtime.submitter_instance.close,
        ),
    )
    variants = (_variant("late:standard:128"),)

    assert preloader.preload_pixmap_for_variants(variants, QSize(96, 96)) is True
    assert preloader.has_pending_work() is True

    preloader.shutdown()

    assert runtime.closed_count == 1
    assert preloader.has_pending_work() is False
    assert repository.reads == []
    assert runtime.submitter_instance.handle is not None
    assert runtime.submitter_instance.handle.outcome is not None
    assert runtime.submitter_instance.handle.outcome.cancelled is True


def test_thumbnail_task_reports_missing_asset_without_ready_image() -> None:
    """Missing thumbnail storage should produce a failed readiness result."""

    repository = _ThumbnailRepository()
    cache_key: PromptLoraPixmapCacheKey = ("missing:standard:128", 96, 96, 1, 1.0)

    result = _load_thumbnail_image(
        asset_repository=repository,
        variant=_variant("missing:standard:128"),
        target_size=QSize(96, 96),
        cache_key=cache_key,
        generation=3,
        device_pixel_ratio=1.0,
    )

    assert repository.reads == ["missing:standard:128"]
    assert result.cache_key == cache_key
    assert result.storage_key == "missing:standard:128"
    assert result.image is None
    assert result.generation == 3


def _variant(storage_key: str) -> PromptProjectionThumbnailVariant:
    """Return one thumbnail variant reference."""

    return PromptProjectionThumbnailVariant(
        size=128,
        storage_key=storage_key,
        width=128,
        height=128,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=1,
    )


def _thumbnail_asset() -> ThumbnailAsset:
    """Return one valid thumbnail asset payload."""

    image = QImage(128, 128, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#51a8ff"))
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key="late:standard:128",
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        payload=prepared.payload,
        content_format=prepared.content_format,
    )


class _ManualExecutionRuntime:
    """Expose a manually completed runtime submitter for thumbnail tests."""

    def __init__(self) -> None:
        """Create the manual runtime state."""

        self.closed_count = 0
        self.submitter_instance = _ManualRuntimeSubmitter(
            close=self._record_close,
        )

    def submitter(
        self,
        _lane_name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> "_ManualRuntimeSubmitter":
        """Return the single manual submitter."""

        _ = owner_id, dispatcher
        return self.submitter_instance

    def _record_close(self) -> None:
        """Record one close request."""

        self.closed_count += 1


class _ManualRuntimeSubmitter:
    """Capture one task request without executing it."""

    def __init__(self, *, close: Callable[[], None]) -> None:
        """Store close accounting."""

        self._close = close
        self.handle: ManualTaskHandle[PromptLoraThumbnailPreloadResult] | None = None
        self._closed = False

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Return a manual task handle."""

        _ = cancellation
        thumbnail_request = cast(TaskRequest[PromptLoraThumbnailPreloadResult], request)
        self.handle = ManualTaskHandle(thumbnail_request)
        return cast(TaskHandle[TResult], self.handle)

    def close(self) -> None:
        """Record close once."""

        if self._closed:
            return
        self._closed = True
        self._close()
