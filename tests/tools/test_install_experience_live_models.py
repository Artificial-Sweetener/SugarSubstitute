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

"""Verify live read-only model discovery used by interactive qualification."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODeviceBase
from PySide6.QtGui import QColor, QImage

from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelRecommendation,
)
from substitute.infrastructure.model_recommendations import CivitaiThumbnailFetcher
from tools import install_experience_driver
from tools.install_experience_live_models import (
    TransientRecommendationThumbnailFetcher,
)


class _RecordedThumbnailFetcher(CivitaiThumbnailFetcher):
    """Return one encoded image without accessing the network."""

    def __init__(self, payload: bytes) -> None:
        """Store the test-owned encoded image payload."""

        self._payload = payload
        self.urls: list[str] = []

    def fetch(self, url: str) -> bytes:
        """Record the provider URL and return the encoded image."""

        self.urls.append(url)
        return self._payload


def test_transient_live_thumbnail_preparation_never_writes_files(
    tmp_path: Path,
) -> None:
    """Prepare real-shaped thumbnail bytes entirely in memory for the smoke UI."""

    image = QImage(320, 180, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#6C5CE7"))
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    assert buffer.open(QIODeviceBase.OpenModeFlag.WriteOnly)
    image_format = cast(bytes, "PNG")  # PySide accepts str despite its bytes stub.
    assert image.save(buffer, image_format)
    fetcher = _RecordedThumbnailFetcher(cast(bytes, encoded.data()))
    recommendation = _recommendation()

    asset = TransientRecommendationThumbnailFetcher(fetcher=fetcher).fetch(
        recommendation
    )

    assert fetcher.urls == [recommendation.thumbnail_url]
    assert asset.width > 0
    assert asset.height > 0
    assert asset.payload
    assert list(tmp_path.iterdir()) == []


def test_interactive_onboarding_enables_live_model_discovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep live CivitAI data exclusive to the explicit maintainer walkthrough."""

    received: list[dict[str, object]] = []

    class _Window:
        """Record that the interactive composition reveals its setup window."""

        def __init__(self) -> None:
            """Initialize an unrevealed window double."""

            self.shown = False

        def show(self) -> None:
            """Record the expected interactive reveal."""

            self.shown = True

    class _Session:
        """Expose the minimal interactive session surface."""

        def __init__(self) -> None:
            """Create the window double owned by this session."""

            self.window = _Window()

    sentinel = _Session()

    def record_session(**kwargs: object) -> object:
        """Capture composition flags without creating a window."""

        received.append(dict(kwargs))
        return sentinel

    monkeypatch.setattr(
        "tools.install_experience_onboarding.OnboardingCheckSession",
        record_session,
    )

    session = install_experience_driver.open_interactive_onboarding(
        install_root=tmp_path,
        install_root_locked=True,
    )

    assert cast(object, session) is sentinel
    assert sentinel.window.shown
    assert received == [
        {
            "install_root": tmp_path,
            "install_root_locked": True,
            "live_model_discovery": True,
        }
    ]


def _recommendation() -> ModelRecommendation:
    """Return one trusted CivitAI-shaped recommendation."""

    return ModelRecommendation(
        family_id=ModelFamilyId.SDXL,
        model_id=101,
        version_id=1010,
        model_name="Model",
        version_name="v1",
        creator="creator",
        file_name="model.safetensors",
        size_bytes=1024,
        sha256=f"{101:064x}",
        download_url="https://civitai.com/api/download/models/1010",
        model_page_url="https://civitai.com/models/101?modelVersionId=1010",
        thumbnail_image_id=10100,
        thumbnail_url="https://image.civitai.com/model-101.jpeg",
        popularity_rank=1,
    )


__all__ = []
