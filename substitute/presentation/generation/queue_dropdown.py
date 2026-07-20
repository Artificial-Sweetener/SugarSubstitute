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

"""Show generation queue state in a qfluent acrylic dropdown."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedStrongBodyLabel,
)

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ScrollArea  # type: ignore[import-untyped]

try:
    from qfluentwidgets import BodyLabel, StrongBodyLabel
except ImportError:  # pragma: no cover - lightweight test stubs
    BodyLabel = QLabel
    StrongBodyLabel = QLabel
from qfluentwidgets.components.material import (  # type: ignore[import-untyped]
    AcrylicFlyout,
    AcrylicFlyoutViewBase,
)
from qfluentwidgets.components.widgets.flyout import (  # type: ignore[import-untyped]
    FlyoutAnimationType,
)

from substitute.application.generation import (
    GenerationQueueJob,
    GenerationQueueStateChange,
)
from substitute.presentation.generation.queue_list_view import (
    QueueDisplayItem,
    QueueJobRowView,
    queue_job_display_items,
    queue_job_row_view,
)
from substitute.presentation.generation.queue_rows_view import GenerationQueueRowsView
from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)

if TYPE_CHECKING:
    from substitute.application.generation import GenerationJobQueueService


class GenerationQueueDropdownView(AcrylicFlyoutViewBase):  # type: ignore[misc]
    """Render queue rows inside an acrylic flyout view."""

    cancelRequested = Signal(str)
    removeRequested = Signal(str)
    moveRequested = Signal(str, int)
    openSnapshotRequested = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        """Create the fixed-size dropdown layout."""

        super().__init__(parent)
        qt = cast(Any, Qt)
        qframe = cast(Any, QFrame)
        self.setFixedWidth(360)
        self.setMaximumHeight(420)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 14)
        self._layout.setSpacing(10)

        title = LocalizedStrongBodyLabel(app_text("Generation queue"), self)
        title.setObjectName("GenerationQueueTitle")
        self._layout.addWidget(title)

        self._empty_state = QWidget(self)
        empty_state_layout = QVBoxLayout(self._empty_state)
        empty_state_layout.setContentsMargins(0, 0, 0, 0)
        empty_state_layout.setSpacing(0)

        self._empty_label = LocalizedBodyLabel(
            app_text("No queued jobs"), self._empty_state
        )
        self._empty_label.setAlignment(qt.AlignCenter)
        self._empty_label.setMinimumHeight(88)
        empty_state_layout.addStretch(1)
        empty_state_layout.addWidget(self._empty_label)
        empty_state_layout.addStretch(1)
        self._layout.addWidget(self._empty_state, 1)

        self._scroll_area = ScrollArea(self)
        configure_qfluent_scroll_surface(self._scroll_area)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(qframe.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(qt.ScrollBarAlwaysOff)

        self._rows_view = GenerationQueueRowsView(
            surface_mode="flyout",
            scroll_area=self._scroll_area,
            parent=self._scroll_area,
        )
        self._scroll_area.setWidget(self._rows_view)
        self._scroll_area.enableTransparentBackground()
        self._layout.addWidget(self._scroll_area, 1)

        self._rows_view.cancelRequested.connect(self.cancelRequested)
        self._rows_view.removeRequested.connect(self.removeRequested)
        self._rows_view.openSnapshotRequested.connect(self.openSnapshotRequested)
        self._rows_view.moveRequested.connect(self.moveRequested)
        self.set_rows(())

    def addWidget(
        self,
        widget: QWidget,
        stretch: int = 0,
        align: object = cast(Any, Qt).AlignLeft,
    ) -> None:
        """Support the qfluent flyout view extension contract."""

        self._layout.addWidget(widget, stretch, cast(Any, align))

    def set_rows(self, rows: tuple[QueueJobRowView, ...]) -> None:
        """Replace the visible queue rows."""

        self._empty_state.setVisible(not rows)
        self._scroll_area.setVisible(bool(rows))
        self._rows_view.set_rows(rows)

    def set_items(self, items: tuple[QueueDisplayItem, ...]) -> None:
        """Replace visible queue display items."""

        rows = tuple(item for item in items if isinstance(item, QueueJobRowView))
        self._empty_state.setVisible(not rows)
        self._scroll_area.setVisible(bool(rows))
        self._rows_view.set_items(items)

    def update_row(self, row: QueueJobRowView) -> bool:
        """Update one visible queue row without rebuilding the flyout layout."""

        return self._rows_view.update_row(row)


class GenerationQueueDropdown:
    """Bind queue service state and cancel intents to an acrylic dropdown."""

    def __init__(
        self,
        queue_service: "GenerationJobQueueService",
        *,
        parent: QWidget,
        open_snapshot_requested: Callable[[str], None] | None = None,
    ) -> None:
        """Subscribe to queue state and remember the flyout parent."""

        self._queue_service = queue_service
        self._parent = parent
        self._open_snapshot_requested = open_snapshot_requested
        self._jobs: tuple[GenerationQueueJob, ...] = ()
        self._flyout: AcrylicFlyout | None = None
        queue_service.add_observer(self._on_jobs_changed)

    def dispose(self) -> None:
        """Detach queue observers and close the flyout before shell disposal."""

        self.close()
        remove_observer = getattr(self._queue_service, "remove_observer", None)
        if callable(remove_observer):
            remove_observer(self._on_jobs_changed)

    def toggle_for(self, target: QWidget) -> None:
        """Open the dropdown below target, or close it when already visible."""

        if self.is_visible():
            self.close()
            return
        self.show_for(target)

    def show_for(self, target: QWidget) -> None:
        """Show a fresh acrylic flyout for the current queue state."""

        view = GenerationQueueDropdownView(self._parent)
        view.cancelRequested.connect(self._queue_service.cancel_job)
        view.removeRequested.connect(self._queue_service.remove_terminal_job)
        view.moveRequested.connect(self._queue_service.move_pending_job)
        if self._open_snapshot_requested is not None:
            view.openSnapshotRequested.connect(self._open_snapshot_requested)
        view.set_items(queue_job_display_items(self._jobs))
        self._flyout = AcrylicFlyout.make(
            view,
            target,
            self._parent,
            FlyoutAnimationType.DROP_DOWN,
            True,
        )
        self._flyout.closed.connect(self._handle_flyout_closed)

    def close(self) -> None:
        """Close the visible queue dropdown."""

        if self._flyout is None:
            return
        self._flyout.close()

    def is_visible(self) -> bool:
        """Return whether the dropdown flyout is currently visible."""

        return self._flyout is not None and self._flyout.isVisible()

    def _on_jobs_changed(self, event: GenerationQueueStateChange) -> None:
        """Store queue state and refresh the open view when possible."""

        jobs = event.jobs
        self._jobs = jobs
        if self._flyout is None:
            return
        view = getattr(self._flyout, "view", None)
        if isinstance(view, GenerationQueueDropdownView):
            if event.change_kind == "progress" and event.changed_job_id is not None:
                row = queue_job_row_view(jobs, event.changed_job_id)
                if row is not None and view.update_row(row):
                    return
            view.set_items(queue_job_display_items(jobs))

    def _handle_flyout_closed(self) -> None:
        """Forget closed flyouts so the next click can reopen cleanly."""

        self._flyout = None


__all__ = ["GenerationQueueDropdown", "GenerationQueueDropdownView"]
