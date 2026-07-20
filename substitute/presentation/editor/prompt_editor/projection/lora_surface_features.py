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

"""Delegate LoRA tooltip, context, and thumbnail viewport requests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QScrollBar, QWidget

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    ensure_fluent_tooltip_filter,
)
from sugarsubstitute_shared.presentation.localization import (
    translate_application_message,
    translate_application_text,
)

from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .layout_engine import PromptProjectionLayout
from .model import (
    PromptProjectionDocument,
    PromptProjectionThumbnailVariant,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)


class PromptSurfaceLoraFeatureHost(Protocol):
    """Expose prepared projection state needed by LoRA viewport feature requests."""

    _layout: PromptProjectionLayout
    _projection_document: PromptProjectionDocument

    def viewport(self) -> QWidget:
        """Return the viewport that receives tooltip and repaint events."""

    def hovered_token(self) -> PromptProjectionToken | None:
        """Return the currently hovered prepared projection token."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the scrollbar that owns the visible document offset."""

    def _emit_lora_context_menu_request(
        self,
        token: PromptProjectionToken,
        global_pos: QPoint,
    ) -> None:
        """Emit one prepared LoRA context-menu request."""

    def _invalidate_projection_content_cache(self, *, reason: str) -> None:
        """Invalidate cached projection content after thumbnail media changes."""

    def _token_at_viewport_position(
        self,
        local_position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the prepared projection token under one viewport-local point."""


class PromptSurfaceLoraThumbnailPreloader(Protocol):
    """Describe explicit thumbnail preload requests for visible LoRA media."""

    def preload_banner_pixmap_for_variants(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Queue one banner thumbnail preload request."""

    def install_banner_pixmap_for_variants_now(
        self,
        variants: tuple[PromptProjectionThumbnailVariant, ...],
        size: QSize,
        *,
        device_pixel_ratio: float = 1.0,
    ) -> bool:
        """Install one local cached banner thumbnail immediately."""

    def has_pending_work(self) -> bool:
        """Return whether thumbnail preloading is still pending."""

    def run_when_idle(self, callback: Callable[[], None]) -> None:
        """Run a callback once currently pending thumbnail work settles."""


class PromptSurfaceLoraFeatureDelegate:
    """Own LoRA viewport feature requests that consume prepared projection state."""

    def __init__(
        self,
        host: PromptSurfaceLoraFeatureHost,
        *,
        thumbnail_cache: PromptLoraThumbnailCache,
        thumbnail_preloader: PromptSurfaceLoraThumbnailPreloader | None = None,
    ) -> None:
        """Bind LoRA tooltip, context, and thumbnail behavior to a surface host."""

        self._host = host
        self._thumbnail_cache = thumbnail_cache
        self._thumbnail_preloader = thumbnail_preloader
        self._tooltip_filter: FluentToolTipFilter | None = None

    @property
    def thumbnail_cache(self) -> PromptLoraThumbnailCache:
        """Return the thumbnail cache used by LoRA inline renderers."""

        return self._thumbnail_cache

    def install_tooltip_filter(self) -> None:
        """Install delayed QFluent tooltips for inline LoRA chip labels."""

        self._tooltip_filter = ensure_fluent_tooltip_filter(
            cast(QWidget, self._host),
            self._host.viewport(),
            show_delay_ms=600,
            cursor_anchor=True,
            tooltip_provider=self.tooltip_for_hover_event,
        )

    def tooltip_for_hover_event(
        self,
        watched: object,
        event: object,
    ) -> str | None:
        """Return full page/version text for the hovered prepared LoRA chip."""

        del watched
        local_position = _local_point_for_tooltip_event(event)
        if local_position is None:
            local_position = QPointF(self._host.viewport().mapFromGlobal(QCursor.pos()))
        token = (
            self._host.hovered_token()
            if local_position is None
            else self._host._token_at_viewport_position(local_position)
        )
        if token is None:
            return None
        return lora_token_tooltip_text(token)

    def request_context_menu(
        self,
        viewport_position: QPointF,
        global_pos: QPoint,
    ) -> bool:
        """Emit a LoRA context-menu request when the clicked token has actions."""

        token = self._host._token_at_viewport_position(viewport_position)
        if (
            token is None
            or token.kind is not PromptProjectionTokenKind.LORA
            or token.model_page_url is None
            or not token.model_page_url.strip()
        ):
            return False
        self._host._emit_lora_context_menu_request(token, global_pos)
        return True

    def preload_visible_banners(self, *, on_complete: Callable[[], None]) -> bool:
        """Preload visible LoRA banners and notify when queued work is ready."""

        queued_count = self.prewarm_visible_banners()
        preloader = self._thumbnail_preloader
        if preloader is None:
            return False
        has_pending_work = preloader.has_pending_work()
        if queued_count <= 0 or not has_pending_work:
            return False
        preloader.run_when_idle(on_complete)
        return True

    def prewarm_visible_banners(self) -> int:
        """Queue thumbnail loads for visible found LoRA chips after layout."""

        preloader = self._thumbnail_preloader
        if preloader is None:
            return 0
        viewport = self._host.viewport()
        viewport_rect = QRectF(viewport.rect())
        if viewport_rect.isEmpty():
            return 0
        scroll_offset = float(self._host.verticalScrollBar().value())
        device_pixel_ratio = viewport.devicePixelRatioF()
        queued_count = 0
        for token in self._host._projection_document.tokens:
            if token.kind is not PromptProjectionTokenKind.LORA:
                continue
            if not _is_visible_lora_thumbnail_candidate(token):
                continue
            token_rect = self._host._layout.token_rect(
                token,
                scroll_offset=scroll_offset,
            )
            if token_rect is None:
                continue
            if not token_rect.intersects(viewport_rect):
                continue
            requested_size = QSize(
                max(1, round(token_rect.width())),
                max(1, round(token_rect.height())),
            )
            immediate = preloader.install_banner_pixmap_for_variants_now(
                token.thumbnail_variants,
                requested_size,
                device_pixel_ratio=device_pixel_ratio,
            )
            if immediate:
                continue
            queued = preloader.preload_banner_pixmap_for_variants(
                token.thumbnail_variants,
                requested_size,
                device_pixel_ratio=device_pixel_ratio,
            )
            if not queued:
                continue
            queued_count += 1
            if queued_count >= 32:
                return queued_count
        return queued_count

    def update_lora_thumbnail_pixmap(self, storage_key: str) -> None:
        """Repaint visible LoRA chips that reference a ready thumbnail asset."""

        if not storage_key:
            return
        self._host._invalidate_projection_content_cache(reason="lora_thumbnail_ready")
        viewport = self._host.viewport()
        viewport_rect = QRectF(viewport.rect())
        if viewport_rect.isEmpty():
            return
        scroll_offset = float(self._host.verticalScrollBar().value())
        matched_count = 0
        repainted_count = 0
        for token in self._host._projection_document.tokens:
            if token.kind is not PromptProjectionTokenKind.LORA:
                continue
            if not any(
                variant.storage_key == storage_key
                for variant in token.thumbnail_variants
            ):
                continue
            matched_count += 1
            token_rect = self._host._layout.token_rect(
                token,
                scroll_offset=scroll_offset,
            )
            if token_rect is None or not token_rect.intersects(viewport_rect):
                continue
            repainted_count += 1
            viewport.update(token_rect.toAlignedRect().adjusted(-2, -2, 2, 2))


def lora_token_tooltip_text(token: PromptProjectionToken) -> str | None:
    """Return full unelided tooltip text for one projected LoRA token."""

    if token.kind is not PromptProjectionTokenKind.LORA:
        return None
    if token.lora_status is not None and token.lora_status.value == "ambiguous":
        prompt_name = (token.detail_text or token.display_text).strip()
        if not prompt_name:
            return translate_application_text("LoRA name is ambiguous")
        return translate_application_message(
            "LoRA name is ambiguous: %1",
            prompt_name,
        )
    if token.lora_status is not None and token.lora_status.value in {
        "pending_no_authority",
        "catalog_unavailable",
    }:
        prompt_name = (token.detail_text or token.display_text).strip()
        if not prompt_name:
            return translate_application_text("LoRA catalog is still resolving")
        return translate_application_message(
            "LoRA catalog is still resolving: %1",
            prompt_name,
        )
    if not token.exists:
        prompt_name = (token.detail_text or token.display_text).strip()
        if not prompt_name:
            return translate_application_text("LoRA not found")
        return translate_application_message("LoRA not found: %1", prompt_name)
    page_name = token.display_text.strip()
    version_name = (
        "" if token.lora_version_text is None else token.lora_version_text.strip()
    )
    lines: list[str] = []
    if page_name:
        lines.append(translate_application_message("Model: %1", page_name))
    if version_name:
        lines.append(translate_application_message("Version: %1", version_name))
    if not lines:
        return None
    return "\n".join(lines)


def _is_visible_lora_thumbnail_candidate(token: PromptProjectionToken) -> bool:
    """Return whether one token can request a prepared LoRA thumbnail banner."""

    return token.kind is PromptProjectionTokenKind.LORA and bool(
        token.thumbnail_variants
    )


def _local_point_for_tooltip_event(event: object) -> QPointF | None:
    """Return a viewport-local point exposed by a hover or tooltip event."""

    position = getattr(event, "position", None)
    if callable(position):
        value = position()
        if isinstance(value, QPointF):
            return value
        if isinstance(value, QPoint):
            return QPointF(value)
    pos = getattr(event, "pos", None)
    if callable(pos):
        value = pos()
        if isinstance(value, QPoint):
            return QPointF(value)
    return None


__all__ = [
    "PromptSurfaceLoraFeatureDelegate",
    "PromptSurfaceLoraFeatureHost",
    "PromptSurfaceLoraThumbnailPreloader",
    "lora_token_tooltip_text",
]
