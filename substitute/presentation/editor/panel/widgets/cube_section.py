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

"""Build passive cube-section widgets for the editor panel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEvent,
    QRect,
    QSize,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CheckableMenu,
    MenuIndicatorType,
    SubtitleLabel,
)
from qfluentwidgets import FluentIcon as FIF

from shiboken6 import isValid

from substitute.presentation.editor.panel.cube_section_title import cube_section_title
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
    MasonryGridLayout,
)
from substitute.presentation.editor.panel.widgets.cube_title_label import (
    CubeTitleLabel,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    EDITOR_ROW_BODY_SPACING,
    EDITOR_ROW_HEIGHT,
    EDITOR_ROW_HORIZONTAL_MARGINS,
    EDITOR_ROW_ICON_SIZE,
    EDITOR_ROW_SPACING,
)
from substitute.presentation.editor.panel.node_card.body_layout import (
    apply_card_body_layout_state,
    ensure_card_body_layout_state,
    resolve_card_body_expanded_height,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.utils.create_vbox import create_vbox
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    resolved_backdrop_mode,
    winui_card_border_color,
    winui_card_fill_color,
)
from substitute.presentation.widgets.menu_buttons import (
    ToggleTransparentDropDownToolButton,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_timing,
    log_warning,
)

if TYPE_CHECKING:
    from substitute.presentation.editor.panel.view import EditorPanel

_LOGGER = get_logger("presentation.editor.panel.widgets.cube_section")
_QT_WIDGET_MAXIMUM_SIZE = 16_777_215
_ISSUE_CARD_CORNER_RADIUS = 4.0
_ISSUE_CARD_ERROR_COLOR = QColor(210, 48, 58)
_UPDATING_WASH_ALPHA = 145
_UPDATING_ELLIPSIS_INTERVAL_MS = 350
_UPDATING_ELLIPSIS_STATES = ("", ".", "..", "...")


@dataclass(frozen=True, slots=True)
class CubeSectionWidgetParts:
    """Carry the passive widgets that make up one cube section."""

    widget: CubeSectionView
    grid_layout: MasonryGridLayout
    header_label: SubtitleLabel
    reveal_button: ToggleTransparentDropDownToolButton
    reveal_menu: CheckableMenu


def _is_live_widget(widget: object) -> bool:
    """Return whether one Qt widget can still be safely inspected."""

    try:
        return bool(isValid(widget))
    except TypeError:
        return True


def _is_string_line_edit_width_group_field(widget: QWidget) -> bool:
    """Return whether one widget participates in cube string width grouping."""

    input_metadata = widget.property("input_metadata")
    return (
        widget.__class__.__name__ == "LineEdit"
        and isinstance(input_metadata, Mapping)
        and input_metadata.get("type") == "STRING"
    )


class CubeSectionView(QWidget):
    """Wrap one cube heading and its card layout with height self-management."""

    cube_height_changed = Signal()

    def __init__(
        self,
        *,
        header_bar: QWidget,
        prompt_area: QVBoxLayout,
        grid_layout: MasonryGridLayout,
        parent: QWidget | None = None,
    ) -> None:
        """Build the cube-section wrapper around the supplied header and layouts."""

        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._header = header_bar
        self._prompt_area = prompt_area
        self._grid_layout = grid_layout
        self._resolved_height: int | None = None
        self._string_line_edit_width_sync_pending = False
        self._issue_severity: str | None = None
        self._issue_messages: tuple[str, ...] = ()

        self._content_container = QWidget(self)
        self._content_container.setAttribute(Qt.WA_TranslucentBackground)
        self._content_container.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Expanding,
        )

        content_layout = QVBoxLayout(self._content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(header_bar)
        if prompt_area.count():
            content_layout.addLayout(prompt_area)
        content_layout.addLayout(grid_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._content_container)

        self._content_container.show()
        self._issue_overlay = _CubeSectionIssueOverlay(self)
        self._issue_overlay.hide()
        self._updating_overlay = _CubeSectionUpdatingOverlay(self)
        self._updating_overlay.hide()

        for index in range(prompt_area.count()):
            item = prompt_area.itemAt(index)
            widget = item.widget()
            if isinstance(widget, PromptEditor):
                widget.resized.connect(self.defer_update_cube_height)

        self.defer_update_cube_height()
        self.defer_string_line_edit_width_group_sync()

    def sizeHint(self) -> QSize:
        """Return the latest resolved cube height as the preferred section height."""

        hint = super().sizeHint()
        if self._resolved_height is None:
            return hint
        return QSize(hint.width(), self._resolved_height)

    def minimumSizeHint(self) -> QSize:
        """Return the latest resolved cube height as the minimum section hint."""

        hint = super().minimumSizeHint()
        if self._resolved_height is None:
            return hint
        return QSize(hint.width(), self._resolved_height)

    def reveal_anchor_y(self) -> int:
        """Return the steady-state section-local anchor for cube navigation."""

        header = self._header
        if not isValid(header):
            return 0
        try:
            return header.mapTo(self, header.rect().center()).y()
        except (RuntimeError, TypeError, AttributeError):
            return 0

    def node_card_order(self) -> tuple[str, ...]:
        """Return semantic node identities in authoritative masonry order."""

        ordered: list[str] = []
        for index in range(self._grid_layout.count()):
            item = self._grid_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            node_name = widget.property("node_name") if widget is not None else None
            if isinstance(node_name, str):
                ordered.append(node_name)
        return tuple(ordered)

    def setIssueSeverity(self, severity: str | None) -> None:
        """Apply presentation-local runtime issue severity to the section."""

        normalized = severity if severity in {"error", "warning"} else None
        if normalized == self._issue_severity:
            return
        self._issue_severity = normalized
        self._issue_overlay.setIssueSeverity(normalized)
        self._issue_overlay.setVisible(normalized is not None)
        self._issue_overlay.raise_()
        self.update()

    def issueSeverity(self) -> str | None:
        """Return the current presentation-local issue severity."""

        return self._issue_severity

    def setIssueMessages(self, messages: tuple[str, ...]) -> None:
        """Store issue copy for contract tests and future accessible surfaces."""

        self._issue_messages = tuple(messages)

    def issueMessages(self) -> tuple[str, ...]:
        """Return the current issue message lines."""

        return self._issue_messages

    def showUpdatingWash(self, message: str = "Updating") -> None:
        """Show a local update wash while this cube section is being rebuilt."""

        self._updating_overlay.showUpdating(message)
        self._updating_overlay.raise_()

    def hideUpdatingWash(self) -> None:
        """Hide the local update wash."""

        self._updating_overlay.hideUpdating()

    def finalize_layout_for_reveal(self, *, reason: str) -> None:
        """Synchronously settle cube-section geometry before visible reveal."""

        self._finalize_layout(reason=reason)

    def finalize_layout_after_child_relayout(self, *, reason: str) -> None:
        """Refresh section geometry after a child field changes size."""

        self._finalize_layout(reason=reason)

    def update_cube_height(self) -> None:
        """Set minimum height from the grid layout size hint plus style padding."""

        extra_cube_padding = 36
        if self._grid_layout is None or not isValid(self._grid_layout):
            return
        try:
            self._grid_layout.invalidate()
            grid_height = self._grid_layout.sizeHint().height()
            content_layout = self._content_container.layout()
            content_height = (
                content_layout.sizeHint().height() if content_layout is not None else 0
            )
            height = max(grid_height + extra_cube_padding, content_height)
        except RuntimeError:
            return
        self._resolved_height = height
        self.setMinimumHeight(height)
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
        self.updateGeometry()
        self.cube_height_changed.emit()

    def defer_update_cube_height(self) -> None:
        """Defer a height recompute until the next event-loop turn."""

        QTimer.singleShot(0, self.update_cube_height)

    def defer_string_line_edit_width_group_sync(self) -> None:
        """Defer shared string line-edit width sync until layout has settled."""

        if self._string_line_edit_width_sync_pending:
            return
        self._string_line_edit_width_sync_pending = True
        QTimer.singleShot(0, self.sync_string_line_edit_width_group)

    def sync_string_line_edit_width_group(self) -> None:
        """Apply one shared width cap to visible single-line string inputs."""

        self._string_line_edit_width_sync_pending = False
        fields = self._string_line_edit_width_group_fields()
        if len(fields) < 2:
            self._release_string_line_edit_width_caps(fields)
            return
        self._release_string_line_edit_width_caps(fields)
        self._activate_string_line_edit_width_layouts(fields)
        visible_fields = [
            field
            for field in fields
            if _is_live_widget(field) and field.isVisibleTo(self) and field.width() > 0
        ]
        if len(visible_fields) < 2:
            return
        shared_width = min(field.width() for field in visible_fields)
        for field in visible_fields:
            field.setMinimumWidth(shared_width)
            field.setMaximumWidth(shared_width)
            self._set_string_line_edit_layout_alignment(
                field,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            field.updateGeometry()
        self._activate_string_line_edit_width_layouts(visible_fields)

    def _string_line_edit_width_group_fields(self) -> list[QWidget]:
        """Return live node-card single-line string inputs under this cube."""

        return [
            widget
            for widget in self.findChildren(QWidget)
            if _is_string_line_edit_width_group_field(widget)
        ]

    def _release_string_line_edit_width_caps(self, fields: list[QWidget]) -> None:
        """Remove prior shared caps so wider layouts can be measured."""

        for field in fields:
            if not _is_live_widget(field):
                continue
            if field.minimumWidth() != 0:
                field.setMinimumWidth(0)
            if field.maximumWidth() != _QT_WIDGET_MAXIMUM_SIZE:
                field.setMaximumWidth(_QT_WIDGET_MAXIMUM_SIZE)
            self._set_string_line_edit_layout_alignment(
                field,
                Qt.AlignmentFlag.AlignVCenter,
            )
            field.updateGeometry()

    def _set_string_line_edit_layout_alignment(
        self,
        field: QWidget,
        alignment: Qt.AlignmentFlag,
    ) -> None:
        """Set parent-layout alignment for a grouped string line edit."""

        parent = field.parentWidget()
        if parent is None or not _is_live_widget(parent):
            return
        layout = parent.layout()
        if layout is None:
            return
        layout.setAlignment(field, alignment)

    def _activate_string_line_edit_width_layouts(self, fields: list[QWidget]) -> None:
        """Ask affected layouts to recompute before measuring field widths."""

        layouts: list[QLayout] = []
        seen_layout_ids: set[int] = set()
        for widget in (self, self._content_container, *fields):
            if not _is_live_widget(widget):
                continue
            current: QWidget | None = widget
            while current is not None and _is_live_widget(current):
                layout = current.layout()
                if layout is not None and id(layout) not in seen_layout_ids:
                    seen_layout_ids.add(id(layout))
                    layouts.append(layout)
                if current is self:
                    break
                current = current.parentWidget()
        self._grid_layout.invalidate()
        for layout in layouts:
            layout.invalidate()
        for layout in reversed(layouts):
            layout.activate()

    def resizeEvent(self, event: object) -> None:
        """Refresh height after wrapper resizes."""

        super().resizeEvent(event)
        self._issue_overlay.setGeometry(self.rect())
        self._issue_overlay.raise_()
        self._updating_overlay.setGeometry(self.rect())
        self._updating_overlay.raise_()
        self.defer_update_cube_height()
        self.defer_string_line_edit_width_group_sync()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh height after wrapper becomes visible."""

        super().showEvent(event)
        self.defer_update_cube_height()
        self.defer_string_line_edit_width_group_sync()

    def event(self, event: object) -> bool:
        """Refresh height on layout requests from parent relayouts."""

        if event.type() == QEvent.LayoutRequest:
            self.defer_update_cube_height()
        return super().event(event)

    def _finalize_layout(self, *, reason: str) -> None:
        """Apply the authoritative section-local layout pass for one boundary."""

        if not _is_live_widget(self):
            log_warning(
                _LOGGER,
                "Skipped cube-section layout finalization for deleted widget",
                cube_alias="",
                reason=reason,
            )
            return
        cube_alias = self._cube_alias()
        width_before = self.width()
        height_before = self.height()
        started_at = perf_counter()
        try:
            content_layout = self._content_container.layout()
            self._invalidate_and_activate_layout(content_layout)
            refreshed_body_count = self._refresh_registered_card_body_layouts()
            synced_model_picker_card_count = self._sync_model_picker_width_groups()
            self.sync_string_line_edit_width_group()
            self._grid_layout.invalidate()
            self._invalidate_and_activate_layout(content_layout)
            self._invalidate_and_activate_layout(self._grid_layout)
            self.update_cube_height()
            self._warn_if_suspicious_masonry_geometry(reason=reason)
        except RuntimeError as error:
            log_warning(
                _LOGGER,
                "Failed cube-section layout finalization",
                cube_alias=cube_alias,
                reason=reason,
                width_before=width_before,
                height_before=height_before,
                error_type=type(error).__name__,
            )
            raise
        log_timing(
            _LOGGER,
            "Finalized cube-section layout",
            started_at=started_at,
            level="debug",
            cube_alias=cube_alias,
            reason=reason,
            width_before=width_before,
            height_before=height_before,
            resolved_height=self._resolved_height,
            masonry_item_count=self._grid_layout.count(),
            refreshed_body_count=refreshed_body_count,
            synced_model_picker_card_count=synced_model_picker_card_count,
            visible=self.isVisible(),
        )

    def _refresh_registered_card_body_layouts(self) -> int:
        """Resolve registered card-body heights without changing collapse state."""

        refreshed_body_count = 0
        for binding in self._registered_card_mode_bindings():
            content_body = getattr(binding, "content_body", None)
            content_layout = getattr(binding, "content_layout", None)
            if (
                content_body is None
                or content_layout is None
                or not _is_live_widget(content_body)
            ):
                continue
            content_layout.invalidate()
            expanded_height = resolve_card_body_expanded_height(
                content_layout=content_layout,
                allow_unbounded_height=bool(
                    getattr(binding, "allow_unbounded_content_height", False)
                ),
            )
            state = ensure_card_body_layout_state(
                content_body=content_body,
                expanded_height=expanded_height,
            )
            apply_card_body_layout_state(
                content_body=content_body,
                state=state,
                allow_unbounded_height=bool(
                    getattr(binding, "allow_unbounded_content_height", False)
                ),
                preserve_animation_height=True,
            )
            content_body.updateGeometry()
            refreshed_body_count += 1
        return refreshed_body_count

    def _sync_model_picker_width_groups(self) -> int:
        """Synchronously settle card-local model-picker width groups."""

        synced_card_count = 0
        for widget in self.findChildren(QWidget):
            sync_width_group = getattr(widget, "sync_model_picker_width_group", None)
            if not callable(sync_width_group) or not _is_live_widget(widget):
                continue
            sync_width_group()
            synced_card_count += 1
        return synced_card_count

    def _registered_card_mode_bindings(self) -> tuple[object, ...]:
        """Return registered node-card mode bindings for this cube section."""

        alias = self._cube_alias()
        if not alias:
            return ()
        current: QWidget | None = self
        while current is not None and _is_live_widget(current):
            controller = getattr(current, "_node_card_mode_controller", None)
            bindings_for_alias = getattr(controller, "bindings_for_alias", None)
            if callable(bindings_for_alias):
                return tuple(bindings_for_alias(alias))
            current = current.parentWidget()
        return ()

    def _cube_alias(self) -> str:
        """Return the cube alias assigned to this section when available."""

        alias = self.property("cube_alias")
        if isinstance(alias, str) and alias:
            return alias
        object_name = self.objectName()
        prefix = "CubePanel-"
        if object_name.startswith(prefix):
            return object_name[len(prefix) :]
        return ""

    @staticmethod
    def _invalidate_and_activate_layout(layout: QLayout | None) -> None:
        """Invalidate and synchronously activate one live Qt layout."""

        if layout is None or not _is_live_widget(layout):
            return
        layout.invalidate()
        layout.activate()

    def _warn_if_suspicious_masonry_geometry(self, *, reason: str) -> None:
        """Log visible masonry geometry that still resembles top-left overlap."""

        seen_geometries: set[tuple[int, int, int, int]] = set()
        duplicate_geometries: list[tuple[int, int, int, int]] = []
        visible_item_count = 0
        for index in range(self._grid_layout.count()):
            item = self._grid_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is None or not _is_live_widget(widget) or not widget.isVisible():
                continue
            visible_item_count += 1
            geometry = widget.geometry()
            signature = (
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
            )
            if geometry.width() <= 0 or geometry.height() <= 0:
                continue
            if signature in seen_geometries:
                duplicate_geometries.append(signature)
            seen_geometries.add(signature)
        if duplicate_geometries:
            log_warning(
                _LOGGER,
                "Detected duplicate visible masonry card geometry after finalization",
                cube_alias=self._cube_alias(),
                reason=reason,
                visible_item_count=visible_item_count,
                duplicate_geometry_count=len(duplicate_geometries),
            )
        if visible_item_count and self._resolved_height == 0:
            log_warning(
                _LOGGER,
                "Resolved zero-height cube section with visible masonry cards",
                cube_alias=self._cube_alias(),
                reason=reason,
                visible_item_count=visible_item_count,
            )


class _CubeSectionIssueOverlay(QWidget):
    """Paint a mouse-transparent issue wash over one cube section."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize the overlay as a non-interactive child widget."""

        super().__init__(parent)
        self._issue_severity: str | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def setIssueSeverity(self, severity: str | None) -> None:
        """Set the issue severity used by the overlay painter."""

        self._issue_severity = severity
        self.update()

    def paintEvent(self, event: object) -> None:
        """Paint the current issue wash."""

        _ = event
        if self._issue_severity != "error":
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(210, 48, 58, 170), 2))
        painter.setBrush(QColor(210, 48, 58, 34))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 190))
        painter.drawRoundedRect(0, 0, 4, max(0, self.height()), 2, 2)


class _CubeSectionUpdatingOverlay(QWidget):
    """Paint a local black update wash over one rebuilding cube section."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize the overlay as an input-blocking child widget."""

        super().__init__(parent)
        self._message = "Updating"
        self._ellipsis_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_UPDATING_ELLIPSIS_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_ellipsis)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            """
            QLabel {
                color: rgba(255, 255, 255, 230);
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }
            """
        )

    def showUpdating(self, message: str = "Updating") -> None:
        """Show this overlay and start the lightweight ellipsis animation."""

        self._message = message.strip() or "Updating"
        self._ellipsis_index = 0
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self._refresh_label()
        self.raise_()
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def hideUpdating(self) -> None:
        """Hide this overlay and stop the ellipsis animation."""

        self._timer.stop()
        self.hide()

    def resizeEvent(self, event: object) -> None:
        """Keep the update label centered when the section changes size."""

        super().resizeEvent(event)
        self._position_label()

    def paintEvent(self, event: object) -> None:
        """Paint the translucent black wash."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, _UPDATING_WASH_ALPHA))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

    def _advance_ellipsis(self) -> None:
        """Advance the update ellipsis by one frame."""

        self._ellipsis_index = (self._ellipsis_index + 1) % len(
            _UPDATING_ELLIPSIS_STATES
        )
        self._refresh_label()

    def _refresh_label(self) -> None:
        """Apply the current update message."""

        self._label.setText(
            f"{self._message}{_UPDATING_ELLIPSIS_STATES[self._ellipsis_index]}"
        )
        self._position_label()

    def _position_label(self) -> None:
        """Center the update label inside the overlay."""

        hint = self._label.sizeHint()
        self._label.setGeometry(
            (self.width() - hint.width()) // 2,
            (self.height() - hint.height()) // 2,
            hint.width(),
            hint.height(),
        )


class CubeSectionBuilder:
    """Compose passive cube-section widgets for an editor panel host."""

    def __init__(self, panel: EditorPanel) -> None:
        """Store the owning editor panel used for widget parenting and registries."""

        self._panel = panel

    def build_cube_section(self, route_key: str) -> CubeSectionWidgetParts:
        """Build the passive wrapper and layouts for one normal cube section."""

        build_started_at = perf_counter()
        panel = self._panel
        header_label = self._build_header_label(route_key)
        header_bar = QWidget()
        header_layout = QHBoxLayout(header_bar)
        shows_title = self._section_shows_title(route_key)
        header_layout.setContentsMargins(
            4,
            0,
            0,
            EDITOR_SECTION_GAP if shows_title else 0,
        )
        header_layout.setSpacing(6)
        header_layout.addWidget(header_label)
        header_label.setVisible(shows_title)
        header_layout.addItem(
            QSpacerItem(10, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        reveal_button = ToggleTransparentDropDownToolButton(FIF.VIEW, header_bar)
        reveal_button.setToolTip("Reveal Hidden Cards")
        reveal_menu = CheckableMenu(
            parent=header_bar,
            indicatorType=MenuIndicatorType.CHECK,
        )
        reveal_button.setMenu(reveal_menu)
        header_layout.addWidget(reveal_button)
        panel._cube_visibility_btns[route_key] = reveal_button
        panel._cube_visibility_menus[route_key] = reveal_menu

        prompt_area = create_vbox(spacing=0)
        grid_layout = MasonryGridLayout()
        widget = self._build_section_widget(
            route_key=route_key,
            header_bar=header_bar,
            prompt_area=prompt_area,
            grid_layout=grid_layout,
        )
        log_timing(
            _LOGGER,
            "Built passive cube-section widget shell",
            started_at=build_started_at,
            cube_alias=route_key,
            level="debug",
        )
        return CubeSectionWidgetParts(
            widget=widget,
            grid_layout=grid_layout,
            header_label=header_label,
            reveal_button=reveal_button,
            reveal_menu=reveal_menu,
        )

    def _section_shows_title(self, route_key: str) -> bool:
        """Return whether the projected graph state uses cube title chrome."""

        cube_states = getattr(self._panel, "_cube_states", None)
        cube_state = (
            cube_states.get(route_key) if isinstance(cube_states, Mapping) else None
        )
        return bool(getattr(cube_state, "shows_cube_section_title", True))

    def build_error_cube_widget(
        self,
        route_key: str,
        *,
        issue_lines: tuple[str, ...],
    ) -> CubeSectionView:
        """Build a passive cube section that shows recoverable issue details."""

        build_started_at = perf_counter()
        header_label = self._build_header_label(route_key)
        header_bar = QWidget()
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(4, 0, 0, EDITOR_SECTION_GAP)
        header_layout.setSpacing(6)
        header_layout.addWidget(header_label)
        header_layout.addItem(
            QSpacerItem(10, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        prompt_area = create_vbox(spacing=0)
        prompt_area.setContentsMargins(12, 4, 12, 14)
        prompt_area.addWidget(_build_runtime_issue_panel(issue_lines))
        widget = self._build_section_widget(
            route_key=route_key,
            header_bar=header_bar,
            prompt_area=prompt_area,
            grid_layout=MasonryGridLayout(),
        )
        widget.setIssueSeverity("error")
        widget.setIssueMessages(issue_lines)
        log_info(
            _LOGGER,
            "Built cube-section runtime issue widget",
            cube_alias=route_key,
            issue_count=len(issue_lines),
        )
        log_timing(
            _LOGGER,
            "Built passive cube-section issue widget",
            started_at=build_started_at,
            cube_alias=route_key,
            level="debug",
        )
        return widget

    def _build_header_label(self, route_key: str) -> SubtitleLabel:
        """Build and register the qfluent title label for one cube section."""

        cube_states = getattr(self._panel, "_cube_states", None)
        cube_state = (
            cube_states.get(route_key) if isinstance(cube_states, dict) else None
        )
        display_name = cube_section_title(route_key, cube_state)
        header_label = CubeTitleLabel(display_name)
        self._panel.cube_headers[route_key] = header_label
        return header_label

    def _build_section_widget(
        self,
        *,
        route_key: str,
        header_bar: QWidget,
        prompt_area: QVBoxLayout,
        grid_layout: MasonryGridLayout,
    ) -> CubeSectionView:
        """Build a section wrapper and attach shared panel height-refresh wiring."""

        panel = self._panel
        widget = CubeSectionView(
            header_bar=header_bar,
            prompt_area=prompt_area,
            grid_layout=grid_layout,
            parent=panel,
        )
        widget.setProperty("cube_alias", route_key)
        schedule_metrics_refresh = getattr(
            panel.scroll, "schedule_metrics_refresh", None
        )
        if callable(schedule_metrics_refresh):
            widget.cube_height_changed.connect(schedule_metrics_refresh)
        try:
            widget.setObjectName(f"CubePanel-{route_key}")
        except (AttributeError, RuntimeError, TypeError) as error:
            log_warning(
                _LOGGER,
                "Failed to name cube-section widget",
                cube_alias=route_key,
                error_type=type(error).__name__,
            )
        return widget


__all__ = [
    "CubeSectionBuilder",
    "CubeSectionWidgetParts",
    "CubeSectionView",
]


def _build_runtime_issue_panel(issue_lines: tuple[str, ...]) -> QWidget:
    """Build the visible inline error details for one cube section."""

    card = _RuntimeIssueNodeCard()
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 0, 0, 0)
    card_layout.setSpacing(0)

    header = _RuntimeIssueCardHeaderSurface(card)
    header.setFixedHeight(EDITOR_ROW_HEIGHT + (EDITOR_ROW_BODY_SPACING * 2))
    header.set_accordion_content_attached(True)
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(
        EDITOR_ROW_HORIZONTAL_MARGINS[0],
        EDITOR_ROW_BODY_SPACING,
        EDITOR_ROW_HORIZONTAL_MARGINS[2],
        EDITOR_ROW_BODY_SPACING,
    )
    header_layout.setSpacing(EDITOR_ROW_SPACING)

    glyph = _RuntimeIssueGlyph(header)
    glyph.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
    header_layout.addWidget(glyph)

    title = QLabel("Cube disabled", header)
    title.setObjectName("CubeRuntimeIssueTitle")
    title_font = title.font()
    title_font.setPointSize(14)
    title_font.setWeight(QFont.Weight.DemiBold)
    title.setFont(title_font)
    title.setWordWrap(True)
    header_layout.addWidget(title)
    header_layout.addStretch()
    card_layout.addWidget(header)

    content = _RuntimeIssueCardContentSurface(card)
    content.set_accordion_content_attached(True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(0)

    for index, line in enumerate(issue_lines):
        divider = _RuntimeIssueDivider(content)
        divider.setObjectName(
            "NodeCardTitleBodyDivider" if index == 0 else "NodeCardBodyDivider"
        )
        content_layout.addWidget(divider)
        detail_row = _RuntimeIssueDetailRow(content)
        detail_layout = QHBoxLayout(detail_row)
        detail_layout.setContentsMargins(
            EDITOR_ROW_HORIZONTAL_MARGINS[0],
            EDITOR_ROW_BODY_SPACING,
            EDITOR_ROW_HORIZONTAL_MARGINS[2],
            EDITOR_ROW_BODY_SPACING,
        )
        detail_layout.setSpacing(EDITOR_ROW_SPACING)
        detail = QLabel(line, detail_row)
        detail.setWordWrap(True)
        detail.setObjectName(
            "CubeRuntimeIssueAction"
            if index == len(issue_lines) - 1 and "ComfyUI" in line
            else "CubeRuntimeIssueDetail"
        )
        detail_layout.addWidget(detail)
        content_layout.addWidget(detail_row)
    card_layout.addWidget(content)
    return card


class _RuntimeIssueNodeCard(QWidget):
    """Compose issue header and body surfaces like an editor node card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the transparent issue-card root."""

        super().__init__(parent)
        self.setObjectName("CubeRuntimeIssueNodeCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)


class _RuntimeIssueCardSurface(QWidget):
    """Paint one red-washed node-card segment with attached-corner rules."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create one themed issue card paint surface."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content_attached = False
        connect_theme_refresh(self, self.update)

    def set_accordion_content_attached(self, attached: bool) -> None:
        """Set whether this surface is visually attached to another segment."""

        self._content_attached = attached
        self.update()

    def paintEvent(self, event: object) -> None:
        """Paint the card segment fill, required red wash, and issue stroke."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill_rect = self.rect()
        stroke_rect = self.rect().adjusted(0, 0, -1, -1)
        fill_path = self._paint_path(fill_rect)
        stroke_path = self._stroke_path(stroke_rect)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(*winui_card_fill_color(resolved_backdrop_mode(self))))
        painter.drawPath(fill_path)

        wash = QColor(_ISSUE_CARD_ERROR_COLOR)
        wash.setAlpha(42)
        painter.setBrush(wash)
        painter.drawPath(fill_path)

        stroke = QColor(*winui_card_border_color())
        painter.setPen(QPen(stroke, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(stroke_path)

        error_stroke = QColor(_ISSUE_CARD_ERROR_COLOR)
        error_stroke.setAlpha(142)
        painter.setPen(QPen(error_stroke, 1))
        painter.drawPath(stroke_path)

    def _paint_path(self, rect: QRect) -> QPainterPath:
        """Return the rounded segment path for the current attachment state."""

        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(_ISSUE_CARD_CORNER_RADIUS, width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)

        path.moveTo(x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.closeSubpath()
        return path

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the border path for this surface."""

        return self._paint_path(rect)

    def _top_left_radius(self, radius: float) -> float:
        """Return the top-left corner radius for this surface."""

        return radius

    def _top_right_radius(self, radius: float) -> float:
        """Return the top-right corner radius for this surface."""

        return radius

    def _bottom_right_radius(self, radius: float) -> float:
        """Return the bottom-right corner radius for this surface."""

        return radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Return the bottom-left corner radius for this surface."""

        return radius


class _RuntimeIssueCardHeaderSurface(_RuntimeIssueCardSurface):
    """Paint the issue card title segment like a node-card header."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the issue card header segment."""

        super().__init__(parent)
        self.setObjectName("NodeCardHeaderSurface")

    def paintEvent(self, event: object) -> None:
        """Paint the attached header and the red issue rail."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 190))
        painter.drawRoundedRect(0, 0, 4, max(0, self.height()), 2, 2)

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the header border path without the attached body seam."""

        if not self._content_attached:
            return super()._stroke_path(rect)
        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(_ISSUE_CARD_CORNER_RADIUS, width / 2.0, height / 2.0)
        top_left = self._top_left_radius(radius)
        top_right = self._top_right_radius(radius)

        path.moveTo(x, y + height)
        path.lineTo(x, y + top_left)
        if top_left:
            path.quadTo(x, y, x + top_left, y)
        path.lineTo(x + width - top_right, y)
        if top_right:
            path.quadTo(x + width, y, x + width, y + top_right)
        path.lineTo(x + width, y + height)
        return path

    def _bottom_right_radius(self, radius: float) -> float:
        """Square the bottom-right corner while body content is attached."""

        return 0.0 if self._content_attached else radius

    def _bottom_left_radius(self, radius: float) -> float:
        """Square the bottom-left corner while body content is attached."""

        return 0.0 if self._content_attached else radius


class _RuntimeIssueCardContentSurface(_RuntimeIssueCardSurface):
    """Paint the issue card body segment like a node-card content surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the issue card content segment."""

        super().__init__(parent)
        self.setObjectName("NodeCardContentSurface")

    def _top_left_radius(self, radius: float) -> float:
        """Square the top-left corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _top_right_radius(self, radius: float) -> float:
        """Square the top-right corner while attached to the header."""

        return 0.0 if self._content_attached else radius

    def _stroke_path(self, rect: QRect) -> QPainterPath:
        """Return the content border path without repainting the attached top edge."""

        if not self._content_attached:
            return super()._stroke_path(rect)
        path = QPainterPath()
        x = float(rect.x())
        y = float(rect.y())
        width = float(rect.width())
        height = float(rect.height())
        radius = min(_ISSUE_CARD_CORNER_RADIUS, width / 2.0, height / 2.0)
        bottom_right = self._bottom_right_radius(radius)
        bottom_left = self._bottom_left_radius(radius)

        path.moveTo(x + width, y)
        path.lineTo(x + width, y + height - bottom_right)
        if bottom_right:
            path.quadTo(x + width, y + height, x + width - bottom_right, y + height)
        path.lineTo(x + bottom_left, y + height)
        if bottom_left:
            path.quadTo(x, y + height, x, y + height - bottom_left)
        path.lineTo(x, y)
        return path


class _RuntimeIssueDetailRow(QWidget):
    """Render one body row inside the issue card content segment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a transparent row with node-card field-row height behavior."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumHeight(EDITOR_ROW_HEIGHT + (EDITOR_ROW_BODY_SPACING * 2))


class _RuntimeIssueDivider(QWidget):
    """Paint one node-card-style separator inside the issue body."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a one-pixel separator row."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(1)
        connect_theme_refresh(self, self.update)

    def paintEvent(self, event: object) -> None:
        """Paint the card divider with a subtle red issue tint."""

        _ = event
        painter = QPainter(self)
        base = QColor(*winui_card_border_color())
        issue = QColor(_ISSUE_CARD_ERROR_COLOR)
        issue.setAlpha(72)
        painter.setPen(QPen(base, 1))
        painter.drawLine(0, 0, self.width(), 0)
        painter.setPen(QPen(issue, 1))
        painter.drawLine(0, 0, self.width(), 0)


class _RuntimeIssueGlyph(QWidget):
    """Paint a compact error glyph for the issue node card title row."""

    def paintEvent(self, event: object) -> None:
        """Paint a small Fluent-style error indicator."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(210, 48, 58, 205))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(255, 255, 255, 235), 2))
        center_x = rect.center().x()
        painter.drawLine(center_x, rect.top() + 4, center_x, rect.bottom() - 6)
        painter.drawPoint(center_x, rect.bottom() - 3)
