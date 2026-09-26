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

"""Draw semantic play badges on CuteCanvas video tiles."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget
from qfluentwidgets import Theme  # type: ignore[import-untyped]
from cutecanvas import (
    CanvasPresentationKind,
    CanvasWorkspace,
    CuteCanvas,
)

from substitute.domain.output_media import OutputMediaKind
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.resources.fluent_app_icon import AppIcon

OUTPUT_VIDEO_BADGE_OVERLAY_NAME = "sugarsubstitute.output.video-play-badge"


class OutputVideoBadgeOverlays(QObject):
    """Attach a non-interactive play cue to each visible video grid tile."""

    def __init__(
        self,
        *,
        workspace: CanvasWorkspace,
        document: OutputCanvasDocument,
        metadata_for: Callable[[UUID], OutputImageMeta | None],
    ) -> None:
        """Observe CuteCanvas presentation changes and retain attached canvases."""

        super().__init__(workspace)
        self._workspace = workspace
        self._document = document
        self._metadata_for = metadata_for
        self._canvases: set[CuteCanvas] = set()
        self._badges: dict[CuteCanvas, _VideoPlayBadge] = {}
        self._watched_canvases: dict[QObject, CuteCanvas] = {}
        workspace.presentationChanged.connect(self.synchronize)
        workspace.destroyed.connect(lambda _object=None: self.close())

    def synchronize(self, _presentation: object | None = None) -> None:
        """Match overlay ownership to the current CuteCanvas grid presentation."""

        self._clear()
        if self._workspace.session.presentation.kind is not CanvasPresentationKind.GRID:
            return
        for image_id in self._document.image_ids():
            metadata = self._metadata_for(image_id)
            if (
                metadata is None
                or getattr(metadata, "media_kind", OutputMediaKind.IMAGE)
                is not OutputMediaKind.VIDEO
            ):
                continue
            composition_id = self._document.composition_id_for(image_id)
            if composition_id is None:
                continue
            canvas = self._workspace.canvasFor(composition_id)
            if canvas is None:
                continue
            badge = _VideoPlayBadge(canvas)
            badge.hide()
            self._badges[canvas] = badge
            for watched in (canvas, *canvas.findChildren(QWidget)):
                watched.setMouseTracking(True)
                watched.installEventFilter(self)
                self._watched_canvases[watched] = canvas
            self._canvases.add(canvas)

    def close(self) -> None:
        """Remove every play badge from its CuteCanvas owner."""

        self._clear()

    def _clear(self) -> None:
        """Unregister overlays before canvases are reused by another presentation."""

        for watched in tuple(self._watched_canvases):
            watched.removeEventFilter(self)
        for badge in self._badges.values():
            badge.close()
            badge.setParent(None)
            badge.deleteLater()
        self._canvases.clear()
        self._badges.clear()
        self._watched_canvases.clear()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Reveal the play cue only while the pointer is over its video tile."""

        canvas = self._watched_canvases.get(watched)
        badge = self._badges.get(canvas) if canvas is not None else None
        if badge is not None:
            if event.type() == QEvent.Type.Resize:
                badge.align_to_parent()
            elif event.type() in {
                QEvent.Type.Enter,
                QEvent.Type.HoverEnter,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonPress,
            }:
                badge.align_to_parent()
                badge.raise_()
                badge.show()
            elif event.type() in {QEvent.Type.Leave, QEvent.Type.HoverLeave}:
                badge.hide()
        return super().eventFilter(watched, event)


class _VideoPlayBadge(QWidget):
    """Render a Fluent play affordance above one CuteCanvas viewport."""

    def __init__(self, parent: CuteCanvas) -> None:
        """Create a transparent, non-interactive tile overlay."""

        super().__init__(parent)
        self.setObjectName(OUTPUT_VIDEO_BADGE_OVERLAY_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.align_to_parent()

    def align_to_parent(self) -> None:
        """Center the badge and scale it within the current tile bounds."""

        parent = self.parentWidget()
        if parent is None:
            return
        diameter = min(48, max(28, round(min(parent.width(), parent.height()) * 0.18)))
        self.setGeometry(
            (parent.width() - diameter) // 2,
            (parent.height() - diameter) // 2,
            diameter,
            diameter,
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the Fluent play glyph over a compact circular material."""

        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        circle = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setPen(QPen(QColor(255, 255, 255, 210), 1.5))
        painter.setBrush(QColor(0, 0, 0, 165))
        painter.drawEllipse(circle)
        icon_size = max(16, round(self.width() * 0.54))
        icon_rect = QRectF(
            (self.width() - icon_size) / 2.0 + self.width() * 0.025,
            (self.height() - icon_size) / 2.0,
            icon_size,
            icon_size,
        )
        AppIcon.PLAY_20_REGULAR.icon(Theme.DARK).paint(
            painter,
            icon_rect.toRect(),
        )


__all__ = ["OUTPUT_VIDEO_BADGE_OVERLAY_NAME", "OutputVideoBadgeOverlays"]
