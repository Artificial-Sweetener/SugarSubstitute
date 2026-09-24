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

"""Coordinate CuteCanvas media layouts with single-video detail playback."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QStackedWidget, QWidget
from cutecanvas import CanvasPresentation, CanvasPresentationKind, CanvasWorkspace
from shiboken6 import isValid

from substitute.application.ports.video import VideoPlaybackEvent, VideoPlayerPort
from substitute.domain.output_media import OutputMediaKind
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_video_badge_overlays import (
    OutputVideoBadgeOverlays,
)
from substitute.presentation.canvas.output.video_playback_page import (
    VideoPlaybackPage,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta


class OutputVideoPresentationCoordinator(QObject):
    """Own player-page switching while leaving every grid with CuteCanvas."""

    def __init__(
        self,
        *,
        parent: QWidget,
        workspace: CanvasWorkspace,
        document: OutputCanvasDocument,
        metadata_for: Callable[[UUID], OutputImageMeta | None],
        player_factory: Callable[
            [Callable[[VideoPlaybackEvent], None]], VideoPlayerPort
        ]
        | None = None,
    ) -> None:
        """Compose the media stack and observe document presentation changes."""

        super().__init__(parent)
        self._workspace = workspace
        self._document = document
        self._metadata_for = metadata_for
        self.video_page = VideoPlaybackPage(parent, player_factory=player_factory)
        self.widget = QStackedWidget(parent)
        self.widget.addWidget(workspace)
        self.widget.addWidget(self.video_page)
        self.widget.setCurrentWidget(workspace)
        self._badges = OutputVideoBadgeOverlays(
            workspace=workspace,
            document=document,
            metadata_for=metadata_for,
        )
        parent.installEventFilter(self)

    def synchronize(self, presentation: CanvasPresentation) -> None:
        """Present video only for single detail and refresh grid play badges."""

        self._badges.synchronize(presentation)
        if presentation.kind is not CanvasPresentationKind.SINGLE:
            self.deactivate()
            return
        composition_id = self._workspace.session.active_composition_id
        media_id = (
            self._document.image_id_for_composition(composition_id)
            if composition_id is not None
            else None
        )
        metadata = self._metadata_for(media_id) if media_id is not None else None
        if not _is_playable_video(metadata):
            self.deactivate()
            return
        assert media_id is not None and metadata is not None
        self.widget.setCurrentWidget(self.video_page)
        self.video_page.present_video(media_id, Path(metadata.path))

    def refresh_badges(self) -> None:
        """Re-evaluate badges after the application registry lookup is installed."""

        self._badges.synchronize()

    def deactivate(self) -> None:
        """Return to CuteCanvas and enforce hidden-player pause and mute policy."""

        self.video_page.set_output_active(False)
        self.widget.setCurrentWidget(self._workspace)

    def retire_media(self, media_id: UUID) -> bool:
        """Unload a retired video and return to the CuteCanvas workspace."""

        retired = self.video_page.retire_video(media_id)
        if retired:
            self.widget.setCurrentWidget(self._workspace)
        return retired

    def close(self) -> None:
        """Release overlays and native playback before the surface is destroyed."""

        self._badges.close()
        self.video_page.close_player()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Enforce pause/mute policy across Output visibility transitions."""

        if not isValid(self.widget) or not isValid(self._workspace):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Hide:
            self.deactivate()
        elif event.type() == QEvent.Type.Show:
            self.synchronize(self._workspace.session.presentation)
        return super().eventFilter(watched, event)


def _is_playable_video(metadata: OutputImageMeta | None) -> bool:
    """Return whether metadata names one validated local video artifact."""

    return bool(
        metadata is not None
        and getattr(metadata, "media_kind", OutputMediaKind.IMAGE)
        is OutputMediaKind.VIDEO
        and metadata.path.strip()
    )


__all__ = ["OutputVideoPresentationCoordinator"]
