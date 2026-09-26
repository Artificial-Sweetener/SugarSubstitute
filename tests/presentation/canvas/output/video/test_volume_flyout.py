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

"""Verify compact video volume controls and QFluent flyout behavior."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QPushButton, QSlider, QVBoxLayout, QWidget

from substitute.presentation.canvas.output.video_playback_page import VideoPlaybackPage
from substitute.presentation.canvas.output.video_volume_flyout import (
    VideoVolumeFlyout,
    VideoVolumeFlyoutView,
    video_volume_icon,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_video_control_bar_keeps_volume_slider_in_a_lazy_flyout() -> None:
    """The persistent chrome should contain one seek slider and no info action."""

    ensure_qt_application()
    page = VideoPlaybackPage()
    try:
        sliders = page.control_bar.findChildren(QSlider)
        assert [slider.accessibleName() for slider in sliders] == ["Video position"]
        assert not any(
            button.accessibleName() == "Video playback diagnostics"
            for button in page.control_bar.findChildren(QPushButton)
        )
        assert any(
            button.accessibleName() == "Video volume"
            for button in page.control_bar.findChildren(QPushButton)
        )
        assert page.findChild(VideoVolumeFlyoutView) is None
    finally:
        page.close_player()
        destroy_qt_object(page)


def test_volume_button_opens_synced_flyout_and_routes_audio_changes() -> None:
    """QFluent's media flyout should own slider space, mute, and live values."""

    app = ensure_qt_application()
    host = QWidget()
    layout = QVBoxLayout(host)
    anchor = QPushButton(host)
    layout.addStretch()
    layout.addWidget(anchor)
    host.resize(320, 360)
    host.show()
    app.processEvents()
    volumes: list[int] = []
    mute_choices: list[bool] = []
    flyout = VideoVolumeFlyout(
        anchor=anchor,
        set_volume=volumes.append,
        set_muted=mute_choices.append,
        mute_text="Mute video",
        volume_text="Video volume",
        parent=host,
    )
    try:
        flyout.synchronize(volume=37, muted=True)
        anchor.click()
        app.processEvents()

        view = host.findChild(VideoVolumeFlyoutView)
        assert view is not None
        assert flyout.is_visible()
        assert not view.isWindow()
        assert view.window() is host
        assert view.size() == QSize(56, 208)
        assert view.muteButton.iconSize() == QSize(18, 18)
        assert view.volumeSlider.value() == 37
        assert view.volumeSlider.orientation() == Qt.Orientation.Vertical
        assert view.height() > view.width()
        assert view.volumeSlider.mapTo(view, QPoint()).y() < view.muteButton.y()
        assert view.volumeSlider.accessibleName() == "Video volume"
        assert view.volumeSlider.toolTip() == ""
        assert view.muteButton.accessibleName() == "Mute video"
        assert view.muteButton.toolTip() == "Mute video"
        assert view.muteButton.size() == anchor.size()
        assert view.muteButton.mapToGlobal(QPoint()) == anchor.mapToGlobal(QPoint())
        assert view.muteButton.mapToGlobal(view.muteButton.rect().bottomRight()) == (
            anchor.mapToGlobal(anchor.rect().bottomRight())
        )
        anchor_center_x = anchor.mapToGlobal(anchor.rect().center()).x()
        assert (
            view.volumeSlider.mapToGlobal(view.volumeSlider.rect().center()).x()
            == anchor_center_x
        )
        assert (
            view.volumeLabel.mapToGlobal(view.volumeLabel.rect().center()).x()
            == anchor_center_x
        )
        assert (
            view.muteButton.mapToGlobal(view.muteButton.rect().center()).x()
            == anchor_center_x
        )
        assert host.isActiveWindow()

        flyout.synchronize(volume=40, muted=True)
        app.processEvents()
        groove_length = view.volumeSlider.height() - view.volumeSlider.handle.height()
        assert abs(view.volumeSlider.handle.y() - round(0.6 * groove_length)) <= 1
        slider_image = view.volumeSlider.grab().toImage()
        rail_x = view.volumeSlider.width() // 2
        assert slider_image.pixelColor(rail_x, 48) != slider_image.pixelColor(
            rail_x, 116
        )

        view.volumeSlider.setValue(64)
        view.muteButton.click()
        app.processEvents()
        assert volumes == [64]
        assert mute_choices == [False]

        anchor.click()
        app.processEvents()
        assert not flyout.is_visible()
    finally:
        flyout.close()
        host.close()
        destroy_qt_object(host)


def test_volume_icon_tracks_output_level_and_explicit_mute() -> None:
    """Speaker waves should communicate zero, low, high, and muted output."""

    assert video_volume_icon(volume=0, muted=False) is AppIcon.SPEAKER_0_20_REGULAR
    assert video_volume_icon(volume=1, muted=False) is AppIcon.SPEAKER_1_20_REGULAR
    assert video_volume_icon(volume=49, muted=False) is AppIcon.SPEAKER_1_20_REGULAR
    assert video_volume_icon(volume=50, muted=False) is AppIcon.SPEAKER_2_20_REGULAR
    assert video_volume_icon(volume=100, muted=False) is AppIcon.SPEAKER_2_20_REGULAR
    assert video_volume_icon(volume=100, muted=True) is AppIcon.SPEAKER_MUTE_20_REGULAR
