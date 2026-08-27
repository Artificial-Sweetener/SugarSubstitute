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

"""Prompt LoRA rendering test support."""

from __future__ import annotations


from collections.abc import Callable
from typing import cast


from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.lora.resolution import (
    PromptLoraResolutionStatus,
)
from tests.support.execution import ImmediateTaskSubmitter
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptEditorTaskExecutor,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail


class _ImmediateDispatcher:
    """Publish test callbacks synchronously."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run one callback immediately."""

        _ = reason
        callback()


def _immediate_prompt_executor() -> PromptEditorTaskExecutor:
    """Return an immediate prompt task executor for thumbnail tests."""

    return PromptEditorTaskExecutor(
        submitter=ImmediateTaskSubmitter(),
        shutdown_callback=lambda: None,
    )


class _AssetRepository:
    """Return configured thumbnail assets and record storage-key reads."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store assets keyed by thumbnail storage key."""

        self.assets = assets
        self.reads: list[str] = []

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Return one asset while recording the storage key."""

        self.reads.append(storage_key)
        return self.assets.get(storage_key)


class _FailingAssetRepository(_AssetRepository):
    """Raise a prompt-like message while recording storage-key reads."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store assets and one prompt-like dynamic exception message."""

        super().__init__(assets)
        self.error_message = "prompt thumbnail secret"

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Raise a deterministic repository failure."""

        self.reads.append(storage_key)
        raise RuntimeError(self.error_message)


def ensure_qapp() -> QApplication:
    """Return a running Qt application for renderer tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _run(display_text: str) -> PromptProjectionRun:
    """Return one inline-object LoRA projection run."""

    return PromptProjectionRun(
        run_id="run:lora",
        kind=PromptProjectionRunKind.INLINE_OBJECT,
        source_start=0,
        source_end=20,
        display_text=display_text,
        source_positions=(0, 20),
        projection_start=0,
        projection_end=1,
        token_id="lora:0",
        renderer_key="lora_chip",
    )


def _token(
    *,
    thumbnail_variants: tuple[PromptProjectionThumbnailVariant, ...] = (),
    value_text: str = "0.8",
    editing_value_text: str | None = None,
    editing_slot_width: float | None = None,
    lora_version_text: str | None = None,
    exists: bool = True,
    lora_status: PromptLoraResolutionStatus | None = None,
) -> PromptProjectionToken:
    """Return one LoRA projection token."""

    resolved_lora_status = lora_status or (
        PromptLoraResolutionStatus.FOUND
        if exists
        else PromptLoraResolutionStatus.MISSING
    )
    return PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=20,
        display_text="Mineru",
        value_text=value_text,
        lora_version_text=lora_version_text,
        exists=exists,
        lora_status=resolved_lora_status,
        editing_value_text=editing_value_text,
        editing_slot_width=editing_slot_width,
        thumbnail_variants=thumbnail_variants,
    )


def _thumbnail_asset(
    storage_key: str,
    color: QColor,
    *,
    width: int = 768,
    height: int = 160,
) -> ThumbnailAsset:
    """Return one Qt-ready banner thumbnail asset."""

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=storage_key,
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )
