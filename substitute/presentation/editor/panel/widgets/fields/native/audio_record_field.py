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

"""Provide a Fluent audio-record field for native Comfy AUDIO_RECORD values."""

from __future__ import annotations

from pathlib import Path
import tempfile
from uuid import uuid4

from PySide6.QtCore import QSignalBlocker, QUrl, Signal
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
)
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    FluentIcon,
    ToolButton,
)

from substitute.presentation.widgets.tooltips import bind_fluent_tooltip


class AudioRecordField(QWidget):
    """Record or choose an audio file through compact Fluent card controls."""

    valueChanged = Signal(object)

    def __init__(self, value: object, parent: QWidget | None = None) -> None:
        """Initialize lazy recording resources and the current file summary."""

        super().__init__(parent)
        self._value: str | None = value if isinstance(value, str) and value else None
        self._recording_target: Path | None = None
        self._capture_session: QMediaCaptureSession | None = None
        self._audio_input: QAudioInput | None = None
        self._recorder: QMediaRecorder | None = None

        self.record_button = ToolButton(FluentIcon.MICROPHONE, self)
        self.choose_button = ToolButton(FluentIcon.FOLDER, self)
        self.status_label = CaptionLabel(self)
        self.status_label.setMinimumWidth(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.record_button)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.status_label, 1)

        bind_fluent_tooltip(
            self.record_button,
            self.tr("Record audio from the default microphone"),
            self.record_button,
        )
        bind_fluent_tooltip(
            self.choose_button,
            self.tr("Choose an existing audio file"),
            self.choose_button,
        )
        self.record_button.clicked.connect(self._toggle_recording)
        self.choose_button.clicked.connect(self._choose_audio_file)
        self._refresh_status()

    def value(self) -> str | None:
        """Return the selected or recorded local audio path."""

        return self._value

    def setValue(self, value: object) -> None:  # noqa: N802
        """Apply an audio path without emitting an application state change."""

        blocker = QSignalBlocker(self)
        self._value = value if isinstance(value, str) and value else None
        self._refresh_status()
        del blocker

    def _toggle_recording(self) -> None:
        """Start or stop a lazy Qt Multimedia recording session."""

        if (
            self._recorder is not None
            and self._recorder.recorderState()
            == QMediaRecorder.RecorderState.RecordingState
        ):
            self._recorder.stop()
            return
        self._start_recording()

    def _start_recording(self) -> None:
        """Record WAV audio without failing the card when no device is available."""

        if not QMediaDevices.audioInputs():
            self.status_label.setText(self.tr("No microphone"))
            self.setProperty("audio_record_availability", "unavailable")
            return
        self._ensure_recorder()
        if self._recorder is None:
            return
        recordings_dir = (
            Path(tempfile.gettempdir()) / "SugarSubstitute" / "audio-recordings"
        )
        recordings_dir.mkdir(parents=True, exist_ok=True)
        self._recording_target = recordings_dir / f"recording-{uuid4().hex}.wav"
        self._recorder.setOutputLocation(
            QUrl.fromLocalFile(str(self._recording_target))
        )
        self._recorder.record()

    def _ensure_recorder(self) -> None:
        """Create Qt Multimedia objects only after the user requests recording."""

        if self._recorder is not None:
            return
        self._capture_session = QMediaCaptureSession(self)
        self._audio_input = QAudioInput(self)
        self._recorder = QMediaRecorder(self)
        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.Wave)
        media_format.setAudioCodec(QMediaFormat.AudioCodec.Wave)
        self._recorder.setMediaFormat(media_format)
        self._capture_session.setAudioInput(self._audio_input)
        self._capture_session.setRecorder(self._recorder)
        self._recorder.recorderStateChanged.connect(self._recording_state_changed)
        self._recorder.errorOccurred.connect(self._recording_failed)

    def _recording_state_changed(self, state: QMediaRecorder.RecorderState) -> None:
        """Update Fluent controls and publish a completed recording path."""

        is_recording = state == QMediaRecorder.RecorderState.RecordingState
        self.record_button.setIcon(
            FluentIcon.PAUSE_BOLD if is_recording else FluentIcon.MICROPHONE
        )
        self.choose_button.setEnabled(not is_recording)
        if is_recording:
            self.status_label.setText(self.tr("Recording…"))
            return
        target = self._recording_target
        if target is not None and target.is_file() and target.stat().st_size > 0:
            self._value = str(target)
            self._refresh_status()
            self.valueChanged.emit(self._value)

    def _recording_failed(
        self,
        _error: QMediaRecorder.Error,
        message: str,
    ) -> None:
        """Expose recorder failure without raising through card construction."""

        self.record_button.setIcon(FluentIcon.MICROPHONE)
        self.choose_button.setEnabled(True)
        self.status_label.setText(message or self.tr("Recording failed"))
        self.setProperty("audio_record_error", message)

    def _choose_audio_file(self) -> None:
        """Choose audio through Qt's native dialog; QFluent has no file picker."""

        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose audio"),
            "",
            self.tr("Audio files (*.wav *.mp3 *.flac *.m4a *.ogg);;All files (*)"),
        )
        if not selected:
            return
        self._value = selected
        self._refresh_status()
        self.valueChanged.emit(selected)

    def _refresh_status(self) -> None:
        """Display a concise filename or an honest empty state."""

        self.status_label.setText(
            Path(self._value).name if self._value else self.tr("No audio")
        )
        self.status_label.setToolTip(self._value or "")


__all__ = ["AudioRecordField"]
