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

"""Render a persistent generation queue panel for the workspace side host."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import ScrollArea, TransparentToolButton  # type: ignore[import-untyped]

try:
    from qfluentwidgets import BodyLabel, StrongBodyLabel
except ImportError:  # pragma: no cover - lightweight test stubs
    BodyLabel = QLabel
    StrongBodyLabel = QLabel

from substitute.application.generation import (
    GenerationQueueJob,
    GenerationQueueStateChange,
)
from substitute.presentation.generation.queue_counts import (
    pending_generation_queue_job_count,
)
from substitute.presentation.generation.queue_list_view import (
    QueueDisplayItem,
    QueueJobRowView,
    queue_job_display_items,
    queue_job_row_view,
)
from substitute.presentation.generation.queue_rows_view import GenerationQueueRowsView
from substitute.presentation.resources.app_icon import AppIcon
from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)

if TYPE_CHECKING:
    from substitute.application.generation import GenerationJobQueueService


class GenerationQueuePanel(QWidget):
    """Display live generation queue state in a persistent side panel."""

    cancelRequested = Signal(str)
    removeRequested = Signal(str)
    openSnapshotRequested = Signal(str)
    moveRequested = Signal(str, int)
    hideRequested = Signal()

    def __init__(
        self,
        queue_service: "GenerationJobQueueService",
        *,
        open_snapshot_requested: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create panel widgets and subscribe to queue changes."""

        super().__init__(parent)
        qt = cast(Any, Qt)
        self._queue_service = queue_service
        self._open_snapshot_requested = open_snapshot_requested
        self._jobs: tuple[GenerationQueueJob, ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._header = QWidget(self)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._title_label = StrongBodyLabel(
            self._header_title(pending_job_count=0),
            self._header,
        )
        self._title_label.setObjectName("GenerationQueuePanelTitle")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch(1)

        self._hide_panel_button = TransparentToolButton(
            AppIcon.PANEL_RIGHT_20_FILLED,
            self._header,
        )
        self._hide_panel_button.setObjectName("GenerationQueuePanelHideButton")
        self._hide_panel_button.setIconSize(QSize(20, 20))
        self._hide_panel_button.setToolTip("Hide full queue panel")
        self._hide_panel_button.clicked.connect(lambda: self.hideRequested.emit())
        header_layout.addWidget(self._hide_panel_button)
        layout.addWidget(self._header)

        self._empty_state = QWidget(self)
        empty_state_layout = QVBoxLayout(self._empty_state)
        empty_state_layout.setContentsMargins(0, 0, 0, 0)
        empty_state_layout.setSpacing(0)

        self._empty_label = BodyLabel("No queued jobs", self._empty_state)
        self._empty_label.setAlignment(qt.AlignCenter)
        self._empty_label.setMinimumHeight(88)
        empty_state_layout.addStretch(1)
        empty_state_layout.addWidget(self._empty_label)
        empty_state_layout.addStretch(1)
        layout.addWidget(self._empty_state, 1)

        self._scroll_area = ScrollArea(self)
        configure_qfluent_scroll_surface(self._scroll_area)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(qt.ScrollBarAlwaysOff)

        self._rows_view = GenerationQueueRowsView(
            surface_mode="panel",
            scroll_area=self._scroll_area,
            parent=self._scroll_area,
        )
        self._scroll_area.setWidget(self._rows_view)
        self._scroll_area.enableTransparentBackground()
        layout.addWidget(self._scroll_area, 1)

        self.cancelRequested.connect(queue_service.cancel_job)
        self.removeRequested.connect(queue_service.remove_terminal_job)
        self.moveRequested.connect(queue_service.move_pending_job)
        if open_snapshot_requested is not None:
            self.openSnapshotRequested.connect(open_snapshot_requested)
        self._rows_view.cancelRequested.connect(self.cancelRequested)
        self._rows_view.removeRequested.connect(self.removeRequested)
        self._rows_view.openSnapshotRequested.connect(self.openSnapshotRequested)
        self._rows_view.moveRequested.connect(self.moveRequested)
        queue_service.add_observer(self._on_jobs_changed)

    def dispose(self) -> None:
        """Detach queue observers before the owning shell is disposed."""

        remove_observer = getattr(self._queue_service, "remove_observer", None)
        if callable(remove_observer):
            remove_observer(self._on_jobs_changed)

    def set_rows(self, rows: tuple[QueueJobRowView, ...]) -> None:
        """Replace the visible queue rows."""

        self._empty_state.setVisible(not rows)
        self._scroll_area.setVisible(bool(rows))
        self._rows_view.set_rows(rows)

    def set_items(self, items: tuple[QueueDisplayItem, ...]) -> None:
        """Replace the visible queue display items."""

        rows = tuple(item for item in items if isinstance(item, QueueJobRowView))
        self._empty_state.setVisible(not rows)
        self._scroll_area.setVisible(bool(rows))
        self._rows_view.set_items(items)

    def _on_jobs_changed(self, event: GenerationQueueStateChange) -> None:
        """Refresh row models after queue state changes."""

        jobs = event.jobs
        self._jobs = jobs
        self._title_label.setText(
            self._header_title(
                pending_job_count=pending_generation_queue_job_count(jobs),
            )
        )
        if event.change_kind == "progress" and event.changed_job_id is not None:
            row = queue_job_row_view(jobs, event.changed_job_id)
            if row is not None and self._rows_view.update_row(row):
                return
        self.set_items(queue_job_display_items(jobs))

    @staticmethod
    def _header_title(*, pending_job_count: int) -> str:
        """Return the expanded queue panel title with the live pending count."""

        return f"Generation Queue :: {pending_job_count} Pending Jobs"


__all__ = ["GenerationQueuePanel"]
