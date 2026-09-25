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

"""Order active video decoder unload before temporary artifact release."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRecord
from substitute.domain.output_media import OutputMediaKind
from substitute.domain.workflow import ImageMeta
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.output_media_retirement")


class RetirableVideoPresentation(Protocol):
    """Unload a media identity currently retained by the Output player."""

    def retire_media(self, media_id: UUID) -> bool:
        """Return whether the media no longer has an active decoder lease."""


class OutputMediaRetirementCoordinator:
    """Retire registry-owned video resources in dependency-safe order."""

    def __init__(
        self,
        *,
        video_presentation: Callable[[], RetirableVideoPresentation | None],
        release_artifact: Callable[[ImageMeta], None],
    ) -> None:
        """Store lazy UI lookup and the temporary artifact owner boundary."""

        self._video_presentation = video_presentation
        self._release_artifact = release_artifact

    def retire_record(self, image_id: UUID, record: CanvasImageRecord) -> None:
        """Unload video playback before releasing the retired artifact lease."""

        metadata = record.metadata
        if metadata.media_kind is OutputMediaKind.VIDEO:
            presentation = self._video_presentation()
            if presentation is not None and not presentation.retire_media(image_id):
                log_warning(
                    _LOGGER,
                    "Deferred temporary video release after decoder unload failed",
                    media_id=str(image_id),
                )
                return
        self._release_artifact(metadata)


__all__ = ["OutputMediaRetirementCoordinator", "RetirableVideoPresentation"]
