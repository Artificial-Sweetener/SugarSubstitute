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

"""Render structured Comfy-style error reports in a qfluent modal dialog."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
    set_localized_text,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedSubtitleLabel,
)
from sugarsubstitute_shared.localization import ApplicationText

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QRectF, Qt, QPropertyAnimation
from PySide6.QtGui import QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    InfoBarIcon,
    MessageBoxBase,
    PlainTextEdit,
    StrongBodyLabel,
    Theme,
    drawIcon,
)
from shiboken6 import isValid

from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
)
from substitute.presentation.motion import (
    ENTER_EASING_CURVE,
    EXIT_EASING_CURVE,
    restart_property_animation,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
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


class ErrorReportDialog(MessageBoxBase):  # type: ignore[misc]
    """Show a user-friendly error summary with complete diagnostic details."""

    def __init__(
        self,
        *,
        report: ErrorReport,
        report_text: str,
        open_console: Callable[[], None] | None = None,
        parent: object | None = None,
    ) -> None:
        """Build the modal error report dialog."""

        parent_widget = _resolve_parent(parent)
        super().__init__(parent_widget)
        del open_console
        self._report = report
        self._report_text = report_text
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
        self._build_details()
        self._build_actions()
        self._sync_body_height()
        self._apply_theme()
        connect_theme_refresh(self, self._apply_theme)

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
        self._body_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self._body_layout.setSpacing(_CONTENT_SPACING)
        self._body_scroll_area.setWidget(self._body_widget)
        self.viewLayout.addWidget(self._body_scroll_area)

    def _build_header(self) -> None:
        """Create the title and short explanatory header."""

        header = QWidget(self.widget)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QGridLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(_HEADER_ICON_TEXT_SPACING)
        layout.setVerticalSpacing(_HEADER_TEXT_SPACING)

        self._title_label = LocalizedSubtitleLabel(self._report.title, header)
        self._message_label = LocalizedBodyLabel(self._report.message, header)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        icon_size = _header_glyph_size(self._title_label, self._message_label)
        header_text_width = _header_text_column_width(icon_size)
        self._title_label.setMaximumWidth(header_text_width)
        self._message_label.setWordWrap(True)
        self._message_label.setMinimumWidth(header_text_width)
        self._message_label.setMaximumWidth(header_text_width)
        self._message_label.setMinimumHeight(self._message_label.sizeHint().height())
        icon_cell = QWidget(header)
        icon_cell.setFixedWidth(icon_size)
        icon_layout = QVBoxLayout(icon_cell)
        icon_layout.setContentsMargins(
            0,
            _header_icon_top_offset(self._title_label, self._message_label, icon_size),
            0,
            0,
        )
        icon_layout.setSpacing(0)
        self._icon_widget = ReportSeverityGlyphWidget(
            size=icon_size,
            severity=self._report.severity,
            parent=icon_cell,
        )
        icon_layout.addWidget(self._icon_widget, 0, Qt.AlignmentFlag.AlignTop)
        icon_layout.addStretch(1)
        layout.addWidget(icon_cell, 0, 0, 2, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._title_label, 0, 1, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._message_label, 1, 1, Qt.AlignmentFlag.AlignLeft)
        layout.setColumnStretch(1, 1)
        self._body_layout.addWidget(header)

    def _build_summary(self) -> None:
        """Create compact key-value context rows for the default view."""

        self._summary_frame = QFrame(self.widget)
        self._summary_frame.setObjectName("SubstituteErrorSummaryFrame")
        layout = QGridLayout(self._summary_frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(6)

        rows = self._summary_rows()
        for row_index, (label, value) in enumerate(rows):
            label_widget = LocalizedCaptionLabel(label, self._summary_frame)
            value_widget = StrongBodyLabel(value, self._summary_frame)
            value_widget.setWordWrap(True)
            layout.addWidget(label_widget, row_index, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(value_widget, row_index, 1)
        layout.setColumnStretch(1, 1)
        self._body_layout.addWidget(self._summary_frame)

    def _build_details(self) -> None:
        """Create the collapsed report body and reveal button."""

        self._details_button = LocalizedPushButton(app_text("Show report"), self.widget)
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
        """Create modal footer buttons."""

        self.buttonGroup.show()
        self.buttonGroup.setFixedHeight(68)
        self._clear_button_layout()
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonLayout.setContentsMargins(24, 16, 24, 16)
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.addStretch(1)

        self._copy_button = LocalizedPushButton(
            app_text("Copy report"), self.buttonGroup
        )
        self._copy_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._copy_button.setMinimumWidth(_ACTION_BUTTON_MINIMUM_WIDTH)
        self._copy_button.clicked.connect(self._copy_report)
        self.buttonLayout.addWidget(self._copy_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._close_button = LocalizedPrimaryPushButton(
            app_text("Close"), self.buttonGroup
        )
        self._close_button.setFixedHeight(_ACTION_BUTTON_HEIGHT)
        self._close_button.setMinimumWidth(_CLOSE_BUTTON_MINIMUM_WIDTH)
        self._close_button.clicked.connect(self.accept)
        self.buttonLayout.addWidget(
            self._close_button, 0, Qt.AlignmentFlag.AlignVCenter
        )

    def _clear_button_layout(self) -> None:
        """Remove qfluent's default action widgets from the footer layout."""

        while self.buttonLayout.count():
            item = self.buttonLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
            nested_layout = item.layout()
            if nested_layout is not None:
                _clear_layout(nested_layout)

    def _summary_rows(self) -> tuple[tuple[ApplicationText, str], ...]:
        """Return compact metadata rows for the error summary."""

        node = self._report.node
        rows: list[tuple[ApplicationText, str]] = [
            (app_text("Stage"), self._report.stage),
            (
                app_text("Workflow"),
                self._report.workflow_id
                or render_application_text(app_text("unknown")),
            ),
        ]
        if self._report.prompt_id:
            rows.append((app_text("Prompt"), self._report.prompt_id))
        if node is not None:
            rows.append((app_text("Node"), _node_label(node.node_id, node.node_type)))
        if self._report.exception_type:
            rows.append((app_text("Exception"), self._report.exception_type))
        if self._report.kind == ErrorReportKind.PROMPT_VALIDATION:
            count = (
                len(self._report.prompt_validation.node_errors)
                if self._report.prompt_validation
                else 0
            )
            rows.append((app_text("Node errors"), str(count)))
        if self._report.kind == ErrorReportKind.CUBE_LIBRARY_DRIFT:
            rows.append(
                (
                    app_text("Affected cubes"),
                    str(_affected_cube_count(self._report)),
                )
            )
        return tuple(rows)

    def _toggle_details(self) -> None:
        """Show or hide the complete report body."""

        self._details_visible = not self._details_visible
        set_localized_text(
            self._details_button,
            "Hide report" if self._details_visible else "Show report",
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
        """Size the scroll body naturally unless the parent height forces scrolling."""

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
        """Copy the complete report text to the clipboard."""

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self._report_text)

    def _apply_theme(self) -> None:
        """Refresh WinUI-style summary and icon colors for the current theme."""

        fill = _rgba_string(winui_card_fill_color())
        border = _rgba_string(winui_card_border_color())
        self._summary_frame.setStyleSheet(
            "QFrame#SubstituteErrorSummaryFrame {"
            f"background: {fill};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
            "}"
        )


def _node_label(node_id: str | None, node_type: str | None) -> str:
    """Return a compact node identity label."""

    if node_id and node_type:
        return f"{node_id} - {node_type}"
    return node_id or node_type or "unknown"


def _header_text_column_width(icon_width: int) -> int:
    """Return the available modal width for header text labels."""

    return (
        _DIALOG_WIDTH
        - (_CONTENT_SIDE_MARGIN * 2)
        - icon_width
        - _HEADER_ICON_TEXT_SPACING
    )


class ReportSeverityGlyphWidget(QWidget):
    """Draw qfluent's WinUI severity glyph without an InfoBar surface."""

    def __init__(
        self,
        *,
        size: int,
        severity: DiagnosticSeverity,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the fixed-size modal header glyph."""

        super().__init__(parent)
        self._glyph_size = size
        self._severity = severity
        self.setFixedSize(size, size)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        """Paint the qfluent glyph that matches the report severity."""

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        drawIcon(
            _severity_icon(self._severity),
            painter,
            QRectF(0, 0, self._glyph_size, self._glyph_size),
            theme=Theme.LIGHT,
        )

    def icon_path(self) -> str:
        """Return the qfluent asset used by the modal header."""

        return cast("str", _severity_icon(self._severity).path(Theme.LIGHT))


def _severity_icon(severity: DiagnosticSeverity) -> InfoBarIcon:
    """Return the qfluent InfoBar icon for one diagnostic severity."""

    if severity == DiagnosticSeverity.WARNING:
        return InfoBarIcon.WARNING
    if severity == DiagnosticSeverity.INFO:
        return InfoBarIcon.INFORMATION
    return InfoBarIcon.ERROR


def _affected_cube_count(report: ErrorReport) -> int:
    """Return the Cube Library drift count from report operation context."""

    context = report.operation_context
    if context is None:
        return 0
    value = context.values.get("message_count")
    if isinstance(value, int):
        return value
    return 0


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
    """Return a modal height cap that keeps the dialog inside its parent."""

    return max(_MIN_DIALOG_HEIGHT, parent.height() - _DIALOG_HEIGHT_MARGIN)


def _header_glyph_size(title: QLabel, message: QLabel) -> int:
    """Return an error glyph size matching the visible two-row text bounds."""

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


__all__ = ["ErrorReportDialog", "ReportSeverityGlyphWidget"]
