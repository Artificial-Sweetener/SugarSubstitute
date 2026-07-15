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

"""Render recoverable Comfy startup incidents in one summary dialog."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping, Sequence
import logging
from typing import Protocol, cast

from PySide6.QtCore import QRectF, Qt, QPropertyAnimation, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    InfoBarIcon,
    MessageBoxBase,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
    Theme,
    drawIcon,
)
from shiboken6 import isValid

from substitute.presentation.motion import (
    ENTER_EASING_CURVE,
    EXIT_EASING_CURVE,
    restart_property_animation,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    floating_surface_border_rgba,
    floating_surface_rgba,
    floating_surface_text_color,
    winui_card_border_color,
    winui_card_fill_color,
)

_DIALOG_WIDTH = 720
_REPORT_MINIMUM_HEIGHT = 260
_REPORT_MINIMUM_HEIGHT_UNDER_PRESSURE = 160
_MIN_DIALOG_HEIGHT = 280
_DIALOG_HEIGHT_MARGIN = 48
_HEADER_TEXT_SPACING = 4
_CONTENT_TOP_MARGIN = 24
_CONTENT_SIDE_MARGIN = 24
_CONTENT_BOTTOM_MARGIN = 16
_CONTENT_SPACING = 12
_ACTION_BUTTON_HEIGHT = 32
_CLOSE_BUTTON_MINIMUM_WIDTH = 88
_ACTION_BUTTON_MINIMUM_WIDTH = 108
_HEADER_ICON_TEXT_SPACING = 12
_REPORT_TOGGLE_DURATION_MS = 160
_FALLBACK_PARENT: QWidget | None = None
_LOG = logging.getLogger(__name__)


class StartupDiagnosticsIncidentView(Protocol):
    """Describe incident fields needed by the startup diagnostics dialog."""

    @property
    def fingerprint(self) -> str:
        """Return the stable incident fingerprint."""

    @property
    def title(self) -> str:
        """Return the incident title."""

    @property
    def message(self) -> str:
        """Return the incident message."""

    @property
    def source(self) -> str | None:
        """Return the incident source label when available."""

    @property
    def severity(self) -> object:
        """Return the incident severity enum or string value."""

    @property
    def impact(self) -> str | None:
        """Return the incident impact summary when available."""

    @property
    def cause(self) -> str | None:
        """Return the likely incident cause when available."""

    @property
    def remediation(self) -> str | None:
        """Return the suggested incident action when available."""

    @property
    def values(self) -> Mapping[str, object]:
        """Return structured incident metadata."""


class StartupDiagnosticsDialog(MessageBoxBase):  # type: ignore[misc]
    """Show recoverable Comfy startup incidents with per-incident ignore choices."""

    def __init__(
        self,
        *,
        incidents: Sequence[StartupDiagnosticsIncidentView],
        report_text: str,
        ignored_count: int = 0,
        parent: object | None = None,
        url_opener: Callable[[str], bool] | None = None,
    ) -> None:
        """Build the startup diagnostics summary dialog."""

        parent_widget = _resolve_parent(parent)
        super().__init__(parent_widget)
        self._incidents = tuple(incidents)
        self._report_text = report_text
        self._ignored_count = ignored_count
        self._url_opener = url_opener or _open_external_url
        self._checkboxes: dict[str, QCheckBox] = {}
        self._details_visible = False
        self._details_animation_target_visible = False
        self._dialog_max_height = _dialog_max_height(parent_widget)

        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.widget.setMinimumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumWidth(_DIALOG_WIDTH)
        self.widget.setMaximumHeight(self._dialog_max_height)
        self.viewLayout.setContentsMargins(
            _CONTENT_SIDE_MARGIN,
            _CONTENT_TOP_MARGIN,
            _CONTENT_SIDE_MARGIN,
            _CONTENT_BOTTOM_MARGIN,
        )
        self.viewLayout.setSpacing(0)

        self._build_body_container()
        self._build_header()
        self._build_summary()
        self._build_incidents()
        self._build_details()
        self._build_actions()
        self._sync_body_height()
        self._apply_theme()
        connect_theme_refresh(self, self._apply_theme)

    def selected_ignored_fingerprints(self) -> frozenset[str]:
        """Return fingerprints selected for future suppression."""

        return frozenset(
            fingerprint
            for fingerprint, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        )

    def _build_body_container(self) -> None:
        """Create the scrollable body area above the fixed footer."""

        self._body_scroll_area = QScrollArea(self.widget)
        self._body_scroll_area.setWidgetResizable(True)
        self._body_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._body_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._body_scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollArea > QWidget { background: transparent; }"
        )
        self._body_scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._body_height_animation = QPropertyAnimation(
            self._body_scroll_area,
            b"maximumHeight",
            self,
        )
        self._body_height_animation.valueChanged.connect(
            self._apply_body_animation_value
        )
        self._body_height_animation.finished.connect(self._finish_details_animation)

        self._body_widget = QWidget(self._body_scroll_area)
        self._body_layout = QVBoxLayout(self._body_widget)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(_CONTENT_SPACING)
        self._body_scroll_area.setWidget(self._body_widget)
        self.viewLayout.addWidget(self._body_scroll_area)

    def _build_header(self) -> None:
        """Create the non-fatal diagnostics header."""

        header = QWidget(self.widget)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QGridLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(_HEADER_ICON_TEXT_SPACING)
        layout.setVerticalSpacing(_HEADER_TEXT_SPACING)

        self._title_label = SubtitleLabel("ComfyUI started with issues", header)
        self._message_label = BodyLabel(
            "ComfyUI is ready, but it reported issues while loading.",
            header,
        )
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._message_label.setWordWrap(True)
        self._message_label.setFixedHeight(self._message_label.fontMetrics().height())

        icon_size = _header_glyph_size(self._title_label, self._message_label)
        self._message_label.setMinimumWidth(_header_text_column_width(icon_size))
        icon_cell = QWidget(header)
        icon_cell.setFixedWidth(icon_size)
        icon_layout = QVBoxLayout(icon_cell)
        icon_layout.setContentsMargins(
            0,
            _header_icon_top_offset(
                self._title_label,
                self._message_label,
                icon_size,
            ),
            0,
            0,
        )
        icon_layout.setSpacing(0)
        self._icon_widget = StartupDiagnosticsGlyphWidget(icon_size, icon_cell)
        icon_layout.addWidget(self._icon_widget, 0, Qt.AlignmentFlag.AlignTop)
        icon_layout.addStretch(1)

        layout.addWidget(icon_cell, 0, 0, 2, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._title_label, 0, 1, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._message_label, 1, 1, Qt.AlignmentFlag.AlignLeft)
        layout.setColumnStretch(1, 1)
        self._body_layout.addWidget(header)

    def _build_summary(self) -> None:
        """Create compact horizontal incident count tiles."""

        self._summary_frame = QFrame(self.widget)
        self._summary_frame.setObjectName("StartupDiagnosticsSummaryFrame")
        layout = QHBoxLayout(self._summary_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        rows = (
            (
                "Errors",
                str(_count_severity(self._incidents, "error")),
                InfoBarIcon.ERROR,
            ),
            (
                "Warnings",
                str(_count_severity(self._incidents, "warning")),
                InfoBarIcon.INFORMATION,
            ),
            ("Ignored", str(self._ignored_count), FIF.HIDE),
        )
        for label, value, icon in rows:
            layout.addWidget(
                _summary_tile(
                    label=label,
                    value=value,
                    icon=icon,
                    parent=self._summary_frame,
                ),
                1,
            )
        self._body_layout.addWidget(self._summary_frame)

    def _build_incidents(self) -> None:
        """Create one structured incident panel with selectable rows."""

        self._incidents_frame = QFrame(self.widget)
        self._incidents_frame.setObjectName("StartupDiagnosticsIncidentsFrame")
        layout = QGridLayout(self._incidents_frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        row_index = 0
        for incident in self._incidents:
            checkbox = QCheckBox(self._incidents_frame)
            checkbox.setToolTip("Ignore this startup issue next time")
            self._checkboxes[incident.fingerprint] = checkbox

            title = StrongBodyLabel(_incident_title(incident), self._incidents_frame)
            detail_widgets = _incident_detail_widgets(
                incident,
                self._incidents_frame,
                self._open_incident_url,
            )

            layout.addWidget(
                checkbox,
                row_index,
                0,
                len(detail_widgets) + 1,
                1,
                Qt.AlignmentFlag.AlignTop,
            )
            layout.addWidget(title, row_index, 1, Qt.AlignmentFlag.AlignLeft)
            row_index += 1
            for widget in detail_widgets:
                layout.addWidget(widget, row_index, 1)
                row_index += 1

        layout.setColumnStretch(1, 1)
        self._body_layout.addWidget(self._incidents_frame)

    def _build_details(self) -> None:
        """Create the complete report details panel."""

        self._details_button = PushButton("Show report", self.widget)
        self._details_button.clicked.connect(self._toggle_details)
        self._body_layout.addWidget(self._details_button)

        self._report_editor = PlainTextEdit(self.widget)
        self._report_editor.setPlainText(self._report_text)
        self._report_editor.setReadOnly(True)
        self._report_editor.setMinimumHeight(self._report_editor_minimum_height())
        self._report_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._report_editor.hide()
        self._body_layout.addWidget(self._report_editor)

    def _report_editor_minimum_height(self) -> int:
        """Return a report editor height that yields under parent height pressure."""

        if self._dialog_max_height < 520:
            return _REPORT_MINIMUM_HEIGHT_UNDER_PRESSURE
        return _REPORT_MINIMUM_HEIGHT

    def _build_actions(self) -> None:
        """Create footer actions for copying, ignoring, and closing."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(68)
        self._clear_button_layout()
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)

        self._copy_button = PushButton("Copy report", self.buttonGroup)
        self._copy_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._copy_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self._copy_button.clicked.connect(self._copy_report)
        self.buttonLayout.addWidget(self._copy_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._ignore_button = PushButton("Ignore selected", self.buttonGroup)
        self._ignore_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._ignore_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self._ignore_button.clicked.connect(self.accept)
        self.buttonLayout.addWidget(
            self._ignore_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self._close_button = PrimaryPushButton("Close", self.buttonGroup)
        self._close_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._close_button.setMinimumWidth(_CLOSE_BUTTON_MINIMUM_WIDTH)
        self._close_button.clicked.connect(self.reject)
        self.buttonLayout.addWidget(
            self._close_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

    def _clear_button_layout(self) -> None:
        """Hide and remove qfluent's default footer widgets."""

        while self.buttonLayout.count():
            item = self.buttonLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
            nested_layout = item.layout()
            if nested_layout is not None:
                _clear_layout(nested_layout)

    def _toggle_details(self) -> None:
        """Show or hide the complete diagnostics report body."""

        self._details_visible = not self._details_visible
        self._details_button.setText(
            "Hide report" if self._details_visible else "Show report"
        )
        self._animate_report_visibility(self._details_visible)

    def _animate_report_visibility(self, visible: bool) -> None:
        """Animate report expansion or collapse without moving the modal mask."""

        self._details_animation_target_visible = visible
        if visible:
            self._report_editor.show()
        target_height, needs_scroll = self._body_height_for(visible)
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if needs_scroll
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        start_height = max(1, self._body_scroll_area.height())
        if start_height == target_height:
            self._apply_body_height(target_height)
            self._finish_details_animation()
            return

        resolved_duration = restart_property_animation(
            self._body_height_animation,
            start_value=start_height,
            end_value=target_height,
            duration_ms=_REPORT_TOGGLE_DURATION_MS,
            easing_curve=ENTER_EASING_CURVE if visible else EXIT_EASING_CURVE,
        )
        if resolved_duration == 0:
            self._apply_body_height(target_height)
            self._finish_details_animation()

    def _apply_body_animation_value(self, value: object) -> None:
        """Apply one report-height animation frame and keep the dialog centered."""

        if isinstance(value, int):
            self._apply_body_height(value)
        elif isinstance(value, float):
            self._apply_body_height(round(value))

    def _finish_details_animation(self) -> None:
        """Settle report visibility and geometry after the height animation ends."""

        if not self._details_animation_target_visible:
            self._report_editor.hide()
        self._sync_body_height()

    def _apply_body_height(self, height: int) -> None:
        """Apply one fixed body height and recenter the qfluent content widget."""

        self._body_scroll_area.setFixedHeight(max(1, height))
        self.vBoxLayout.invalidate()
        self.vBoxLayout.activate()
        self.widget.adjustSize()
        self._center_dialog_widget()

    def _sync_body_height(self) -> None:
        """Size the scroll body naturally unless parent height forces scrolling."""

        height, needs_scroll = self._body_height_for(self._details_visible)
        self._body_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if needs_scroll
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._apply_body_height(height)

    def _body_height_for(self, details_visible: bool) -> tuple[int, bool]:
        """Return target body height and scrollbar state for one details state."""

        was_visible = not self._report_editor.isHidden()
        if was_visible != details_visible:
            self._report_editor.setVisible(details_visible)
        self._body_layout.activate()
        self._body_widget.adjustSize()
        content_height = self._body_widget.sizeHint().height()
        if was_visible != details_visible:
            self._report_editor.setVisible(was_visible)

        maximum_body_height = self._maximum_body_height()
        needs_scroll = content_height > maximum_body_height
        body_height = (
            maximum_body_height
            if needs_scroll
            else min(content_height + 2, maximum_body_height)
        )
        return body_height, needs_scroll

    def _center_dialog_widget(self) -> None:
        """Keep the resized qfluent content widget centered inside the modal mask."""

        self.widget.move(
            max(0, (self.width() - self.widget.width()) // 2),
            max(0, (self.height() - self.widget.height()) // 2),
        )

    def _maximum_body_height(self) -> int:
        """Return the tallest body area that keeps footer and margins visible."""

        margins = self.viewLayout.contentsMargins()
        return int(
            max(
                1,
                self._dialog_max_height
                - self.buttonGroup.height()
                - margins.top()
                - margins.bottom(),
            )
        )

    def _copy_report(self) -> None:
        """Copy the complete startup diagnostics report."""

        QGuiApplication.clipboard().setText(self._report_text)

    def _open_incident_url(self, url: str) -> None:
        """Open one incident support URL without changing modal state."""

        if not self._url_opener(url):
            _LOG.warning("Failed to open startup diagnostics URL.", extra={"url": url})

    def _apply_theme(self) -> None:
        """Refresh WinUI-style summary and row colors."""

        fill = _rgba_string(winui_card_fill_color())
        border = _rgba_string(winui_card_border_color())
        self._incidents_frame.setStyleSheet(
            "QFrame#StartupDiagnosticsIncidentsFrame {"
            f"background: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
            "}"
        )
        self._summary_frame.setStyleSheet(
            "QFrame#StartupDiagnosticsSummaryFrame {"
            "background: transparent;"
            "border: none;"
            "}"
        )

        tile_style = (
            "QFrame#StartupDiagnosticsSummaryTile {"
            f"background: {floating_surface_rgba()};"
            f"border: 1px solid {floating_surface_border_rgba()};"
            "border-radius: 7px;"
            "}"
        )
        text_style = (
            f"color: {floating_surface_text_color().name()};background: transparent;"
        )
        for tile in self._summary_frame.findChildren(QFrame):
            if tile.objectName() == "StartupDiagnosticsSummaryTile":
                tile.setStyleSheet(tile_style)
        for label in self._summary_frame.findChildren(QLabel):
            label.setStyleSheet(text_style)
        for icon in self._summary_frame.findChildren(
            StartupDiagnosticsSummaryTileIconWidget
        ):
            icon.update()


class StartupDiagnosticsGlyphWidget(QWidget):
    """Paint the qfluent warning glyph used for recoverable startup diagnostics."""

    def __init__(self, size: int, parent: QWidget | None = None) -> None:
        """Store the square warning glyph size."""

        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the warning glyph into the widget bounds."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        drawIcon(
            InfoBarIcon.WARNING,
            painter,
            QRectF(0, 0, self.width(), self.height()),
            theme=Theme.LIGHT,
        )

    @staticmethod
    def icon_path() -> str:
        """Return the qfluent warning asset used by the modal header."""

        return cast("str", InfoBarIcon.WARNING.path(Theme.LIGHT))


class StartupDiagnosticsSummaryTileIconWidget(QWidget):
    """Paint one icon inside a startup diagnostics summary tile."""

    def __init__(
        self,
        icon: object,
        size: int,
        parent: QWidget | None = None,
    ) -> None:
        """Store the tile icon and fixed square size."""

        super().__init__(parent)
        self._icon = icon
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the tile icon into the widget bounds."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        attributes: dict[str, object] = {}
        if self._icon is FIF.HIDE:
            attributes["fill"] = floating_surface_text_color().name()
        drawIcon(
            self._icon,
            painter,
            QRectF(0, 0, self._size, self._size),
            theme=Theme.LIGHT,
            **attributes,
        )

    def icon_path(self) -> str | None:
        """Return the icon resource path when the icon exposes one."""

        path = getattr(self._icon, "path", None)
        if not callable(path):
            return None
        return cast("str", path(Theme.LIGHT))


def _resolve_parent(parent: object | None) -> QWidget:
    """Return a QWidget parent because qfluent mask dialogs require one."""

    if isinstance(parent, QWidget) and isValid(parent):
        return parent
    active_window = QApplication.activeWindow()
    if isinstance(active_window, QWidget) and isValid(active_window):
        return active_window
    global _FALLBACK_PARENT
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1024, 768)
    return _FALLBACK_PARENT


def _dialog_max_height(parent: QWidget) -> int:
    """Return a dialog height cap that fits inside the parent."""

    return max(_MIN_DIALOG_HEIGHT, parent.height() - _DIALOG_HEIGHT_MARGIN)


def _header_text_column_width(icon_width: int) -> int:
    """Return the available modal width for header text labels."""

    return (
        _DIALOG_WIDTH
        - (_CONTENT_SIDE_MARGIN * 2)
        - icon_width
        - _HEADER_ICON_TEXT_SPACING
    )


def _header_glyph_size(title: QLabel, message: QLabel) -> int:
    """Return a warning glyph size matching the visible two-row text bounds."""

    ink_top, ink_bottom = _header_text_ink_bounds(title, message)
    return max(16, ink_bottom - ink_top - 1)


def _header_text_ink_bounds(title: QLabel, message: QLabel) -> tuple[int, int]:
    """Return the visible text bounds of the two-line header stack."""

    title_ink_top, title_ink_bottom = _label_ink_bounds(title, 0)
    message_top = title.fontMetrics().height() + _HEADER_TEXT_SPACING
    message_ink_top, message_ink_bottom = _label_ink_bounds(message, message_top)
    return min(title_ink_top, message_ink_top), max(
        title_ink_bottom,
        message_ink_bottom,
    )


def _header_icon_top_offset(title: QLabel, message: QLabel, icon_size: int) -> int:
    """Return the icon top offset inside the two-row grid-spanning cell."""

    title_top = 0
    message_bottom = (
        title.fontMetrics().height() + _HEADER_TEXT_SPACING + message.height()
    )
    cell_center = (title_top + message_bottom) / 2
    ink_top, ink_bottom = _header_text_ink_bounds(title, message)
    ink_center = (ink_top + ink_bottom) / 2
    centered_top = round(cell_center - (icon_size / 2))
    return max(0, centered_top + int(ink_center - cell_center))


def _label_ink_bounds(label: QLabel, top: int) -> tuple[int, int]:
    """Return vertical text ink bounds relative to the header origin."""

    metrics = label.fontMetrics()
    rect = metrics.tightBoundingRect(label.text() or " ")
    ink_top = top + metrics.ascent() + rect.top()
    return ink_top, ink_top + rect.height()


def _count_severity(
    incidents: Sequence[StartupDiagnosticsIncidentView],
    severity: str,
) -> int:
    """Return the number of incidents matching one severity."""

    return sum(1 for incident in incidents if _severity_value(incident) == severity)


def _incident_title(incident: StartupDiagnosticsIncidentView) -> str:
    """Return one row title that includes severity without fatal styling."""

    return f"{_severity_value(incident).title()}: {incident.title}"


def _incident_detail_widgets(
    incident: StartupDiagnosticsIncidentView,
    parent: QWidget,
    open_url: Callable[[str], None],
) -> tuple[QWidget, ...]:
    """Return concise visible detail rows for one startup incident."""

    widgets: list[QWidget] = []

    source = CaptionLabel(_source_location_text(incident), parent)
    source.setWordWrap(True)
    widgets.append(source)

    cause = BodyLabel(incident.cause or incident.message, parent)
    cause.setWordWrap(True)
    widgets.append(cause)

    action = BodyLabel(
        incident.remediation or "Review the startup report.",
        parent,
    )
    action.setWordWrap(True)
    widgets.append(action)

    links = _incident_link_buttons(incident, parent, open_url)
    if links:
        widgets.append(_incident_link_row(links, parent))
    return tuple(widgets)


def _source_location_text(incident: StartupDiagnosticsIncidentView) -> str:
    """Return one compact source/location display line."""

    source = incident.source or "unknown"
    location = _mapping_text(incident.values, "location")
    return f"{source} • {location}" if location else source


def _summary_tile(
    *,
    label: str,
    value: str,
    icon: object,
    parent: QWidget,
) -> QFrame:
    """Return one rounded horizontal summary count tile."""

    panel = QFrame(parent)
    panel.setObjectName("StartupDiagnosticsSummaryTile")
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    layout = QGridLayout(panel)
    layout.setContentsMargins(10, 9, 10, 9)
    layout.setHorizontalSpacing(8)
    layout.setVerticalSpacing(0)

    icon_widget = StartupDiagnosticsSummaryTileIconWidget(icon, 16, panel)
    icon_widget.setObjectName("StartupDiagnosticsSummaryTileIcon")
    layout.addWidget(icon_widget, 0, 0, Qt.AlignmentFlag.AlignVCenter)

    label_widget = CaptionLabel(label, panel)
    layout.addWidget(label_widget, 0, 1, Qt.AlignmentFlag.AlignVCenter)

    value_widget = StrongBodyLabel(value, panel)
    layout.addWidget(value_widget, 0, 2, Qt.AlignmentFlag.AlignRight)

    layout.setColumnStretch(1, 1)
    return panel


def _incident_link_buttons(
    incident: StartupDiagnosticsIncidentView,
    parent: QWidget,
    open_url: Callable[[str], None],
) -> tuple[PushButton, ...]:
    """Return compact external link buttons for one incident."""

    buttons: list[PushButton] = []
    repository_url = _repository_url(incident)
    if repository_url:
        buttons.append(
            _incident_link_button(
                text="Repository",
                icon=FIF.GITHUB,
                url=repository_url,
                parent=parent,
                open_url=open_url,
            )
        )
    issues_url = _issues_url(incident)
    if issues_url:
        buttons.append(
            _incident_link_button(
                text="Report issue",
                icon=FIF.FEEDBACK,
                url=issues_url,
                parent=parent,
                open_url=open_url,
            )
        )
    return tuple(buttons)


def _incident_link_row(links: tuple[PushButton, ...], parent: QWidget) -> QWidget:
    """Return one compact row of external incident link buttons."""

    row = QWidget(parent)
    row.setObjectName("StartupDiagnosticsIncidentLinks")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for button in links:
        layout.addWidget(button)
    layout.addStretch(1)
    return row


def _incident_link_button(
    *,
    text: str,
    icon: object,
    url: str,
    parent: QWidget,
    open_url: Callable[[str], None],
) -> PushButton:
    """Return one secondary incident link button."""

    button = PushButton(text, parent)
    button.setIcon(icon)
    button.setFixedHeight(26)
    button.setToolTip(url)
    button.clicked.connect(_open_url_handler(url, open_url))
    return button


def _open_url_handler(url: str, open_url: Callable[[str], None]) -> Callable[[], None]:
    """Return a Qt slot that opens one captured URL."""

    def handler() -> None:
        open_url(url)

    return handler


def _repository_url(incident: StartupDiagnosticsIncidentView) -> str | None:
    """Return the trusted repository URL for one incident when present."""

    return _mapping_text(incident.values, "repository_url")


def _issues_url(incident: StartupDiagnosticsIncidentView) -> str | None:
    """Return the trusted issue tracker URL for one incident when present."""

    return _mapping_text(incident.values, "issues_url")


def _open_external_url(url: str) -> bool:
    """Open a trusted external URL through the desktop shell."""

    return bool(QDesktopServices.openUrl(QUrl(url)))


def _mapping_text(values: Mapping[str, object], key: str) -> str | None:
    """Return one non-empty string metadata value from an incident mapping."""

    value = values.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _severity_value(incident: StartupDiagnosticsIncidentView) -> str:
    """Return a display-ready severity value from a domain enum or string."""

    value = getattr(incident.severity, "value", incident.severity)
    return str(value)


def _clear_layout(layout: QLayout) -> None:
    """Hide widgets owned by a nested layout removed from the footer."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.hide()
        nested_layout = item.layout()
        if nested_layout is not None:
            _clear_layout(nested_layout)


def _rgba_string(color: tuple[int, int, int, int]) -> str:
    """Return a Qt stylesheet rgba value from an RGBA tuple."""

    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


__all__ = ["StartupDiagnosticsDialog", "StartupDiagnosticsGlyphWidget"]
