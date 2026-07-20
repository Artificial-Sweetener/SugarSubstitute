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

"""Provide Toolkit-aligned Settings card widgets for the Settings workspace."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QMargins, QObject, QEvent, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QEnterEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, IconWidget  # type: ignore[import-untyped]
from qfluentwidgets.common.icon import FluentIcon  # type: ignore[import-untyped]

from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN,
    SETTINGS_CARD_ACTION_ICON_MAX_SIZE,
    SETTINGS_CARD_DESCRIPTION_FONT_SIZE,
    SETTINGS_CARD_ICON_MAX_SIZE,
    SETTINGS_CARD_ICON_RIGHT_MARGIN,
    SETTINGS_CARD_MIN_HEIGHT,
    SETTINGS_CARD_MIN_WIDTH,
    SETTINGS_CARD_PADDING,
    SETTINGS_CARD_RADIUS,
    SETTINGS_CARD_TEXT_CONTROL_GAP,
    SETTINGS_CARD_TRAILING_MIN_WIDTH,
    SETTINGS_CARD_VERTICAL_CONTENT_SPACING,
    SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD,
    SETTINGS_CARD_WRAP_THRESHOLD,
    CLICKABLE_SETTINGS_EXPANDER_ITEM_PADDING,
    SETTINGS_EXPANDER_HEADER_PADDING,
    SETTINGS_EXPANDER_ITEM_MIN_HEIGHT,
    SETTINGS_EXPANDER_ITEM_PADDING,
    settings_card_border_color,
    settings_card_fill_color,
    settings_card_overlay_color,
)
from substitute.presentation.widgets.row_interaction_feedback import (
    RowInteractionFeedback,
)
from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    ApplicationText,
    LocalizationBindings,
)

SettingsCardLayoutMode = Literal["wide", "wrapped", "wrapped_no_icon"]
SettingsCardContentAlignment = Literal["right", "left", "vertical"]
SettingsCardAppearance = Literal[
    "normal",
    "expander_header",
    "controlled_expander_header",
    "expander_item",
    "clickable_expander_item",
    "segmented_item",
]


class SettingsCard(QFrame):
    """Render one Windows-like settings card with optional trailing content."""

    def __init__(
        self,
        *,
        title: ApplicationText,
        description: ApplicationText = "",
        visual_widget: QWidget | None = None,
        trailing_widget: QWidget | None = None,
        reserve_visual_space: bool = True,
        show_chevron: bool = False,
        action_icon: QWidget | None = None,
        appearance: SettingsCardAppearance = "normal",
        content_alignment: SettingsCardContentAlignment = "right",
        wrap_threshold: int = SETTINGS_CARD_WRAP_THRESHOLD,
        wrap_no_icon_threshold: int = SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD,
        stretch_wrapped_content: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        """Create a Settings card with Toolkit-aligned spacing and wrapping."""

        super().__init__(parent)
        self.setObjectName("SubstituteSettingsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self._appearance = appearance
        self._content_alignment = content_alignment
        self._wrap_threshold = wrap_threshold
        self._wrap_no_icon_threshold = wrap_no_icon_threshold
        self._stretch_wrapped_content = stretch_wrapped_content
        self._expander_header_attached = False
        self.setMinimumSize(SETTINGS_CARD_MIN_WIDTH, self._minimum_height())
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._reserve_visual_space = reserve_visual_space
        self._layout_mode: SettingsCardLayoutMode = "wide"
        self._trailing_is_wrapped = False

        self.visual_slot = self._build_visual_slot(visual_widget)
        self.title_label = self._build_title_label(title)
        self.description_label = self._build_description_label(description)
        self._localization_bindings = LocalizationBindings(self)
        self._bind_application_message(self.title_label, title)
        self._bind_application_message(self.description_label, description)
        self.text_column = self._build_text_column()
        self.trailing_widget = trailing_widget
        self.action_icon = self._build_action_icon(action_icon, show_chevron)
        self._build_layout()
        self._sync_layout_mode()

    def layout_mode(self) -> SettingsCardLayoutMode:
        """Return the current threshold-selected layout mode."""

        return self._layout_mode

    def appearance(self) -> SettingsCardAppearance:
        """Return the current visual appearance role for this settings card."""

        return self._appearance

    def content_alignment(self) -> SettingsCardContentAlignment:
        """Return how this card places its content relative to header text."""

        return self._content_alignment

    def set_expander_header_attached(self, attached: bool) -> None:
        """Set whether an expander header joins visible body content."""

        if self._expander_header_attached == attached:
            return
        self._expander_header_attached = attached
        self.update()

    def expander_header_attached(self) -> bool:
        """Return whether this header should square its bottom overlay corners."""

        return self._expander_header_attached

    def interactive_targets(self) -> tuple[QWidget, ...]:
        """Return body children that should activate an interactive card."""

        return (
            self.visual_slot,
            self.text_column,
            self.title_label,
            self.description_label,
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recompute wrapped layout mode when the card width changes."""

        super().resizeEvent(event)
        self._sync_layout_mode()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the card fill and border before child widgets draw."""

        _ = event
        if self._appearance in {"expander_header", "controlled_expander_header"}:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._appearance in {
            "expander_item",
            "clickable_expander_item",
            "segmented_item",
        }:
            return
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(settings_card_border_color())
        painter.setBrush(settings_card_fill_color(self))
        painter.drawRoundedRect(rect, SETTINGS_CARD_RADIUS, SETTINGS_CARD_RADIUS)

    def _build_visual_slot(self, visual_widget: QWidget | None) -> QWidget:
        """Create the card icon slot."""

        slot = QWidget(self)
        slot.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        slot.setStyleSheet("background-color: transparent; border: none;")
        width = SETTINGS_CARD_ICON_MAX_SIZE if self._reserve_visual_space else 0
        slot.setFixedSize(width, SETTINGS_CARD_ICON_MAX_SIZE)
        layout = QHBoxLayout(slot)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if visual_widget is not None:
            visual_widget.setParent(slot)
            visual_widget.setMaximumSize(
                SETTINGS_CARD_ICON_MAX_SIZE,
                SETTINGS_CARD_ICON_MAX_SIZE,
            )
            layout.addWidget(visual_widget, 0, Qt.AlignmentFlag.AlignCenter)
        return slot

    def _build_title_label(self, title: ApplicationText) -> BodyLabel:
        """Create the card title label."""

        label = BodyLabel(title, self)
        font = label.font()
        font.setWeight(QFont.Weight.DemiBold)
        label.setFont(font)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return label

    def _build_description_label(self, description: ApplicationText) -> CaptionLabel:
        """Create the optional card description label."""

        label = CaptionLabel(description, self)
        font = label.font()
        font.setPixelSize(SETTINGS_CARD_DESCRIPTION_FONT_SIZE)
        label.setFont(font)
        label.setWordWrap(True)
        label.setVisible(bool(description))
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return label

    def _bind_application_message(
        self,
        target: BodyLabel | CaptionLabel,
        message: ApplicationText,
    ) -> None:
        """Retain marked app copy while leaving opaque strings untouched."""

        if isinstance(message, ApplicationMessage):
            self._localization_bindings.bind_message(target, message)

    def _build_text_column(self) -> QWidget:
        """Create the title and description column."""

        column = QWidget(self)
        column.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        column.setStyleSheet("background-color: transparent; border: none;")
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        return column

    def _build_action_icon(
        self,
        action_icon: QWidget | None,
        show_chevron: bool,
    ) -> QWidget | None:
        """Create the optional action icon or chevron slot."""

        if action_icon is not None:
            icon = action_icon
        elif show_chevron:
            icon = IconWidget(FluentIcon.CHEVRON_RIGHT, self)
        else:
            return None
        icon.setParent(self)
        icon.setFixedSize(
            SETTINGS_CARD_ACTION_ICON_MAX_SIZE,
            SETTINGS_CARD_ACTION_ICON_MAX_SIZE,
        )
        return icon

    def _build_layout(self) -> None:
        """Compose the wide and wrapped card layouts."""

        margins = self._padding()
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(
            margins.left(),
            margins.top(),
            margins.right(),
            margins.bottom(),
        )
        outer_layout.setSpacing(SETTINGS_CARD_VERTICAL_CONTENT_SPACING)

        self._primary_layout = QHBoxLayout()
        self._primary_layout.setContentsMargins(0, 0, 0, 0)
        self._primary_layout.setSpacing(0)
        self._primary_layout.addWidget(
            self.visual_slot,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self._primary_layout.addSpacing(SETTINGS_CARD_ICON_RIGHT_MARGIN)
        self._primary_layout.addWidget(
            self.text_column,
            1,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self._trailing_layout = QHBoxLayout()
        self._trailing_layout.setContentsMargins(0, 0, 0, 0)
        self._trailing_layout.setSpacing(0)
        if self.trailing_widget is not None:
            self.trailing_widget.setMinimumWidth(
                max(
                    self.trailing_widget.minimumWidth(),
                    SETTINGS_CARD_TRAILING_MIN_WIDTH,
                )
            )
            self._primary_layout.addSpacing(SETTINGS_CARD_TEXT_CONTROL_GAP)
            self._trailing_layout.addWidget(
                self.trailing_widget,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
        self._primary_layout.addLayout(self._trailing_layout)
        if self.action_icon is not None:
            self._primary_layout.addSpacing(SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN)
            self._primary_layout.addWidget(
                self.action_icon,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
        outer_layout.addLayout(self._primary_layout)

        self._wrapped_content = QWidget(self)
        self._wrapped_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._wrapped_content.setStyleSheet(
            "background-color: transparent; border: none;"
        )
        self._wrapped_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._wrapped_layout = QHBoxLayout(self._wrapped_content)
        self._wrapped_layout.setContentsMargins(
            self._wrapped_content_left_margin(),
            0,
            0,
            0,
        )
        self._wrapped_layout.setSpacing(0)
        outer_layout.addWidget(self._wrapped_content)
        self._wrapped_content.hide()

    def _sync_layout_mode(self) -> None:
        """Apply Toolkit card wrap thresholds to the current card width."""

        width = self.width()
        if width <= 0:
            width = self._wrap_threshold + 1
        if width < self._wrap_no_icon_threshold:
            mode: SettingsCardLayoutMode = "wrapped_no_icon"
        elif width < self._wrap_threshold:
            mode = "wrapped"
        else:
            mode = "wide"
        self._layout_mode = mode
        self._sync_content_alignment(mode)

    def _sync_content_alignment(self, mode: SettingsCardLayoutMode) -> None:
        """Apply the current width state and configured content alignment."""

        if self._content_alignment == "left":
            self._set_header_collapsed(True)
            self._set_visual_collapsed(True)
            self._set_trailing_wrapped(True)
            self._notify_trailing_layout_mode(mode)
            return
        self._set_header_collapsed(False)
        self._set_visual_collapsed(mode == "wrapped_no_icon")
        self._set_trailing_wrapped(
            mode != "wide" or self._content_alignment == "vertical"
        )
        self._notify_trailing_layout_mode(mode)

    def _set_header_collapsed(self, collapsed: bool) -> None:
        """Show or hide header text for left-aligned content-only rows."""

        self.text_column.setVisible(not collapsed)

    def _set_visual_collapsed(self, collapsed: bool) -> None:
        """Collapse the icon slot for very narrow card widths."""

        if collapsed:
            self.visual_slot.setFixedWidth(0)
            self.visual_slot.hide()
            self._wrapped_layout.setContentsMargins(0, 0, 0, 0)
            return
        width = SETTINGS_CARD_ICON_MAX_SIZE if self._reserve_visual_space else 0
        self.visual_slot.setFixedWidth(width)
        self.visual_slot.setVisible(width > 0)
        self._wrapped_layout.setContentsMargins(
            self._wrapped_content_left_margin(),
            0,
            0,
            0,
        )

    def _minimum_height(self) -> int:
        """Return the minimum row height for the current appearance role."""

        if self._appearance in {
            "expander_item",
            "clickable_expander_item",
        }:
            return SETTINGS_EXPANDER_ITEM_MIN_HEIGHT
        return SETTINGS_CARD_MIN_HEIGHT

    def _padding(self) -> QMargins:
        """Return Toolkit-aligned content padding for the current appearance."""

        if self._appearance == "expander_header":
            return SETTINGS_EXPANDER_HEADER_PADDING
        if self._appearance == "controlled_expander_header":
            return SETTINGS_CARD_PADDING
        if self._appearance == "segmented_item":
            return SETTINGS_CARD_PADDING
        if self._appearance == "expander_item":
            return SETTINGS_EXPANDER_ITEM_PADDING
        if self._appearance == "clickable_expander_item":
            return CLICKABLE_SETTINGS_EXPANDER_ITEM_PADDING
        return SETTINGS_CARD_PADDING

    def _wrapped_content_left_margin(self) -> int:
        """Return the wrapped trailing-content inset for the current appearance."""

        if self._appearance in {"expander_item", "clickable_expander_item"}:
            return 0
        if self._reserve_visual_space:
            return SETTINGS_CARD_ICON_MAX_SIZE + SETTINGS_CARD_ICON_RIGHT_MARGIN
        return 0

    def _set_trailing_wrapped(self, wrapped: bool) -> None:
        """Move trailing content between the wide and wrapped card positions."""

        if self.trailing_widget is None or self._trailing_is_wrapped == wrapped:
            self._wrapped_content.setVisible(
                self.trailing_widget is not None and wrapped
            )
            return
        if wrapped:
            self._trailing_layout.removeWidget(self.trailing_widget)
            self._wrapped_layout.addWidget(
                self.trailing_widget,
                1 if self._stretch_wrapped_content else 0,
            )
            self._wrapped_content.show()
        else:
            self._wrapped_layout.removeWidget(self.trailing_widget)
            self._trailing_layout.addWidget(
                self.trailing_widget,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
            self._wrapped_content.hide()
        self._trailing_is_wrapped = wrapped

    def _notify_trailing_layout_mode(self, mode: SettingsCardLayoutMode) -> None:
        """Tell cooperative trailing content about the active card layout mode."""

        if self.trailing_widget is None:
            return
        setter = getattr(self.trailing_widget, "set_settings_card_layout_mode", None)
        if callable(setter):
            setter(mode)


class InteractiveSettingsCard(SettingsCard):
    """Settings card that activates from body clicks with Fluent feedback."""

    activated = Signal()

    def __init__(
        self,
        *,
        title: ApplicationText,
        description: ApplicationText = "",
        visual_widget: QWidget | None = None,
        trailing_widget: QWidget | None = None,
        reserve_visual_space: bool = True,
        show_chevron: bool = False,
        action_icon: QWidget | None = None,
        appearance: SettingsCardAppearance = "normal",
        content_alignment: SettingsCardContentAlignment = "right",
        wrap_threshold: int = SETTINGS_CARD_WRAP_THRESHOLD,
        wrap_no_icon_threshold: int = SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD,
        stretch_wrapped_content: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        """Create an interactive Settings card."""

        super().__init__(
            title=title,
            description=description,
            visual_widget=visual_widget,
            trailing_widget=trailing_widget,
            reserve_visual_space=reserve_visual_space,
            show_chevron=show_chevron,
            action_icon=action_icon,
            appearance=appearance,
            content_alignment=content_alignment,
            wrap_threshold=wrap_threshold,
            wrap_no_icon_threshold=wrap_no_icon_threshold,
            stretch_wrapped_content=stretch_wrapped_content,
            parent=parent,
        )
        self._pressed = False
        self._hovered = False
        self._interaction = RowInteractionFeedback(
            self,
            overlay_path=self._feedback_overlay_path,
            activation=self.activated.emit,
            consume_target_press=False,
        )
        self._interaction.set_interactive_targets(self.interactive_targets())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route text and visual child clicks through the card interaction state."""

        if self._interaction.eventFilter(watched, event):
            return True
        return bool(super().eventFilter(watched, event))

    def enterEvent(self, event: QEnterEvent) -> None:
        """Apply hover state when the pointer enters the card."""

        self._hovered = True
        self._interaction.set_hovered(True)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear transient interaction state when the pointer exits the card."""

        self._hovered = False
        self._pressed = False
        self._interaction.clear_transient_state()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Apply pressed state for body clicks."""

        self._pressed = event.button() == Qt.MouseButton.LeftButton
        self._interaction.handle_mouse_press(event)
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Activate the card when a body click is released."""

        self._pressed = False
        self._interaction.handle_mouse_release(event)
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint card feedback above the base card fill."""

        super().paintEvent(event)
        if self.appearance() in {"expander_item", "clickable_expander_item"}:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        overlay = settings_card_overlay_color(
            pressed=self._pressed,
            hovered=self._hovered,
        )
        if overlay.alpha() > 0:
            painter.fillPath(self._feedback_overlay_path(self.rect()), overlay)
        self._interaction.paint_overlay(painter)

    def _feedback_overlay_path(self, rect: QRect) -> QPainterPath:
        """Return the overlay path for this card's current attachment state."""

        return _settings_card_overlay_path(
            rect,
            bottom_corners_attached=(
                self.appearance() in {"expander_header", "controlled_expander_header"}
                and self.expander_header_attached()
            ),
        )


def _settings_card_overlay_path(
    rect: QRect,
    *,
    bottom_corners_attached: bool = False,
) -> QPainterPath:
    """Return the rounded card overlay path."""

    if bottom_corners_attached:
        return _settings_card_top_rounded_overlay_path(rect)
    path = QPainterPath()
    path.addRoundedRect(
        QRectF(rect.adjusted(1, 1, -1, -1)),
        SETTINGS_CARD_RADIUS,
        SETTINGS_CARD_RADIUS,
    )
    return path


def _settings_card_top_rounded_overlay_path(rect: QRect) -> QPainterPath:
    """Return an overlay path with rounded top corners and square bottom corners."""

    adjusted = rect.adjusted(1, 1, -1, -1)
    path = QPainterPath()
    x = float(adjusted.x())
    y = float(adjusted.y())
    width = float(adjusted.width())
    height = float(adjusted.height())
    radius = min(float(SETTINGS_CARD_RADIUS), width / 2.0, height / 2.0)

    path.moveTo(x + radius, y)
    path.lineTo(x + width - radius, y)
    if radius:
        path.quadTo(x + width, y, x + width, y + radius)
    path.lineTo(x + width, y + height)
    path.lineTo(x, y + height)
    path.lineTo(x, y + radius)
    if radius:
        path.quadTo(x, y, x + radius, y)
    path.closeSubpath()
    return path


__all__ = [
    "InteractiveSettingsCard",
    "SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN",
    "SETTINGS_CARD_ACTION_ICON_MAX_SIZE",
    "SETTINGS_CARD_DESCRIPTION_FONT_SIZE",
    "SETTINGS_CARD_ICON_MAX_SIZE",
    "SETTINGS_CARD_ICON_RIGHT_MARGIN",
    "SETTINGS_CARD_MIN_HEIGHT",
    "SETTINGS_CARD_MIN_WIDTH",
    "SETTINGS_CARD_PADDING",
    "SETTINGS_CARD_RADIUS",
    "SETTINGS_CARD_TEXT_CONTROL_GAP",
    "SETTINGS_CARD_TRAILING_MIN_WIDTH",
    "SETTINGS_CARD_VERTICAL_CONTENT_SPACING",
    "SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD",
    "SETTINGS_CARD_WRAP_THRESHOLD",
    "SettingsCard",
    "SettingsCardAppearance",
    "SettingsCardContentAlignment",
    "SettingsCardLayoutMode",
]
