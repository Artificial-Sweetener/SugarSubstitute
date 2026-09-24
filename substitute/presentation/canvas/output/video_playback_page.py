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

"""Present generated video playback and explicit frame controls."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoPlayerPort,
)
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_player import MpvVideoPlayer
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoPlaybackController,
)

_SEEK_STEPS = 10_000
_PLAY_OR_PAUSE = app_text("Play or pause")
_PREVIOUS_FRAME = app_text("Previous frame")
_NEXT_FRAME = app_text("Next frame")
_LOOP_VIDEO = app_text("Loop video")
_MUTE_VIDEO = app_text("Mute video")
_VIDEO_VOLUME = app_text("Video volume")
_VIDEO_POSITION = app_text("Video position")
_RETRY_VIDEO = app_text("Retry video")


class VideoPlaybackPage(QWidget):
    """Host one native video surface and its localized playback controls."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        player_factory: Callable[
            [Callable[[VideoPlaybackEvent], None]], VideoPlayerPort
        ]
        | None = None,
    ) -> None:
        """Create the render surface, playback controller, and control bar."""

        super().__init__(parent)
        self.setObjectName("outputVideoPlaybackPage")
        self._surface = QFrame(self)
        self._surface.setObjectName("outputVideoRenderSurface")
        self._surface.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._surface.setStyleSheet("background: #000000; border: none;")
        self._status = QLabel(self)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._status.hide()
        self._play = QPushButton("▶", self)
        self._previous_frame = QPushButton("|◀", self)
        self._next_frame = QPushButton("▶|", self)
        self._loop = QPushButton("↻", self)
        self._loop.setCheckable(True)
        self._loop.setChecked(True)
        self._mute = QPushButton("M", self)
        self._mute.setCheckable(True)
        self._volume = QSlider(Qt.Orientation.Horizontal, self)
        self._volume.setRange(0, 100)
        self._volume.setValue(100)
        self._volume.setMaximumWidth(120)
        self._seek = QSlider(Qt.Orientation.Horizontal, self)
        self._seek.setRange(0, _SEEK_STEPS)
        self._time = QLabel("00:00 / 00:00", self)
        self._retry = QPushButton(self)
        self._retry.hide()

        factory = player_factory or self._create_bundled_player
        self.controller = VideoPlaybackController(
            player_factory=factory,
            parent=self,
        )
        self.controller.snapshotChanged.connect(self._apply_snapshot)
        self.destroyed.connect(lambda _object=None: self.controller.close())
        self._compose_layout()
        self._connect_controls()
        self._install_shortcuts()
        self.retranslate()
        self._apply_snapshot(self.controller.snapshot)

    @property
    def render_surface(self) -> QWidget:
        """Return the native surface used by the bundled player."""

        return self._surface

    def present_video(self, media_id: UUID, path: Path) -> None:
        """Present one validated local video and leave it paused."""

        self.controller.activate(media_id, path)

    def set_output_active(self, active: bool) -> None:
        """Apply output visibility policy to playback and audio."""

        if active:
            snapshot = self.controller.snapshot
            media_id = snapshot.media_id
            if media_id is not None:
                self.controller.set_playing(False)
            return
        self.controller.deactivate()

    def close_player(self) -> None:
        """Release the native player before the Qt render surface is destroyed."""

        self.controller.close()

    def retranslate(self) -> None:
        """Refresh every SugarSubstitute-owned playback label."""

        play_or_pause = render_application_text(_PLAY_OR_PAUSE)
        previous_frame = render_application_text(_PREVIOUS_FRAME)
        next_frame = render_application_text(_NEXT_FRAME)
        loop_video = render_application_text(_LOOP_VIDEO)
        mute_video = render_application_text(_MUTE_VIDEO)
        video_volume = render_application_text(_VIDEO_VOLUME)
        video_position = render_application_text(_VIDEO_POSITION)
        retry_video = render_application_text(_RETRY_VIDEO)
        set_fluent_tooltip_text(self._play, play_or_pause)
        self._play.setAccessibleName(play_or_pause)
        set_fluent_tooltip_text(self._previous_frame, previous_frame)
        self._previous_frame.setAccessibleName(previous_frame)
        set_fluent_tooltip_text(self._next_frame, next_frame)
        self._next_frame.setAccessibleName(next_frame)
        set_fluent_tooltip_text(self._loop, loop_video)
        self._loop.setAccessibleName(loop_video)
        set_fluent_tooltip_text(self._mute, mute_video)
        self._mute.setAccessibleName(mute_video)
        set_fluent_tooltip_text(self._volume, video_volume)
        self._volume.setAccessibleName(video_volume)
        set_fluent_tooltip_text(self._seek, video_position)
        self._seek.setAccessibleName(video_position)
        self._retry.setText(retry_video)
        self._retry.setAccessibleName(retry_video)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Retranslate the playback page when application language changes."""

        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        super().changeEvent(event)

    def _compose_layout(self) -> None:
        """Build a render-first page whose controls retain stable geometry."""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._surface, 1)
        root.addWidget(self._status)
        controls = QHBoxLayout()
        controls.setContentsMargins(8, 6, 8, 6)
        controls.addWidget(self._previous_frame)
        controls.addWidget(self._play)
        controls.addWidget(self._next_frame)
        controls.addWidget(self._seek, 1)
        controls.addWidget(self._time)
        controls.addWidget(self._loop)
        controls.addWidget(self._mute)
        controls.addWidget(self._volume)
        controls.addWidget(self._retry)
        root.addLayout(controls)

    def _connect_controls(self) -> None:
        """Translate control gestures into typed controller commands."""

        self._play.clicked.connect(self._toggle_playback)
        self._previous_frame.clicked.connect(self.controller.step_previous_frame)
        self._next_frame.clicked.connect(self.controller.step_next_frame)
        self._loop.toggled.connect(self.controller.set_loop_enabled)
        self._mute.toggled.connect(self.controller.set_user_muted)
        self._volume.valueChanged.connect(self.controller.set_volume)
        self._seek.sliderReleased.connect(self._seek_released)
        self._retry.clicked.connect(self.controller.retry)

    def _install_shortcuts(self) -> None:
        """Install keyboard equivalents scoped to the visible playback page."""

        for sequence, callback in (
            ("Space", self._toggle_playback),
            (",", self.controller.step_previous_frame),
            (".", self.controller.step_next_frame),
            ("L", lambda: self._loop.setChecked(not self._loop.isChecked())),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    def _create_bundled_player(
        self,
        callback: Callable[[VideoPlaybackEvent], None],
    ) -> VideoPlayerPort:
        """Create the project-owned player against this page's native surface."""

        return MpvVideoPlayer(
            runtime=MpvRuntime.bundled(),
            player_generation=1,
            event_callback=callback,
            native_window_id=int(self._surface.winId()),
        )

    @Slot()
    def _toggle_playback(self) -> None:
        """Toggle explicit play/pause state from the latest observation."""

        snapshot = self.controller.snapshot
        self.controller.set_playing(snapshot.paused)

    @Slot()
    def _seek_released(self) -> None:
        """Seek from the normalized slider only when duration is known."""

        duration = self.controller.snapshot.duration_seconds
        if duration is None or duration <= 0:
            return
        self.controller.seek(duration * self._seek.value() / _SEEK_STEPS)

    @Slot(object)
    def _apply_snapshot(self, value: object) -> None:
        """Project one coherent controller snapshot into the controls."""

        if not isinstance(value, VideoPlaybackSnapshot):
            return
        self._play.setText("▶" if value.paused else "❚❚")
        ready = value.state in {
            VideoPlaybackState.READY,
            VideoPlaybackState.PLAYING,
            VideoPlaybackState.ENDED,
        }
        for control in (
            self._play,
            self._previous_frame,
            self._next_frame,
            self._seek,
            self._loop,
        ):
            control.setEnabled(ready)
        self._loop.blockSignals(True)
        self._loop.setChecked(value.loop_enabled)
        self._loop.blockSignals(False)
        self._mute.blockSignals(True)
        self._mute.setChecked(value.user_muted)
        self._mute.blockSignals(False)
        self._volume.blockSignals(True)
        self._volume.setValue(value.volume)
        self._volume.blockSignals(False)
        self._seek.blockSignals(True)
        self._seek.setValue(_normalized_seek(value))
        self._seek.blockSignals(False)
        self._time.setText(
            f"{_format_time(value.time_seconds)} / {_format_time(value.duration_seconds)}"
        )
        error = value.error if value.state is VideoPlaybackState.ERROR else None
        self._status.setText(error or "")
        self._status.setVisible(bool(error))
        self._retry.setVisible(bool(error))


def _normalized_seek(snapshot: VideoPlaybackSnapshot) -> int:
    """Return a bounded slider position for one playback snapshot."""

    if (
        snapshot.time_seconds is None
        or snapshot.duration_seconds is None
        or snapshot.duration_seconds <= 0
    ):
        return 0
    return min(
        _SEEK_STEPS,
        max(0, round(snapshot.time_seconds / snapshot.duration_seconds * _SEEK_STEPS)),
    )


def _format_time(value: float | None) -> str:
    """Format seconds as stable elapsed playback text."""

    seconds = max(0, int(value or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


__all__ = ["VideoPlaybackPage"]
