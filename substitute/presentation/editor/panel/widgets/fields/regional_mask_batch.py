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

"""Render ordered regional masks as labeled CuteCanvas preview rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QColor, QEnterEvent, QPaintEvent, QPainter
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionFocusRect,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import PushButton  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    translate_application_text,
)

from substitute.presentation.editor.panel.widgets.fields.thumbnail_preview_surface import (
    ThumbnailPreviewSurface,
)
from substitute.presentation.editor.panel.widgets.fields.mask_visual_opacity import (
    MaskVisualOpacityControl,
)
from substitute.presentation.editor.panel.widgets.fields.regional_mask_selection_animation import (
    RegionalMaskSelectionAnimationTarget,
    RegionalMaskSelectionAnimator,
)
from substitute.presentation.regional import region_color

_SELECTED_PREVIEW_WIDTH = 288
_COMPACT_PREVIEW_BOUND = QSize(44, 44)
_PREVIEW_CORNER_RADIUS = 6


@runtime_checkable
class _RegionalMaskPreview(Protocol):
    """Expose the shared live-preview sizing and lifecycle boundary."""

    def aspect_fit_size(
        self,
        *,
        maximum_width: int,
        maximum_height: int | None = None,
    ) -> QSize:
        """Return source-aspect geometry inside the supplied bounds."""

    def set_preferred_width(self, preferred_width: int) -> None:
        """Resize one live viewport without changing its source aspect."""

    def close(self) -> bool:
        """Release the mounted CuteCanvas viewport."""

    def deleteLater(self) -> None:  # noqa: N802
        """Schedule Qt-owned preview deletion."""


class _RegionalMaskRow(QPushButton):
    """Own one selectable label and one shared thumbnail preview surface."""

    hoverChanged = Signal(int, bool)

    def __init__(self, label: str, index: int, parent: QWidget) -> None:
        """Create one normal-text row with its immutable ordered position."""

        super().__init__(parent)
        self._region_index = index
        self._selected = False
        self._linked_hovered = False
        self._color = QColor()
        self._live_preview: QWidget | None = None
        self.setProperty("region_selected", False)
        self.setProperty("region_linked_hovered", False)
        self.setText("")
        self.setFlat(True)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(10, 6, 8, 6)
        self._layout.setHorizontalSpacing(8)
        self._layout.setVerticalSpacing(5)
        self._label = QLabel(label, self)
        self._label.setObjectName("regionalMaskLabel")
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._preview_surface = ThumbnailPreviewSurface(
            thumbnail_width=_SELECTED_PREVIEW_WIDTH,
            corner_radius=_PREVIEW_CORNER_RADIUS,
            shadow_margin=4,
            parent=self,
        )
        self._preview_surface.clicked.connect(self.click)
        self._apply_layout()

    @property
    def region_index(self) -> int:
        """Return this row's immutable ordered mask position."""

        return self._region_index

    def set_label(self, label: str) -> None:
        """Replace the compact row label without rebuilding its live preview."""

        self._label.setText(label)
        self.setAccessibleName(label)

    def set_region_color(self, color: QColor) -> None:
        """Set the authored identity color used by this row's leading rail."""

        self._color = QColor(color)
        self.update()

    def set_selected_immediately(self, selected: bool) -> None:
        """Apply one selection state without transitional motion."""

        if selected == self._selected:
            return
        self._apply_selection_state(selected)
        self._sync_preview_extent()
        self.updateGeometry()
        self.update()

    def prepare_selection_transition(
        self,
        selected: bool,
    ) -> RegionalMaskSelectionAnimationTarget | None:
        """Prepare one aspect-preserving row transition for the shared clock."""

        if selected == self._selected:
            return None
        preview = self._live_preview
        start_width = preview.sizeHint().width() if preview is not None else 0
        self._apply_selection_state(selected)
        if not isinstance(preview, _RegionalMaskPreview):
            self.updateGeometry()
            self.update()
            return None
        target_width = self._target_preview_size(preview).width()

        def apply_progress(progress: float) -> None:
            """Interpolate preview scale while preserving the source aspect."""

            width = max(1, round(start_width + (target_width - start_width) * progress))
            preview.set_preferred_width(width)
            self._preview_surface.refresh_live_content_size()
            self._notify_layout_change()

        def finish() -> None:
            """Settle exact target geometry after animation or interruption."""

            preview.set_preferred_width(target_width)
            self._preview_surface.refresh_live_content_size()
            self._notify_layout_change()

        return RegionalMaskSelectionAnimationTarget(apply_progress, finish)

    def set_linked_hovered(self, hovered: bool) -> None:
        """Show linked SEP or canvas hover without changing selection."""

        if hovered == self._linked_hovered:
            return
        self._linked_hovered = hovered
        self.setProperty("region_linked_hovered", hovered)
        self.update()

    def set_live_preview(self, preview: QWidget) -> None:
        """Mount one regular mask-loader CuteCanvas preview in this row."""

        if not isinstance(preview, QWidget) or not isinstance(
            preview, _RegionalMaskPreview
        ):
            raise TypeError("preview must support regional mask preview sizing")
        self.release_preview()
        self._live_preview = preview
        self._preview_surface.set_live_content(preview)
        self._sync_preview_extent()

    def live_preview(self) -> QWidget | None:
        """Return the currently mounted CuteCanvas preview widget."""

        return self._live_preview

    def sizeHint(self) -> QSize:  # noqa: N802
        """Return the child-layout extent instead of native text-button geometry."""

        return self._layout.sizeHint().expandedTo(QSize(1, self.minimumHeight()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Keep compact and expanded preview contents inside row negotiation."""

        return self._layout.minimumSize().expandedTo(QSize(1, self.minimumHeight()))

    def release_preview(self) -> None:
        """Close and retire this row's viewport before row replacement."""

        preview = self._live_preview
        if preview is None:
            return
        self._live_preview = None
        self._preview_surface.remove_live_content()
        preview.close()
        preview.deleteLater()

    def enterEvent(self, event: QEnterEvent) -> None:
        """Publish transient entry into this ordered region row."""

        super().enterEvent(event)
        self.hoverChanged.emit(self._region_index, True)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        """Publish transient exit from this ordered region row."""

        super().leaveEvent(event)
        self.hoverChanged.emit(self._region_index, False)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint theme-derived selection chrome and the authored color rail."""

        painter = QPainter(self)
        palette = self.palette()
        if self._selected or self._linked_hovered or self.underMouse():
            background = QColor(palette.color(palette.ColorRole.Highlight))
            background.setAlpha(34 if self._selected else 22)
            painter.fillRect(self.rect(), background)
        rail_color = (
            self._color if self._color.isValid() else palette.highlight().color()
        )
        painter.fillRect(0, 0, 4, self.height(), rail_color)
        if self.hasFocus():
            focus = QStyleOptionFocusRect()
            focus.initFrom(self)
            focus.rect = self.rect().adjusted(5, 1, -1, -1)
            self.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_FrameFocusRect,
                focus,
                painter,
                self,
            )
        painter.end()
        event.accept()

    def _apply_layout(self) -> None:
        """Place one large preview below the label or one compact preview beside it."""

        self._layout.removeWidget(self._label)
        self._layout.removeWidget(self._preview_surface)
        if self._selected:
            self._layout.addWidget(self._label, 0, 0, 1, 2)
            self._layout.addWidget(
                self._preview_surface,
                1,
                0,
                1,
                2,
                Qt.AlignmentFlag.AlignHCenter,
            )
            self.setMinimumHeight(48)
        else:
            self._layout.addWidget(
                self._preview_surface,
                0,
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
            self._layout.addWidget(
                self._label,
                0,
                1,
                Qt.AlignmentFlag.AlignVCenter,
            )
            self.setMinimumHeight(44)

    def _apply_selection_state(self, selected: bool) -> None:
        """Project selection into row semantics and target layout placement."""

        self._selected = selected
        self.setChecked(selected)
        self.setProperty("region_selected", selected)
        self._apply_layout()

    def _sync_preview_extent(self) -> None:
        """Apply row state to the one shared responsive preview widget."""

        preview = self._live_preview
        if not isinstance(preview, _RegionalMaskPreview):
            return
        preview.set_preferred_width(self._target_preview_size(preview).width())
        self._preview_surface.refresh_live_content_size()

    def _target_preview_size(self, preview: _RegionalMaskPreview) -> QSize:
        """Return source-aspect preview geometry for the current row state."""

        return preview.aspect_fit_size(
            maximum_width=(
                _SELECTED_PREVIEW_WIDTH
                if self._selected
                else _COMPACT_PREVIEW_BOUND.width()
            ),
            maximum_height=(
                None if self._selected else _COMPACT_PREVIEW_BOUND.height()
            ),
        )

    def _notify_layout_change(self) -> None:
        """Propagate animated preview geometry through both owning layouts."""

        self._layout.invalidate()
        self.updateGeometry()
        parent = self.parentWidget()
        parent_layout = parent.layout() if parent is not None else None
        if parent is not None and parent_layout is not None:
            parent_layout.invalidate()
            parent.updateGeometry()
        self.update()


class RegionalMaskBatchEditor(QFrame):
    """Display one expanded mask preview and compact related mask rows."""

    regionActionRequested = Signal(str, str, str)
    regionHoverChanged = Signal(object)
    selectionAnimationFinished = Signal()
    visualOpacityChanged = Signal(str, str, float)
    visualOpacityCommitted = Signal(str, str, float, float)

    def __init__(
        self,
        *,
        cube_alias: str,
        node_name: str,
        values: list[str],
        labels: list[str | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build ordered rows from the current authored Comfy list value."""

        super().__init__(parent)
        self.cube_alias = cube_alias
        self.node_name = node_name
        self._values = list(values)
        self._labels = _normalized_labels(labels, len(values))
        self._selected_index = 0 if values else -1
        self._hovered_index: int | None = None
        self._rows: list[_RegionalMaskRow] = []
        self._selection_animator = RegionalMaskSelectionAnimator(self)
        self._selection_animator.finished.connect(self.selectionAnimationFinished)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._rows_host = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        self._layout.addWidget(self._rows_host)
        self.opacity_control = MaskVisualOpacityControl(self)
        self.opacity_control.opacityChanged.connect(self._publish_visual_opacity)
        self.opacity_control.opacityCommitted.connect(
            self._publish_visual_opacity_commit
        )
        self._layout.addWidget(self.opacity_control)
        action_row = QWidget(self)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)
        self._add_button = PushButton(app_text("Add"), action_row)
        self._add_button.setProperty("region_add_button", True)
        self._add_button.clicked.connect(self._add_region)
        action_layout.addWidget(self._add_button)
        self._import_button = PushButton(app_text("Choose Mask"), action_row)
        self._import_button.setProperty("region_import_button", True)
        self._import_button.clicked.connect(self._import_regions)
        action_layout.addWidget(self._import_button)
        self._remove_button = PushButton(app_text("Remove"), action_row)
        self._remove_button.setProperty("region_remove_button", True)
        self._remove_button.clicked.connect(self._remove_selected_region)
        action_layout.addWidget(self._remove_button)
        self._layout.addWidget(action_row)
        self._rebuild_rows()

    @property
    def selected_index(self) -> int:
        """Return the currently expanded ordered mask index."""

        return self._selected_index

    @property
    def region_count(self) -> int:
        """Return the number of authored ordered regions shown by the widget."""

        return len(self._values)

    @property
    def selection_animation_running(self) -> bool:
        """Return whether selected rows are currently exchanging prominence."""

        return self._selection_animator.is_running

    def select_region(self, index: int) -> None:
        """Expand one mask preview and contract every other row."""

        if not 0 <= index < len(self._rows):
            return
        if index == self._selected_index and self._rows[index].property(
            "region_selected"
        ):
            return
        self._selection_animator.complete()
        previous_index = self._selected_index
        self._selected_index = index
        self._remove_button.setEnabled(bool(self._rows))
        targets = []
        if 0 <= previous_index < len(self._rows):
            previous_target = self._rows[previous_index].prepare_selection_transition(
                False
            )
            if previous_target is not None:
                targets.append(previous_target)
        selected_target = self._rows[index].prepare_selection_transition(True)
        if selected_target is not None:
            targets.append(selected_target)
        self._selection_animator.start(targets)

    def set_hovered_region(self, index: int | None) -> None:
        """Render linked hover without changing the expanded selection."""

        resolved_index = (
            index if index is not None and 0 <= index < len(self._rows) else None
        )
        if resolved_index == self._hovered_index:
            return
        self._hovered_index = resolved_index
        for row_index, row in enumerate(self._rows):
            row.set_linked_hovered(row_index == resolved_index)

    def set_regions(
        self,
        values: list[str],
        *,
        labels: list[str | None] | None = None,
        selected_index: int | None,
    ) -> None:
        """Render one authoritative ordered collection without discarding stable views."""

        next_labels = _normalized_labels(labels, len(values))
        next_selected_index = (
            selected_index
            if selected_index is not None and 0 <= selected_index < len(values)
            else (0 if values else -1)
        )
        same_row_count = len(values) == len(self._rows)
        self._values = list(values)
        self._labels = next_labels
        previous_selected_index = self._selected_index
        self._hovered_index = None
        if not same_row_count:
            self._selected_index = next_selected_index
            self._rebuild_rows()
            return
        self._selected_index = previous_selected_index
        self._refresh_row_labels_and_colors()
        if self._rows:
            self.select_region(next_selected_index)
        else:
            self._remove_button.setEnabled(False)

    def set_region_names(self, labels: list[str | None]) -> None:
        """Refresh SEP-derived labels without replacing any mask previews."""

        self._labels = _normalized_labels(labels, len(self._values))
        self._refresh_row_labels_and_colors()

    def set_visual_opacity(self, opacity: float) -> None:
        """Project the workflow-owned visual opacity into this node card."""

        self.opacity_control.set_opacity(opacity)

    def set_live_preview(self, index: int, preview: QWidget) -> bool:
        """Mount one CuteCanvas mask preview at its ordered batch position."""

        if not 0 <= index < len(self._rows):
            return False
        self._selection_animator.complete()
        self._rows[index].set_live_preview(preview)
        return True

    def live_preview(self, index: int) -> QWidget | None:
        """Return one ordered row's currently mounted preview."""

        if not 0 <= index < len(self._rows):
            return None
        return self._rows[index].live_preview()

    def _add_region(self) -> None:
        """Request durable region materialization without inventing local state."""

        self.regionActionRequested.emit(self.cube_alias, self.node_name, "@region:add")

    def _publish_visual_opacity(self, opacity: float) -> None:
        """Publish node identity with one user-authored presentation value."""

        self.visualOpacityChanged.emit(self.cube_alias, self.node_name, opacity)

    def _publish_visual_opacity_commit(self, before: float, after: float) -> None:
        """Publish one completed node-level opacity gesture."""

        self.visualOpacityCommitted.emit(
            self.cube_alias,
            self.node_name,
            before,
            after,
        )

    def _import_regions(self) -> None:
        """Choose arbitrary mask files and append one ordered region per file."""

        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            translate_application_text("Choose Mask"),
            "",
            translate_application_text("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        next_index = len(self._values)
        for offset, path in enumerate(paths):
            payload = json.dumps(
                [next_index + offset, path],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.regionActionRequested.emit(
                self.cube_alias,
                self.node_name,
                f"@region:import:{payload}",
            )

    def _remove_selected_region(self) -> None:
        """Publish exact removal intent and await authoritative collection state."""

        index = self._selected_index
        if not 0 <= index < len(self._values):
            return
        self.regionActionRequested.emit(
            self.cube_alias,
            self.node_name,
            f"@region:remove:{index}",
        )

    def _rebuild_rows(self) -> None:
        """Recreate ordered rows while explicitly retiring obsolete viewports."""

        self._selection_animator.complete()
        for row in self._rows:
            row.release_preview()
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        total = len(self._values)
        for index, value in enumerate(self._values):
            row = _RegionalMaskRow(
                _row_label(value, index, self._labels[index]),
                index,
                self._rows_host,
            )
            row.setProperty("region_index", index)
            row.set_region_color(region_color(index, total))
            row.hoverChanged.connect(self._handle_row_hover)
            row.clicked.connect(
                lambda _checked=False, selected=index: self._select_and_emit(selected)
            )
            self._rows.append(row)
            self._rows_layout.addWidget(row)
        if self._rows:
            self._selected_index = min(self._selected_index, len(self._rows) - 1)
            for row_index, row in enumerate(self._rows):
                row.set_selected_immediately(row_index == self._selected_index)
            self._remove_button.setEnabled(True)
        else:
            self._remove_button.setEnabled(False)

    def _refresh_row_labels_and_colors(self) -> None:
        """Apply names and palette colors while preserving row and preview identity."""

        total = len(self._rows)
        for index, row in enumerate(self._rows):
            row.set_label(_row_label(self._values[index], index, self._labels[index]))
            row.set_region_color(region_color(index, total))
            row.set_linked_hovered(False)

    def _select_and_emit(self, index: int) -> None:
        """Request matching durable canvas and collection selection."""

        self.regionActionRequested.emit(
            self.cube_alias,
            self.node_name,
            f"@region:select:{index}",
        )

    def _handle_row_hover(self, index: int, hovered: bool) -> None:
        """Publish transient row hover and keep local linked styling in sync."""

        next_index = index if hovered else None
        self.set_hovered_region(next_index)
        self.regionHoverChanged.emit(next_index)


def _normalized_labels(
    labels: list[str | None] | None,
    count: int,
) -> list[str | None]:
    """Return exactly one optional authored SEP name per mask position."""

    source = labels or []
    return [source[index] if index < len(source) else None for index in range(count)]


def _row_label(value: str, index: int, region_name: str | None) -> str:
    """Prefer an authored SEP name and otherwise preserve the mask's existing label."""

    authored_name = "" if region_name is None else region_name.strip()
    if authored_name:
        return authored_name
    stem = Path(value).stem.strip()
    return stem or f"#{index + 1}"


__all__ = ["RegionalMaskBatchEditor"]
