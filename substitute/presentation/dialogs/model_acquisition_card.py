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

"""Render one reviewed missing-model item with installer portrait styling."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QFont, QImage, QPalette, QColor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelUnresolvedReference,
)
from substitute.domain.model_metadata import CivitaiDownloadAccess
from substitute.presentation.localization import LocalizedLabel
from substitute.presentation.onboarding.onboarding_download_text import (
    format_model_size,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    THUMBNAIL_SIZE,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)

UrlOpener = Callable[[str], bool]


class ModelAcquisitionCard(QFrame):
    """Present one exact missing model and its provider access state."""

    def __init__(
        self,
        reference: RecipeModelUnresolvedReference,
        *,
        network: QNetworkAccessManager,
        open_url: UrlOpener,
        preview_image: QImage | None = None,
        parent: QWidget,
    ) -> None:
        """Build the card and begin an allowed asynchronous thumbnail request."""

        super().__init__(parent)
        self._reply: QNetworkReply | None = None
        self._reference = reference
        self.setObjectName(f"ModelAcquisitionCard_{reference.sha256[:12]}")
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        candidate = reference.candidate
        title = (
            candidate.model_name
            if candidate is not None and candidate.model_name.strip()
            else _file_name(reference.value)
        )
        metadata = _metadata(reference)
        self.portrait = RecommendationPortrait(
            image=preview_image,
            title=title,
            thumbnail_failed=(
                preview_image is None
                and (candidate is None or candidate.thumbnail_url is None)
            ),
            selected=False,
            accessible_name=title,
            metadata=metadata,
            portrait_size=THUMBNAIL_SIZE,
            selectable=False,
            parent=self,
        )
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignCenter)
        if candidate is not None:
            self._build_information_button(candidate.model_page_url, open_url)
            if candidate.download_access is CivitaiDownloadAccess.API_KEY_REQUIRED:
                self._build_access_badge()
            if preview_image is None and candidate.thumbnail_url:
                self._request_thumbnail(network, candidate.thumbnail_url)
        else:
            self._build_unavailable_badge()

    @property
    def reference(self) -> RecipeModelUnresolvedReference:
        """Return the exact model reference represented by this card."""

        return self._reference

    def _build_information_button(self, url: str, open_url: UrlOpener) -> None:
        """Create a keyboard-focusable provider information action."""

        button = QToolButton(self.portrait)
        button.setObjectName("ModelAcquisitionInformationButton")
        button.setAutoRaise(True)
        button.setIcon(FIF.GLOBE.icon())
        button.setFixedSize(32, 32)
        button.setIconSize(QSize(20, 20))
        button.move(10, 10)
        label = render_application_text(
            app_text("View %1 on CivitAI", _title(self._reference))
        )
        button.setAccessibleName(label)
        set_fluent_tooltip_text(button, label)
        button.clicked.connect(lambda: open_url(url))
        button.raise_()

    def _build_access_badge(self) -> None:
        """Mark the exact card whose provider requires authentication."""

        self._build_status_badge(
            app_text("API key required"),
            QColor(255, 228, 145),
        )

    def _build_unavailable_badge(self) -> None:
        """Explain why an exact model cannot join the aggregate download."""

        text = (
            app_text("No safe file")
            if self._reference.civitai_state is RecipeModelCivitaiState.NO_SAFE_FILE
            else app_text("Unavailable")
        )
        self._build_status_badge(text, QColor(255, 174, 162))

    def _build_status_badge(self, text: ApplicationText, color: QColor) -> None:
        """Place a compact provider status opposite the information action."""

        badge = LocalizedLabel(text, self.portrait)
        badge.setObjectName("ModelAcquisitionAccessBadge")
        font = QFont(badge.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        badge.setFont(font)
        palette = QPalette(badge.palette())
        palette.setColor(QPalette.ColorRole.WindowText, color)
        badge.setPalette(palette)
        badge.adjustSize()
        badge.move(THUMBNAIL_SIZE.width() - badge.width() - 10, 10)
        badge.raise_()

    def _request_thumbnail(
        self,
        network: QNetworkAccessManager,
        url: str,
    ) -> None:
        """Fetch one policy-approved provider thumbnail without blocking the UI."""

        self._reply = network.get(QNetworkRequest(QUrl(url)))
        self._reply.finished.connect(self._finish_thumbnail)

    def _finish_thumbnail(self) -> None:
        """Settle the card's asynchronous thumbnail state."""

        reply = self._reply
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.portrait.set_thumbnail_unavailable()
                return
            image = QImage.fromData(cast(bytes, reply.readAll().data()))
            if image.isNull():
                self.portrait.set_thumbnail_unavailable()
                return
            self.portrait.set_image(image)
        finally:
            reply.deleteLater()
            self._reply = None


def _metadata(reference: RecipeModelUnresolvedReference) -> str:
    """Return compact kind, size, and availability metadata."""

    candidate = reference.candidate
    kind = _kind_label(reference.kind)
    if candidate is None:
        return kind
    if candidate.size_kb is None:
        return kind
    return f"{kind} · {format_model_size(round(candidate.size_kb * 1024))}"


def _kind_label(kind: str) -> str:
    """Return a compact card label for one Backend model kind."""

    label = {
        "checkpoints": app_text("Checkpoint"),
        "loras": app_text("LoRA"),
        "upscale_models": app_text("Upscaler"),
        "vae": app_text("VAE"),
        "controlnet": app_text("ControlNet"),
    }.get(kind)
    return (
        render_application_text(label) if label is not None else kind.replace("_", " ")
    )


def _file_name(value: str) -> str:
    """Return a readable file name from a portable model value."""

    normalized = value.strip().replace("\\", "/")
    return normalized.rsplit("/", maxsplit=1)[-1] or render_application_text(
        app_text("Model file")
    )


def _title(reference: RecipeModelUnresolvedReference) -> str:
    """Return the provider title used by information accessibility copy."""

    candidate = reference.candidate
    return (
        candidate.model_name if candidate is not None else _file_name(reference.value)
    )


__all__ = ["ModelAcquisitionCard", "UrlOpener"]
