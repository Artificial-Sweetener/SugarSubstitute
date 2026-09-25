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

"""Present video volume through QFluent's compact media flyout."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QObject, QPoint, QRectF, Qt, Slot
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QPushButton, QWidget
from qfluentwidgets.common.color import (  # type: ignore[import-untyped]
    autoFallbackThemeColor,
)
from qfluentwidgets.components.widgets.flyout import (  # type: ignore[import-untyped]
    Flyout,
    FlyoutAnimationType,
)
from qfluentwidgets.multimedia.media_play_bar import (  # type: ignore[import-untyped]
    VolumeView,
)
from qfluentwidgets.components.widgets.slider import (  # type: ignore[import-untyped]
    Slider,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from substitute.presentation.resources.fluent_app_icon import AppIcon


class _VerticalVolumeSlider(Slider):  # type: ignore[misc]
    """Keep greater volume at the top of QFluent's vertical slider."""

    def _adjustHandlePos(self) -> None:  # noqa: N802
        """Position the custom QFluent handle with maximum at the top."""

        total = max(self.maximum() - self.minimum(), 1)
        delta = int((self.maximum() - self.value()) / total * self.grooveLength)
        self.handle.move(0, delta)

    def _posToValue(self, pos: QPoint) -> int:  # noqa: N802
        """Convert top-origin pointer geometry to increasing volume."""

        handle_radius = self.handle.width() / 2
        groove = max(self.grooveLength, 1)
        fraction = (pos.y() - handle_radius) / groove
        return int(round(self.maximum() - fraction * (self.maximum() - self.minimum())))

    def _drawVerticalGroove(self, painter: QPainter) -> None:  # noqa: N802
        """Fill upward from the bottom so the rail agrees with the handle."""

        height = self.height()
        handle_radius = self.handle.width() / 2
        groove_length = height - 2 * handle_radius
        painter.drawRoundedRect(
            QRectF(handle_radius - 2, handle_radius, 4, groove_length),
            2,
            2,
        )
        value_range = self.maximum() - self.minimum()
        if value_range == 0:
            return
        filled_length = (self.value() - self.minimum()) / value_range * groove_length
        fill_top = height - handle_radius - filled_length
        painter.setBrush(
            autoFallbackThemeColor(self.lightGrooveColor, self.darkGrooveColor)
        )
        painter.drawRoundedRect(
            QRectF(handle_radius - 2, fill_top, 4, filled_length),
            2,
            2,
        )


class VideoVolumeFlyoutView(VolumeView):  # type: ignore[misc]
    """Adapt QFluent's standard volume surface to localized app semantics."""

    volumeSlider: _VerticalVolumeSlider

    def __init__(
        self,
        *,
        mute_text: str,
        volume_text: str,
        parent: QWidget | None = None,
    ) -> None:
        """Create the standard slider, value label, and nested mute action."""

        super().__init__(parent)
        self._mute_text = mute_text
        horizontal_slider = cast(QWidget, getattr(self, "volumeSlider"))
        horizontal_slider.setParent(None)
        horizontal_slider.deleteLater()
        self.volumeSlider = _VerticalVolumeSlider(Qt.Orientation.Vertical, self)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setFixedSize(22, 144)
        self.setFixedSize(64, 224)
        self.volumeSlider.move(21, 34)
        self.muteButton.move(17, 187)
        self.setObjectName("outputVideoVolumeFlyout")
        self.muteButton.setObjectName("outputVideoFlyoutMuteButton")
        self.volumeSlider.setObjectName("outputVideoFlyoutVolumeSlider")
        self.retranslate(mute_text=mute_text, volume_text=volume_text)

    def retranslate(self, *, mute_text: str, volume_text: str) -> None:
        """Refresh accessible names and tooltips without rebuilding the flyout."""

        self._mute_text = mute_text
        set_fluent_tooltip_text(self.muteButton, mute_text)
        self.muteButton.setAccessibleName(mute_text)
        set_fluent_tooltip_text(self.volumeSlider, volume_text)
        self.volumeSlider.setAccessibleName(volume_text)

    def synchronize(self, *, volume: int, muted: bool) -> None:
        """Project player state without feeding programmatic values back."""

        was_blocked = self.volumeSlider.blockSignals(True)
        try:
            self.setVolume(volume)
        finally:
            self.volumeSlider.blockSignals(was_blocked)
        self.setMuted(muted)
        set_fluent_tooltip_text(self.muteButton, self._mute_text)
        self.muteButton.setIcon(
            (
                AppIcon.SPEAKER_MUTE_20_REGULAR
                if muted
                else AppIcon.SPEAKER_2_20_REGULAR
            ).icon()
        )

    def setVolume(self, volume: int) -> None:  # noqa: N802
        """Place the current value above the vertical slider."""

        bounded_volume = min(max(int(volume), 0), 100)
        self.volumeSlider.setValue(bounded_volume)
        self.volumeSlider._adjustHandlePos()
        self.volumeLabel.setNum(bounded_volume)
        self.volumeLabel.adjustSize()
        self.volumeLabel.move((self.width() - self.volumeLabel.width()) // 2, 8)


class VideoVolumeFlyout(QObject):
    """Own one window-local volume flyout anchored to the compact audio button."""

    def __init__(
        self,
        *,
        anchor: QPushButton,
        set_volume: Callable[[int], None],
        set_muted: Callable[[bool], None],
        mute_text: str,
        volume_text: str,
        parent: QObject | None = None,
    ) -> None:
        """Bind player commands and localized copy to a lazy QFluent flyout."""

        super().__init__(parent)
        self._anchor = anchor
        self._set_volume = set_volume
        self._set_muted = set_muted
        self._mute_text = mute_text
        self._volume_text = volume_text
        self._volume = 100
        self._muted = False
        self._flyout: Flyout | None = None
        self._view: VideoVolumeFlyoutView | None = None
        self._anchor.clicked.connect(self.toggle)

    def synchronize(self, *, volume: int, muted: bool) -> None:
        """Retain current audio state and refresh an open flyout in place."""

        self._volume = min(max(int(volume), 0), 100)
        self._muted = bool(muted)
        if self._view is not None:
            self._view.synchronize(volume=self._volume, muted=self._muted)

    def retranslate(self, *, mute_text: str, volume_text: str) -> None:
        """Refresh copy retained for the next flyout and any open view."""

        self._mute_text = mute_text
        self._volume_text = volume_text
        if self._view is not None:
            self._view.retranslate(mute_text=mute_text, volume_text=volume_text)

    @Slot()
    def toggle(self) -> None:
        """Open the volume surface above the button, or close the visible one."""

        if self.is_visible():
            self.close()
            return
        view = VideoVolumeFlyoutView(
            mute_text=self._mute_text,
            volume_text=self._volume_text,
            parent=self._anchor,
        )
        view.synchronize(volume=self._volume, muted=self._muted)
        view.volumeSlider.valueChanged.connect(self._handle_volume_changed)
        view.muteButton.clicked.connect(self._handle_mute_clicked)
        flyout = cast(
            Flyout,
            Flyout.make(
                view,
                self._anchor,
                self._anchor.window(),
                FlyoutAnimationType.PULL_UP,
                True,
            ),
        )
        self._view = view
        self._flyout = flyout
        flyout.closed.connect(self._handle_closed)

    def close(self) -> None:
        """Close and forget the current window-local flyout."""

        flyout = self._flyout
        self._flyout = None
        self._view = None
        if flyout is not None:
            flyout.close()

    def is_visible(self) -> bool:
        """Return whether the current volume flyout is visible."""

        return self._flyout is not None and self._flyout.isVisible()

    @Slot(int)
    def _handle_volume_changed(self, volume: int) -> None:
        """Update the numeric label immediately and forward user volume intent."""

        self._volume = min(max(int(volume), 0), 100)
        if self._view is not None:
            self._view.synchronize(volume=self._volume, muted=self._muted)
        self._set_volume(self._volume)

    @Slot()
    def _handle_mute_clicked(self) -> None:
        """Toggle mute inside the flyout while keeping the anchor compact."""

        self._muted = not self._muted
        if self._view is not None:
            self._view.synchronize(volume=self._volume, muted=self._muted)
        self._set_muted(self._muted)

    @Slot()
    def _handle_closed(self) -> None:
        """Drop references after QFluent completes outside-click dismissal."""

        self._flyout = None
        self._view = None


__all__ = ["VideoVolumeFlyout", "VideoVolumeFlyoutView"]
