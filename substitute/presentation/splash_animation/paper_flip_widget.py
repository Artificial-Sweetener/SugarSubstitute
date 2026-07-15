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

"""Render packaged splash poses as a compact animated paper flip."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
import random
import time
from typing import cast

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QSizePolicy, QWidget

from substitute.presentation.splash_animation.pose_library import SplashPose
from substitute.presentation.splash_animation.pose_selector import (
    RecencyWeightedPoseSelector,
)
from substitute.presentation.splash_animation.projection import (
    ProjectionParameters,
    build_projected_quad,
    is_valid_projected_quad,
)

Clock = Callable[[], float]


class SplashFlipPhase(Enum):
    """Identify the active paper-flip animation phase."""

    HOLD = "hold"
    FLIP = "flip"


@dataclass(frozen=True)
class SplashFlipSettings:
    """Collect production timing and projection settings for the splash flip."""

    base_hold_ms: int = 950
    hold_jitter_ms: int = 150
    flip_ms: int = 390
    projection: ProjectionParameters = ProjectionParameters()
    edge_thickness: float = 1.25
    edge_opacity: float = 0.35
    edge_window_fraction: float = 0.035

    def normalized(self) -> "SplashFlipSettings":
        """Return settings clamped to ranges that keep animation stable."""

        return SplashFlipSettings(
            base_hold_ms=max(0, self.base_hold_ms),
            hold_jitter_ms=max(0, self.hold_jitter_ms),
            flip_ms=max(120, self.flip_ms),
            projection=self.projection.normalized(),
            edge_thickness=max(0.0, min(12.0, self.edge_thickness)),
            edge_opacity=max(0.0, min(1.0, self.edge_opacity)),
            edge_window_fraction=max(0.005, min(0.12, self.edge_window_fraction)),
        )


class SplashPaperFlipWidget(QWidget):
    """Animate transparent splash pose PNGs through a perspective paper flip."""

    def __init__(
        self,
        poses: tuple[SplashPose, ...],
        selector: RecencyWeightedPoseSelector[SplashPose],
        parent: QWidget | None = None,
        *,
        settings: SplashFlipSettings | None = None,
        clock: Clock = time.monotonic,
        hold_random: random.Random | None = None,
    ) -> None:
        """Create a compact animated splash visual bound to one pose selector."""

        super().__init__(parent)
        if not poses:
            raise ValueError("SplashPaperFlipWidget requires at least one pose.")

        self._poses = poses
        self._selector = selector
        self._settings = (settings or SplashFlipSettings()).normalized()
        self._clock = clock
        self._hold_random = hold_random or random.Random()
        self._phase = SplashFlipPhase.HOLD
        self._phase_started_at = self._clock()
        self._current_hold_ms = self._sample_hold_duration()
        self._current_pose = poses[0]
        self._selector.commit(self._current_pose)
        self._next_pose = self._selector.choose_next(current_pose=self._current_pose)
        self._direction = 1
        self._last_progress = 0.0
        self._last_quad = QPolygonF()

        self.setObjectName("SplashPaperFlipWidget")
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @property
    def current_pose(self) -> SplashPose:
        """Return the pose currently considered visible."""

        return self._current_pose

    @property
    def next_pose(self) -> SplashPose:
        """Return the pose queued for the next flip."""

        return self._next_pose

    @property
    def phase(self) -> SplashFlipPhase:
        """Return the active animation phase."""

        return self._phase

    @property
    def current_hold_ms(self) -> int:
        """Return the sampled duration for the active hold phase."""

        return self._current_hold_ms

    def set_settings(self, settings: SplashFlipSettings) -> None:
        """Replace animation settings and resample the active hold duration."""

        self._settings = settings.normalized()
        if self._phase is SplashFlipPhase.HOLD:
            self._current_hold_ms = self._sample_hold_duration()
            self._phase_started_at = self._clock()
        self.update()

    def paintEvent(self, _event: object) -> None:
        """Draw the current paper-flip animation frame."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        progress = self._current_progress()
        pixmap = self._current_render_pose(progress).pixmap
        source = QRectF(0.0, 0.0, float(pixmap.width()), float(pixmap.height()))
        source_quad = QPolygonF(
            [
                source.topLeft(),
                source.topRight(),
                source.bottomRight(),
                source.bottomLeft(),
            ]
        )
        target_quad = build_projected_quad(
            self._card_bounds(source),
            progress=progress,
            direction=self._direction,
            parameters=self._settings.projection,
        )
        self._last_progress = progress
        self._last_quad = target_quad

        transform = cast(
            QTransform | None, QTransform.quadToQuad(source_quad, target_quad)
        )
        if transform is not None and is_valid_projected_quad(target_quad):
            painter.save()
            painter.setTransform(transform)
            painter.drawPixmap(source, pixmap, source)
            painter.restore()

        self._paint_paper_edge(painter, target_quad, progress)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start an immediate flip when the mascot is clicked during hold."""

        if event.button() == Qt.MouseButton.LeftButton and self.trigger_flip():
            event.accept()
            return
        super().mousePressEvent(event)

    def closeEvent(self, event: object) -> None:
        """Stop frame scheduling when the splash visual closes."""

        self._timer.stop()
        super().closeEvent(event)  # type: ignore[arg-type]

    def trigger_flip(self) -> bool:
        """Start an immediate mascot flip when the widget is currently holding."""

        if self._phase is not SplashFlipPhase.HOLD:
            return False
        self._start_flip()
        self.update()
        return True

    def _tick(self) -> None:
        """Advance animation state and schedule repaint."""

        elapsed_ms = (self._clock() - self._phase_started_at) * 1000.0
        if self._phase is SplashFlipPhase.HOLD:
            if elapsed_ms >= self._current_hold_ms:
                self._start_flip()
        elif elapsed_ms >= self._settings.flip_ms:
            self._finish_flip()

        self.update()

    def _start_flip(self) -> None:
        """Enter the flip phase and alternate the visual direction."""

        self._phase = SplashFlipPhase.FLIP
        self._phase_started_at = self._clock()
        self._direction *= -1

    def _finish_flip(self) -> None:
        """Commit the queued pose and return to a newly sampled hold."""

        self._current_pose = self._next_pose
        self._selector.commit(self._current_pose)
        self._next_pose = self._selector.choose_next(current_pose=self._current_pose)
        self._phase = SplashFlipPhase.HOLD
        self._phase_started_at = self._clock()
        self._current_hold_ms = self._sample_hold_duration()
        self._last_progress = 0.0

    def _current_progress(self) -> float:
        """Return normalized front-edge-front flip progress."""

        if self._phase is SplashFlipPhase.HOLD:
            return 0.0
        elapsed_ms = (self._clock() - self._phase_started_at) * 1000.0
        return max(0.0, min(1.0, elapsed_ms / float(self._settings.flip_ms)))

    def _current_render_pose(self, progress: float) -> SplashPose:
        """Return the pose pixmap that should be painted for one progress value."""

        if self._phase is SplashFlipPhase.FLIP and progress >= 0.5:
            return self._next_pose
        return self._current_pose

    def _sample_hold_duration(self) -> int:
        """Return one jittered hold duration in milliseconds."""

        jitter = self._settings.hold_jitter_ms
        if jitter <= 0:
            return self._settings.base_hold_ms
        sampled = self._settings.base_hold_ms + self._hold_random.randint(
            -jitter, jitter
        )
        return max(0, sampled)

    def _card_bounds(self, source: QRectF) -> QRectF:
        """Return aspect-preserving mascot bounds inside the PSD layer rectangle."""

        available = QRectF(self.rect())
        if source.width() <= 0 or source.height() <= 0:
            return available
        source_aspect = source.width() / source.height()
        available_aspect = available.width() / max(1.0, available.height())
        if available_aspect > source_aspect:
            height = available.height()
            width = height * source_aspect
        else:
            width = available.width()
            height = width / source_aspect
        return QRectF(
            available.center().x() - width / 2.0,
            available.center().y() - height / 2.0,
            width,
            height,
        )

    def _paint_paper_edge(
        self,
        painter: QPainter,
        quad: QPolygonF,
        progress: float,
    ) -> None:
        """Draw a subtle paper edge while the pose is close to edge-on."""

        midpoint_distance = abs(progress - 0.5)
        edge_window = self._settings.edge_window_fraction
        if (
            self._settings.edge_thickness <= 0
            or self._settings.edge_opacity <= 0
            or midpoint_distance > edge_window
            or quad.count() != 4
        ):
            return

        top_mid = _midpoint(_quad_point(quad, 0), _quad_point(quad, 1))
        bottom_mid = _midpoint(_quad_point(quad, 2), _quad_point(quad, 3))
        midpoint_alpha = 1.0 - (midpoint_distance / edge_window)
        alpha = int(255 * self._settings.edge_opacity * midpoint_alpha)
        pen = QPen(QColor(54, 16, 16, alpha), self._settings.edge_thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.save()
        painter.setPen(pen)
        painter.drawLine(top_mid, bottom_mid)
        painter.restore()


def _quad_point(quad: QPolygonF, index: int) -> QPointF:
    """Return one quad point through Qt's typed accessor."""

    return quad.at(index)


def _midpoint(first: QPointF, second: QPointF) -> QPointF:
    """Return the midpoint between two floating-point Qt points."""

    return QPointF((first.x() + second.x()) / 2.0, (first.y() + second.y()) / 2.0)


def splash_flip_settings_with_projection(
    settings: SplashFlipSettings,
    *,
    perspective_strength: float,
) -> SplashFlipSettings:
    """Return settings with the projection perspective changed."""

    return replace(
        settings,
        projection=replace(
            settings.projection,
            perspective_strength=perspective_strength,
        ),
    ).normalized()


__all__ = [
    "SplashFlipPhase",
    "SplashFlipSettings",
    "SplashPaperFlipWidget",
    "splash_flip_settings_with_projection",
]
