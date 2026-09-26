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

"""Qualify compact QFluent volume controls in the native video surface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QSlider, QWidget

from substitute.presentation.canvas.output.video_playback_page import VideoPlaybackPage
from substitute.presentation.canvas.output.video_volume_flyout import (
    VideoVolumeFlyoutView,
    video_volume_icon,
)
from tools.video_output_qualification_support import (
    capture,
    find_button,
    native_click,
    native_click_vertical_fraction,
    pump_events,
    wait_until,
)


def qualify_volume_flyout(
    *,
    application: QApplication,
    root: QWidget,
    page: VideoPlaybackPage,
    evidence_dir: Path,
) -> dict[str, object]:
    """Prove slider space and diagnostics are absent until volume is requested."""

    persistent_slider_names = tuple(
        slider.accessibleName() for slider in page.control_bar.findChildren(QSlider)
    )
    if persistent_slider_names != ("Video position",):
        raise RuntimeError("Video volume still occupies persistent control-bar space.")
    if any(
        button.accessibleName() == "Video playback diagnostics"
        for button in page.control_bar.findChildren(QPushButton)
    ):
        raise RuntimeError("The removed video diagnostics button remains visible.")

    volume_button = find_button(page, "Video volume")
    native_click(root, volume_button, application)
    wait_until(
        application,
        lambda: _visible_volume_view(root) is not None,
        label="video volume flyout",
    )
    view = _visible_volume_view(root)
    if view is None:
        raise RuntimeError("Video volume flyout disappeared before interaction.")
    pump_events(application, 0.25)
    flyout_window = view.window()
    if view.isWindow() or flyout_window is not root.window():
        raise RuntimeError("Video volume opened as a separate window.")
    if QApplication.activeWindow() is not root.window():
        raise RuntimeError("Opening video volume deactivated the application window.")
    if view.size() != QSize(56, 208):
        raise RuntimeError(f"Video volume overlay is not compact: size={view.size()}.")
    if view.muteButton.iconSize() != volume_button.iconSize():
        raise RuntimeError(
            "Stacked volume icons are not rendered at the same size: "
            f"overlay={view.muteButton.iconSize()}, bar={volume_button.iconSize()}."
        )
    if not _icons_match(view.muteButton.icon(), volume_button.icon()):
        raise RuntimeError("Stacked volume icons do not render the same pixels.")
    anchor_rect = QRect(volume_button.mapToGlobal(QPoint()), volume_button.size())
    nested_button_rect = QRect(
        view.muteButton.mapToGlobal(QPoint()),
        view.muteButton.size(),
    )
    if nested_button_rect != anchor_rect:
        raise RuntimeError(
            "The flyout volume button does not exactly cover its bar button: "
            f"overlay={nested_button_rect}, bar={anchor_rect}."
        )
    overlay_size = [view.width(), view.height()]
    if view.volumeSlider.orientation() != Qt.Orientation.Vertical:
        raise RuntimeError("Video volume flyout slider is not vertical.")
    if view.volumeSlider.toolTip():
        raise RuntimeError("Video volume slider still exposes a redundant tooltip.")
    anchor_center_x = volume_button.mapToGlobal(volume_button.rect().center()).x()
    aligned_centers = {
        "slider": view.volumeSlider.mapToGlobal(view.volumeSlider.rect().center()).x(),
        "value": view.volumeLabel.mapToGlobal(view.volumeLabel.rect().center()).x(),
        "mute": view.muteButton.mapToGlobal(view.muteButton.rect().center()).x(),
    }
    if any(center != anchor_center_x for center in aligned_centers.values()):
        raise RuntimeError(
            "Video volume stack is not aligned to its button: "
            f"anchor={anchor_center_x}, controls={aligned_centers}."
        )
    native_click_vertical_fraction(
        flyout_window,
        view.volumeSlider,
        0.6,
        application,
    )
    try:
        wait_until(
            application,
            lambda: 38 <= page.controller.snapshot.volume <= 46,
            label="flyout volume change",
        )
    except TimeoutError as error:
        raise RuntimeError(
            "Vertical flyout did not route the selected volume: "
            f"volume={page.controller.snapshot.volume}."
        ) from error
    selected_volume = page.controller.snapshot.volume
    if not _icons_match(
        volume_button.icon(),
        video_volume_icon(volume=selected_volume, muted=False).icon(),
    ):
        raise RuntimeError("Video volume button did not switch to its low-volume icon.")
    _assert_slider_geometry(view, selected_volume)
    capture(root, evidence_dir / "video-volume-flyout.png")
    native_click(flyout_window, view.muteButton, application)
    wait_until(
        application,
        lambda: page.controller.snapshot.user_muted,
        label="flyout mute change",
    )
    if not _icons_match(
        volume_button.icon(),
        video_volume_icon(volume=selected_volume, muted=True).icon(),
    ):
        raise RuntimeError("Video volume button did not switch to its muted icon.")
    native_click(flyout_window, page.render_surface, application)
    wait_until(
        application,
        lambda: _visible_volume_view(root) is None,
        label="closed video volume flyout",
    )
    return {
        "persistent_slider_names": persistent_slider_names,
        "diagnostics_button_removed": True,
        "flyout_body_above_button": True,
        "button_rect_match": True,
        "in_window_overlay": True,
        "window_activation_preserved": True,
        "icon_pixels_match": True,
        "overlay_size": overlay_size,
        "stack_center_x": anchor_center_x,
        "slider_tooltip_removed": True,
        "responsive_volume_icons": True,
        "slider_orientation": "vertical",
        "selected_volume": selected_volume,
        "selected_muted": True,
    }


def _assert_slider_geometry(view: VideoVolumeFlyoutView, volume: int) -> None:
    """Require the native knob and bottom-up fill to agree at partial volume."""

    slider = view.volumeSlider
    groove_length = slider.height() - slider.handle.height()
    expected_handle_top = round((100 - volume) / 100 * groove_length)
    if abs(slider.handle.y() - expected_handle_top) > 2:
        raise RuntimeError(
            "Vertical volume knob does not represent the selected value: "
            f"actual={slider.handle.y()}, expected={expected_handle_top}."
        )
    image = slider.grab().toImage()
    rail_x = slider.width() // 2
    unfilled_y = max(slider.handle.height() // 2, slider.handle.y() - 20)
    filled_y = min(
        slider.height() - slider.handle.height() // 2 - 1,
        slider.handle.geometry().center().y() + 20,
    )
    if image.pixelColor(rail_x, unfilled_y) == image.pixelColor(rail_x, filled_y):
        raise RuntimeError(
            "Vertical volume rail does not visibly fill from the bottom."
        )


def _icons_match(first: QIcon, second: QIcon) -> bool:
    """Return whether two themed icons paint the same native pixels."""

    size = QSize(20, 20)
    return first.pixmap(size).toImage() == second.pixmap(size).toImage()


def _visible_volume_view(root: QWidget) -> VideoVolumeFlyoutView | None:
    """Return the visible QFluent volume surface owned by the current window."""

    return next(
        (
            view
            for view in root.findChildren(VideoVolumeFlyoutView)
            if view.window().isVisible()
        ),
        None,
    )


__all__ = ["qualify_volume_flyout"]
