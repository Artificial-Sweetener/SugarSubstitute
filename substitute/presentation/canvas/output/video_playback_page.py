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

from PySide6.QtCore import QEvent, QSize, Qt, Slot
from PySide6.QtGui import QColor, QKeySequence, QShortcut
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
from qfluentwidgets import themeColor  # type: ignore[import-untyped]

from substitute.application.ports.video import (
    VideoPlaybackEvent,
    VideoPlaybackFallback,
    VideoPlaybackSnapshot,
    VideoPlaybackState,
    VideoPlayerPort,
)
from substitute.domain.generation import VideoPlaybackSettings
from substitute.infrastructure.video.mpv_runtime import MpvRuntime
from substitute.infrastructure.video.mpv_video_player import MpvVideoPlayer
from substitute.presentation.canvas.output.video_playback_controller import (
    VideoPlaybackController,
    VideoViewportMode,
    VideoViewportState,
)
from substitute.presentation.canvas.output.video_viewport_interaction import (
    VideoViewportInteraction,
)
from substitute.presentation.canvas.output.video_opengl_surface import (
    VideoOpenGLSurface,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    floating_surface_text_color,
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
_FIT_VIDEO = app_text("Fit video")
_ACTUAL_SIZE_VIDEO = app_text("Show video at actual size")
_VIDEO_DIAGNOSTICS = app_text("Video playback diagnostics")
_SOFTWARE_FALLBACK = app_text(
    "Hardware video decoding was unavailable. Software decoding is active."
)
_RENDERER_FALLBACK = app_text(
    "The requested video renderer was unavailable. A safe fallback is active."
)
_UNKNOWN_DIAGNOSTIC = app_text("unknown")


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
        video_settings_provider: Callable[[], VideoPlaybackSettings] | None = None,
    ) -> None:
        """Create the render surface, playback controller, and control bar."""

        super().__init__(parent)
        self.setObjectName("outputVideoPlaybackPage")
        self._surface = VideoOpenGLSurface(self)
        self._status = QLabel(self)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._status.hide()
        self._play = QPushButton(self)
        self._previous_frame = QPushButton(self)
        self._next_frame = QPushButton(self)
        self._loop = QPushButton(self)
        self._loop.setCheckable(True)
        self._loop.setChecked(True)
        self._mute = QPushButton(self)
        self._mute.setCheckable(True)
        self._volume = QSlider(Qt.Orientation.Horizontal, self)
        self._volume.setRange(0, 100)
        self._volume.setValue(100)
        self._volume.setMinimumWidth(48)
        self._volume.setMaximumWidth(80)
        self._seek = QSlider(Qt.Orientation.Horizontal, self)
        self._seek.setRange(0, _SEEK_STEPS)
        self._time = QLabel("00:00 / 00:00", self)
        self._retry = QPushButton(self)
        self._retry.hide()
        self._fit = QPushButton(self)
        self._fit.setCheckable(True)
        self._actual_size = QPushButton(self)
        self._actual_size.setCheckable(True)
        self._diagnostics = QPushButton(self)
        self._control_bar = QFrame(self)
        self._control_bar.setObjectName("outputVideoPlaybackControls")
        self._pending_video: tuple[UUID, Path] | None = None
        self._player_generation = 0
        self._video_settings_provider = video_settings_provider or VideoPlaybackSettings
        factory = player_factory or self._create_bundled_player
        self.controller = VideoPlaybackController(
            player_factory=factory,
            player_preparer=self._surface.bind_player,
            parent=self,
        )
        self.controller.snapshotChanged.connect(self._apply_snapshot)
        self._viewport = VideoViewportInteraction(
            surface=self._surface,
            apply_viewport=self.controller.set_viewport,
        )
        self.controller.viewportChanged.connect(self._viewport.set_state)
        self.controller.viewportChanged.connect(self._apply_viewport_state)
        self._surface.renderingReady.connect(self._present_pending_video)
        self._surface.surfaceResized.connect(self._refresh_actual_size)
        self.destroyed.connect(lambda _object=None: self.controller.close())
        self._compose_layout()
        connect_theme_refresh(self, self._apply_theme)
        self._connect_controls()
        self._install_shortcuts()
        self.retranslate()
        self._apply_snapshot(self.controller.snapshot)

    @property
    def render_surface(self) -> QWidget:
        """Return the Qt-composited surface used by the bundled player."""

        return self._surface

    @property
    def viewport_state(self) -> VideoViewportState:
        """Return the current user-visible Fit, 1:1, or custom viewport state."""

        return self._viewport.state

    @property
    def control_bar(self) -> QWidget:
        """Return the playback bar for rendered qualification and hit-testing."""

        return self._control_bar

    def present_video(self, media_id: UUID, path: Path) -> None:
        """Present one validated local video and leave it paused."""

        if self._surface.rendering_ready:
            self.controller.activate(media_id, path)
            return
        self._pending_video = (media_id, path)
        self._surface.update()

    def place_control_bar(self, *, x: int, y: int, width: int, height: int) -> None:
        """Place playback controls beside Output navigation on its exact row."""

        self._control_bar.setGeometry(x, y, width, height)
        self._control_bar.raise_()
        self._control_bar.show()

    def set_output_active(self, active: bool) -> None:
        """Apply output visibility policy to playback and audio."""

        if active:
            snapshot = self.controller.snapshot
            media_id = snapshot.media_id
            if media_id is not None:
                self.controller.set_playing(False)
            return
        self._pending_video = None
        self.controller.deactivate()

    def close_player(self) -> None:
        """Release the native player before the Qt render surface is destroyed."""

        self._pending_video = None
        self._surface.release_player()
        self.controller.close()

    def prepare_for_window_transition(self) -> None:
        """Retire native window resources before the Output canvas is rehosted."""

        self._surface.release_player()
        self.controller.release_native_player_for_window_transition()

    def complete_window_transition(self) -> None:
        """Bind rendering to the context created by the new Output window."""

        self._surface.complete_window_transition()

    def retire_video(self, media_id: UUID) -> bool:
        """Unload one retired video before its temporary file is released."""

        if self._pending_video is not None and self._pending_video[0] == media_id:
            self._pending_video = None
        return self.controller.retire(media_id)

    @Slot()
    def _present_pending_video(self) -> None:
        """Activate queued media only after Qt owns a usable GL context."""

        pending = self._pending_video
        if pending is None:
            return
        self._pending_video = None
        self.controller.activate(*pending)

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
        fit_video = render_application_text(_FIT_VIDEO)
        actual_size_video = render_application_text(_ACTUAL_SIZE_VIDEO)
        video_diagnostics = render_application_text(_VIDEO_DIAGNOSTICS)
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
        set_fluent_tooltip_text(self._fit, fit_video)
        self._fit.setAccessibleName(fit_video)
        set_fluent_tooltip_text(self._actual_size, actual_size_video)
        self._actual_size.setAccessibleName(actual_size_video)
        set_fluent_tooltip_text(
            self._diagnostics,
            _diagnostics_text(self.controller.snapshot),
        )
        self._diagnostics.setAccessibleName(video_diagnostics)

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
        controls = QHBoxLayout(self._control_bar)
        controls.setContentsMargins(6, 4, 6, 4)
        controls.setSpacing(3)
        controls.addWidget(self._previous_frame)
        controls.addWidget(self._play)
        controls.addWidget(self._next_frame)
        controls.addWidget(self._seek, 1)
        controls.addWidget(self._time)
        controls.addWidget(self._loop)
        controls.addWidget(self._mute)
        controls.addWidget(self._volume)
        controls.addWidget(self._fit)
        controls.addWidget(self._actual_size)
        controls.addWidget(self._diagnostics)
        controls.addWidget(self._retry)
        self._control_bar.setGeometry(8, 8, 1, 36)
        self._apply_theme()

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
        self._fit.clicked.connect(self.controller.reset_viewport)
        self._actual_size.clicked.connect(self._set_actual_size)

    def _install_shortcuts(self) -> None:
        """Install keyboard equivalents scoped to the visible playback page."""

        for sequence, callback in (
            ("Space", self._toggle_playback),
            (",", self.controller.step_previous_frame),
            (".", self.controller.step_next_frame),
            ("L", lambda: self._loop.setChecked(not self._loop.isChecked())),
            ("0", self.controller.reset_viewport),
            ("1", self._set_actual_size),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    def _create_bundled_player(
        self,
        callback: Callable[[VideoPlaybackEvent], None],
    ) -> VideoPlayerPort:
        """Create the project-owned player against this page's native surface."""

        self._player_generation += 1
        return MpvVideoPlayer(
            runtime=MpvRuntime.bundled(),
            player_generation=self._player_generation,
            event_callback=callback,
            render_api=True,
            settings=self._video_settings_provider(),
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
        self._play.setIcon(
            (
                AppIcon.PLAY_20_REGULAR if value.paused else AppIcon.PAUSE_20_REGULAR
            ).icon()
        )
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
            self._fit,
            self._actual_size,
        ):
            control.setEnabled(ready)
        self._loop.blockSignals(True)
        self._loop.setChecked(value.loop_enabled)
        self._loop.blockSignals(False)
        self._mute.blockSignals(True)
        self._mute.setChecked(value.user_muted)
        self._mute.setIcon(
            (
                AppIcon.SPEAKER_MUTE_20_REGULAR
                if value.user_muted
                else AppIcon.SPEAKER_2_20_REGULAR
            ).icon()
        )
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
        fallback = _fallback_text(value.diagnostics.fallback)
        self._status.setText(error or fallback)
        self._status.setVisible(bool(error or fallback))
        self._retry.setVisible(bool(error))
        set_fluent_tooltip_text(self._diagnostics, _diagnostics_text(value))
        self._control_bar.raise_()

    @Slot(object)
    def _apply_viewport_state(self, value: object) -> None:
        """Expose Fit and 1:1 as explicit mutually exclusive view states."""

        if not isinstance(value, VideoViewportState):
            return
        self._fit.blockSignals(True)
        self._actual_size.blockSignals(True)
        self._fit.setChecked(value.mode is VideoViewportMode.FIT)
        self._actual_size.setChecked(value.mode is VideoViewportMode.ACTUAL_SIZE)
        self._fit.blockSignals(False)
        self._actual_size.blockSignals(False)

    @Slot()
    def _set_actual_size(self) -> None:
        """Project source pixels at physical display pixel size."""

        self.controller.set_actual_size_viewport(
            surface_width=self._surface.width(),
            surface_height=self._surface.height(),
            device_pixel_ratio=self._surface.devicePixelRatioF(),
        )

    @Slot()
    def _refresh_actual_size(self) -> None:
        """Preserve 1:1 scale when the available video surface changes."""

        if self._viewport.state.mode is VideoViewportMode.ACTUAL_SIZE:
            self._set_actual_size()

    def _apply_theme(self) -> None:
        """Match Output navigation material and refresh themed Fluent icons."""

        text = floating_surface_text_color()
        accent = QColor(themeColor())
        hover_channel = 255 if text.lightness() > 127 else 0
        text_rgba = _rgba(text)
        disabled_rgba = _rgba(QColor(text.red(), text.green(), text.blue(), 80))
        hover_rgba = f"rgba({hover_channel}, {hover_channel}, {hover_channel}, 24)"
        checked_rgba = _rgba(QColor(accent.red(), accent.green(), accent.blue(), 56))
        self._control_bar.setStyleSheet(
            floating_canvas_surface_stylesheet("QFrame#outputVideoPlaybackControls")
            + "QFrame#outputVideoPlaybackControls QPushButton {"
            " min-width: 26px; min-height: 26px; max-height: 26px; padding: 0px;"
            f" color: {text_rgba}; background: transparent; border: none;"
            " border-radius: 5px;"
            "}"
            "QFrame#outputVideoPlaybackControls QPushButton:hover {"
            f" background: {hover_rgba};"
            "}"
            "QFrame#outputVideoPlaybackControls QPushButton:checked {"
            f" background: {checked_rgba};"
            "}"
            "QFrame#outputVideoPlaybackControls QPushButton:disabled {"
            f" color: {disabled_rgba};"
            "}"
            "QFrame#outputVideoPlaybackControls QLabel {"
            f" color: {text_rgba}; background: transparent;"
            "}"
            "QFrame#outputVideoPlaybackControls QSlider { background: transparent; }"
        )
        for button, icon in (
            (self._previous_frame, AppIcon.PREVIOUS_20_REGULAR),
            (self._next_frame, AppIcon.NEXT_20_REGULAR),
            (self._loop, AppIcon.ARROW_REPEAT_ALL_20_REGULAR),
            (self._fit, AppIcon.ZOOM_FIT_20_REGULAR),
            (self._actual_size, AppIcon.RATIO_ONE_TO_ONE_20_REGULAR),
            (self._diagnostics, AppIcon.INFO_20_REGULAR),
        ):
            button.setIcon(icon.icon())
            button.setIconSize(QSize(18, 18))
        self._play.setIconSize(QSize(18, 18))
        self._mute.setIconSize(QSize(18, 18))
        self._apply_snapshot(self.controller.snapshot)


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


def _rgba(color: QColor) -> str:
    """Return a QSS RGBA token for one concrete theme color."""

    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def _format_time(value: float | None) -> str:
    """Format seconds as stable elapsed playback text."""

    seconds = max(0, int(value or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _fallback_text(fallback: VideoPlaybackFallback | None) -> str:
    """Return localized visibility text for one active native fallback."""

    if fallback is VideoPlaybackFallback.SOFTWARE_DECODING:
        return render_application_text(_SOFTWARE_FALLBACK)
    if fallback is VideoPlaybackFallback.RENDERER:
        return render_application_text(_RENDERER_FALLBACK)
    return ""


def _diagnostics_text(snapshot: VideoPlaybackSnapshot) -> str:
    """Render sanitized requested and observed playback facts."""

    diagnostics = snapshot.diagnostics
    unknown = render_application_text(_UNKNOWN_DIAGNOSTIC)
    return render_application_text(
        app_text(
            "Renderer: requested %1, active %2; GPU: %3/%4; decoder: %5; codec: %6; pixel format: %7",
            diagnostics.requested_renderer.value,
            diagnostics.actual_video_output or unknown,
            diagnostics.gpu_api or unknown,
            diagnostics.gpu_context or unknown,
            diagnostics.hardware_decoder or unknown,
            diagnostics.codec or unknown,
            diagnostics.pixel_format or unknown,
        )
    )


__all__ = ["VideoPlaybackPage"]
