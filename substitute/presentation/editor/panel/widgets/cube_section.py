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

"""Host one passive cube heading and its mounted node-card layout."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from shiboken6 import isValid

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.editor.panel.widgets.cube_section_layout_controller import (
    CubeSectionLayoutController,
)
from substitute.presentation.editor.panel.widgets.cube_section_overlays import (
    CubeSectionIssueOverlay,
    CubeSectionUpdatingOverlay,
)
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    MasonryGridLayout,
)
from substitute.presentation.editor.prompt_editor import PromptEditor


class CubeSectionView(QWidget):
    """Host one cube section while focused collaborators own its behavior."""

    cube_height_changed = Signal()

    @property
    def _resolved_height(self) -> int | None:
        """Expose resolved height for established diagnostics and tests."""

        return self._layout_controller.resolved_height

    def __init__(
        self,
        *,
        header_bar: QWidget,
        prompt_area: QVBoxLayout,
        grid_layout: MasonryGridLayout,
        parent: QWidget | None = None,
    ) -> None:
        """Build the cube-section wrapper around supplied header and layouts."""

        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._header = header_bar
        self._grid_layout = grid_layout
        self._issue_severity: str | None = None
        self._issue_messages: tuple[str, ...] = ()

        self._content_container = QWidget(self)
        self._content_container.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self._content_container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
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

        self._issue_overlay = CubeSectionIssueOverlay(self)
        self._issue_overlay.hide()
        self._updating_overlay = CubeSectionUpdatingOverlay(self)
        self._updating_overlay.hide()
        self._layout_controller = CubeSectionLayoutController(
            section=self,
            content_container=self._content_container,
            grid_layout=grid_layout,
            height_changed=self.cube_height_changed.emit,
        )
        for index in range(prompt_area.count()):
            item = prompt_area.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, PromptEditor):
                widget.resized.connect(self.defer_update_cube_height)
        self.defer_update_cube_height()
        self.defer_string_line_edit_width_group_sync()

    def sizeHint(self) -> QSize:
        """Return the latest resolved cube height as the preferred height."""

        hint = super().sizeHint()
        resolved_height = self._layout_controller.resolved_height
        return hint if resolved_height is None else QSize(hint.width(), resolved_height)

    def minimumSizeHint(self) -> QSize:
        """Return the latest resolved cube height as the minimum hint."""

        hint = super().minimumSizeHint()
        resolved_height = self._layout_controller.resolved_height
        return hint if resolved_height is None else QSize(hint.width(), resolved_height)

    def reveal_anchor_y(self) -> int:
        """Return the steady-state section-local anchor for cube navigation."""

        if not isValid(self._header):
            return 0
        try:
            return self._header.mapTo(self, self._header.rect().center()).y()
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

    def setIssueSeverity(self, severity: str | None) -> None:  # noqa: N802
        """Apply presentation-local runtime issue severity to the section."""

        normalized = severity if severity in {"error", "warning"} else None
        if normalized == self._issue_severity:
            return
        self._issue_severity = normalized
        self._issue_overlay.set_issue_severity(normalized)
        self._issue_overlay.setVisible(normalized is not None)
        self._issue_overlay.raise_()
        self.update()

    def issueSeverity(self) -> str | None:  # noqa: N802
        """Return the current presentation-local issue severity."""

        return self._issue_severity

    def setIssueMessages(self, messages: tuple[str, ...]) -> None:  # noqa: N802
        """Store issue copy for contract tests and accessible surfaces."""

        self._issue_messages = tuple(messages)

    def issueMessages(self) -> tuple[str, ...]:  # noqa: N802
        """Return the current issue message lines."""

        return self._issue_messages

    def showUpdatingWash(  # noqa: N802
        self,
        message: ApplicationText = app_text("Updating"),
    ) -> None:
        """Show a local update wash while this section is rebuilt."""

        self._updating_overlay.show_updating(message)
        self._updating_overlay.raise_()

    def hideUpdatingWash(self) -> None:  # noqa: N802
        """Hide the local update wash."""

        self._updating_overlay.hide_updating()

    def finalize_layout_for_reveal(self, *, reason: str) -> None:
        """Synchronously settle geometry before visible reveal."""

        self._layout_controller.finalize(reason=reason)

    def finalize_layout_after_child_relayout(self, *, reason: str) -> None:
        """Settle section geometry after an owned child's layout changes."""

        self._layout_controller.finalize(reason=reason)

    def update_cube_height(self) -> None:
        """Update section height through the layout owner."""

        self._layout_controller.update_height()

    def defer_update_cube_height(self) -> None:
        """Defer section height resolution through the layout owner."""

        self._layout_controller.defer_height_update()

    def defer_string_line_edit_width_group_sync(self) -> None:
        """Defer string field width synchronization."""

        self._layout_controller.defer_string_width_sync()

    def sync_string_line_edit_width_group(self) -> None:
        """Synchronize string field widths through the layout owner."""

        self._layout_controller.sync_string_width_group()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh overlays and layout after wrapper resize."""

        super().resizeEvent(event)
        self._issue_overlay.setGeometry(self.rect())
        self._issue_overlay.raise_()
        self._updating_overlay.setGeometry(self.rect())
        self._updating_overlay.raise_()
        self.defer_update_cube_height()
        self.defer_string_line_edit_width_group_sync()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh layout after the wrapper becomes visible."""

        super().showEvent(event)
        self.defer_update_cube_height()
        self.defer_string_line_edit_width_group_sync()


__all__ = ["CubeSectionView"]
