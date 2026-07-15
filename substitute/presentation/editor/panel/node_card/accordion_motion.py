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

"""Coordinate Fluent-style accordion motion for editor node cards."""

from __future__ import annotations

from collections.abc import Callable
from PySide6.QtCore import (
    QObject,
    Property,
    QPropertyAnimation,
    QRectF,
    QSize,
    QTimer,
)
from PySide6.QtGui import QPainter, QResizeEvent
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from .body_layout import (
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
    prepare_card_body_collapse,
    prepare_card_body_expand,
    resolve_card_body_expanded_height,
)
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_COLLAPSE_EASING_CURVE,
    ACCORDION_EXPAND_DURATION_MS,
    ACCORDION_EXPAND_EASING_CURVE,
    is_reduced_motion_enabled,
    restart_property_animation,
)

_EXPANDED_CHEVRON_ROTATION = 180.0
_COLLAPSED_CHEVRON_ROTATION = 0.0
_DIVIDER_SHOW_PROGRESS = 0.72
_UNBOUNDED_HEIGHT_THRESHOLD = 1_000_000


def _paint_rotated_icon(
    painter: QPainter,
    icon_enum: FIF,
    rect: QRectF,
    angle: float,
) -> None:
    """Paint one Fluent icon rotated in logical widget coordinates."""

    painter.save()
    try:
        center = rect.center()
        painter.translate(center)
        painter.rotate(angle)
        painter.translate(-center)
        icon_enum.render(painter, rect)
    finally:
        painter.restore()


class AccordionChevronWidget(QWidget):
    """Render a small rotatable chevron used by animated accordion headers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize chevron geometry and default expanded-state rotation."""

        super().__init__(parent)
        self._rotation = _EXPANDED_CHEVRON_ROTATION
        self.setFixedSize(14, 14)

    def _get_rotation(self) -> float:
        """Return the current chevron rotation in degrees."""

        return self._rotation

    def rotation_value(self) -> float:
        """Expose the current rotation for Python callers and tests."""

        return self._rotation

    def set_rotation(self, angle: float) -> None:
        """Apply a new chevron rotation and schedule repaint."""

        self._rotation = angle
        self.update()

    def paintEvent(self, event: object) -> None:
        """Draw the rotated arrow icon centered within the widget bounds."""

        del event
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        _paint_rotated_icon(
            painter,
            FIF.ARROW_DOWN,
            QRectF(self.rect()),
            self._rotation,
        )

    rotation = Property(float, _get_rotation, set_rotation)


class AccordionContentClip(QWidget):
    """Clip one moving accordion content surface and expose its vertical offset."""

    def __init__(
        self,
        parent: QWidget,
        *,
        content_surface_factory: Callable[[QWidget], QWidget] | None = None,
    ) -> None:
        """Create the clipped host used for WinUI-style reveal motion."""

        super().__init__(parent)
        self._content_offset_y = 0
        self._content_height = 0
        self._content_overlap_y = 0
        self._content_widget = (
            content_surface_factory(self)
            if content_surface_factory is not None
            else QWidget(self)
        )
        self._content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

    def content_widget(self) -> QWidget:
        """Return the child surface that owns the accordion content layout."""

        return self._content_widget

    def content_offset_y(self) -> int:
        """Return the current vertical content offset in viewport coordinates."""

        return self._content_offset_y

    def set_content_offset_y(self, offset_y: int) -> None:
        """Move the clipped content surface to the supplied vertical offset."""

        self._content_offset_y = int(offset_y)
        self._sync_content_geometry()

    def set_content_height(self, content_height: int) -> None:
        """Store the natural content height used by reveal offset calculations."""

        self._content_height = self._bounded_content_height(content_height)
        self._sync_content_geometry()
        self.updateGeometry()

    def content_height(self) -> int:
        """Return the stored natural content height for the inner content surface."""

        return self._content_height

    def content_overlap_y(self) -> int:
        """Return the upward content overlap used to hide header seams."""

        return self._content_overlap_y

    def set_content_overlap_y(self, overlap_y: int) -> None:
        """Apply a WinUI-style upward overlap for the moving content surface."""

        self._content_overlap_y = max(0, int(overlap_y))
        self._sync_content_geometry()

    def sizeHint(self) -> QSize:
        """Return the content surface hint while layout height is externally capped."""

        content_hint = self._content_widget.sizeHint()
        return QSize(content_hint.width(), max(self._content_height, 0))

    def minimumSizeHint(self) -> QSize:
        """Return a zero-height hint so collapsed viewports can leave layout cleanly."""

        content_hint = self._content_widget.minimumSizeHint()
        return QSize(content_hint.width(), 0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the inner content width synchronized with the clipped viewport."""

        super().resizeEvent(event)
        self._sync_content_geometry()

    def _bounded_content_height(self, content_height: int) -> int:
        """Return a usable content height without treating unbounded max as natural."""

        if content_height >= _UNBOUNDED_HEIGHT_THRESHOLD:
            return max(0, self._content_widget.sizeHint().height())
        return max(0, int(content_height))

    def _sync_content_geometry(self) -> None:
        """Apply the current offset and natural height to the content surface."""

        height = max(self._content_height, self._content_widget.sizeHint().height())
        self._content_widget.setGeometry(
            0,
            self._content_offset_y - self._content_overlap_y,
            max(0, self.width()),
            max(0, height + self._content_overlap_y),
        )

    contentOffsetY = Property(int, content_offset_y, set_content_offset_y)


def set_accordion_surface_attachment(
    *,
    card_title: QWidget,
    content_body: QWidget,
    attached: bool,
) -> None:
    """Apply optional attached-corner state to one accordion header and body."""

    content_widget = content_body
    get_content_widget = getattr(content_body, "content_widget", None)
    if callable(get_content_widget):
        content_widget = get_content_widget()
    for widget in (card_title, content_widget):
        setter = getattr(widget, "set_accordion_content_attached", None)
        if callable(setter):
            setter(attached)


class AccordionMotionController(QObject):
    """Own synchronized expand/collapse animation for one node-card body."""

    def __init__(
        self,
        *,
        owner: QWidget,
        card_title: QWidget,
        content_body: AccordionContentClip,
        content_layout: QVBoxLayout,
        divider_below_title: QWidget | None,
        chevron: AccordionChevronWidget,
        cube_height_updater: Callable[[], None],
    ) -> None:
        """Bind one card header, body, and optional divider to shared motion policy."""

        super().__init__(owner)
        self._card_title = card_title
        self._content_body = content_body
        self._content_layout = content_layout
        self._divider_below_title = divider_below_title
        self._chevron = chevron
        self._cube_height_updater = cube_height_updater
        self._state = ensure_card_body_layout_state(
            content_body=content_body,
            expanded_height=resolve_card_body_expanded_height(
                content_layout=content_layout,
                allow_unbounded_height=False,
            ),
        )

        self._content_body.set_content_height(self._state.expanded_height)
        self._offset_animation = QPropertyAnimation(
            content_body,
            b"contentOffsetY",
            self,
        )
        self._chevron_animation = QPropertyAnimation(chevron, b"rotation", self)
        self._divider_timer = QTimer(self)
        self._divider_timer.setSingleShot(True)
        self._divider_timer.timeout.connect(self._show_divider_after_expand)

        self._offset_animation.finished.connect(self._on_animation_finished)

        apply_card_body_layout_state(
            content_body=content_body,
            state=self._state,
            allow_unbounded_height=False,
        )
        self._sync_final_content_offset()
        self._sync_surface_attachment()
        if self._divider_below_title is not None:
            self._divider_below_title.setVisible(not self._state.collapsed)

    def toggle(self) -> None:
        """Animate the card body toward the opposite collapsed state."""

        self._divider_timer.stop()
        will_collapse = not self._state.collapsed
        self._resolve_expanded_height()
        target_offset = -self._state.expanded_height if will_collapse else 0
        target_rotation = (
            _COLLAPSED_CHEVRON_ROTATION if will_collapse else _EXPANDED_CHEVRON_ROTATION
        )
        duration_ms = (
            ACCORDION_COLLAPSE_DURATION_MS
            if will_collapse
            else ACCORDION_EXPAND_DURATION_MS
        )
        easing_curve = (
            ACCORDION_COLLAPSE_EASING_CURVE
            if will_collapse
            else ACCORDION_EXPAND_EASING_CURVE
        )

        self._prepare_visible_transition(will_collapse=will_collapse)
        self._state.collapsed = will_collapse
        self._state.animating = True
        self._sync_surface_attachment(attached=True)
        if self._divider_below_title is not None:
            self._divider_below_title.setVisible(False)

        resolved_duration = restart_property_animation(
            self._offset_animation,
            start_value=self._content_body.content_offset_y(),
            end_value=target_offset,
            duration_ms=duration_ms,
            easing_curve=easing_curve,
        )
        restart_property_animation(
            self._chevron_animation,
            start_value=self._chevron.rotation_value(),
            end_value=target_rotation,
            duration_ms=duration_ms,
            easing_curve=easing_curve,
        )

        if not will_collapse and self._divider_below_title is not None:
            if resolved_duration == 0 or is_reduced_motion_enabled():
                self._divider_below_title.setVisible(True)
            else:
                divider_delay = max(1, int(resolved_duration * _DIVIDER_SHOW_PROGRESS))
                self._divider_timer.start(divider_delay)

        self._cube_height_updater()

    def content_offset_y(self) -> int:
        """Return the current clipped content offset for tests and diagnostics."""

        return self._content_body.content_offset_y()

    def content_height(self) -> int:
        """Return the measured natural content height for tests and diagnostics."""

        return self._content_body.content_height()

    def is_body_clip_visible(self) -> bool:
        """Return whether the content clip currently participates visibly."""

        return not self._content_body.isHidden()

    def _prepare_visible_transition(self, *, will_collapse: bool) -> None:
        """Keep layout stable while the clipped content offset animates."""

        if will_collapse:
            prepare_card_body_collapse(content_body=self._content_body)
            self._content_body.setMaximumHeight(self._state.expanded_height)
            self._content_body.setVisible(True)
            return
        prepare_card_body_expand(
            content_body=self._content_body,
            state=self._state,
        )
        self._content_body.setMaximumHeight(self._state.expanded_height)
        self._content_body.setVisible(True)

    def _resolve_expanded_height(self) -> int:
        """Refresh and return the natural expanded body height."""

        self._state.expanded_height = resolve_card_body_expanded_height(
            content_layout=self._content_layout,
            allow_unbounded_height=False,
        )
        self._content_body.set_content_height(self._state.expanded_height)
        return self._state.expanded_height

    def _show_divider_after_expand(self) -> None:
        """Reveal the divider only once the expand transition has substantially settled."""

        if self._divider_below_title is not None and not self._state.collapsed:
            self._divider_below_title.setVisible(True)

    def _on_animation_finished(self) -> None:
        """Apply the authoritative final card state after one transition completes."""

        self._state.animating = False
        apply_card_body_layout_state(
            content_body=self._content_body,
            state=self._state,
            allow_unbounded_height=False,
        )
        self._sync_final_content_offset()
        self._sync_surface_attachment()
        if not self._state.collapsed:
            self._show_divider_after_expand()
        self._cube_height_updater()

    def _sync_final_content_offset(self) -> None:
        """Set the content offset that matches the current authoritative state."""

        offset = -self._state.expanded_height if self._state.collapsed else 0
        self._content_body.set_content_offset_y(offset)

    def _sync_surface_attachment(self, *, attached: bool | None = None) -> None:
        """Update optional header/content corner states for the current transition."""

        is_attached = not self._state.collapsed if attached is None else attached
        set_accordion_surface_attachment(
            card_title=self._card_title,
            content_body=self._content_body,
            attached=is_attached,
        )


__all__ = [
    "AccordionChevronWidget",
    "AccordionContentClip",
    "AccordionMotionController",
    "set_accordion_surface_attachment",
]
