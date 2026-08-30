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

"""Verify generation queue labels and surfaces follow QFluent themes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from PySide6.QtWidgets import QLabel
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    Theme,
)

from substitute.presentation.generation.queue_dropdown import (
    GenerationQueueDropdownView,
)
from substitute.presentation.generation.queue_item_row import GenerationQueueItemRow
from substitute.presentation.generation.queue_list_view import QueueJobRowView
from substitute.presentation.generation.queue_panel import GenerationQueuePanel
from substitute.presentation.generation.queue_rows_view import GenerationQueueRowsView
from tests.presentation.theme.support import ThemeWidgetOwner

if TYPE_CHECKING:
    from substitute.application.generation import GenerationJobQueueService


class QueueService:
    """Provide queue operations needed by focused presentation construction."""

    def add_observer(self, _observer: object) -> None:
        """Accept queue observer registration."""

    def cancel_job(self, _job_id: str) -> None:
        """Accept cancel requests."""

    def remove_terminal_job(self, _job_id: str) -> None:
        """Accept remove requests."""

    def move_pending_job(self, _job_id: str, _target_index: int) -> None:
        """Accept move requests."""


def queue_row(
    job_id: str,
    *,
    title: str = "Workflow #001",
    subtitle: str = "Next",
    visual_role: Literal["active", "pending", "resolved"] = "pending",
) -> QueueJobRowView:
    """Return a queue row view for theme-awareness tests."""

    return QueueJobRowView(
        job_id=job_id,
        title=title,
        subtitle=subtitle,
        status="pending",
        action=None,
        visual_role=visual_role,
    )


def test_labels_use_qfluent_primitives(theme_owner: ThemeWidgetOwner) -> None:
    """Generation queue text uses QFluent labels rather than dark-only QSS."""

    with theme_owner.using_theme(Theme.DARK):
        panel = theme_owner.own(
            GenerationQueuePanel(cast("GenerationJobQueueService", QueueService()))
        )
        dropdown = theme_owner.own(GenerationQueueDropdownView())
        row = theme_owner.own(GenerationQueueItemRow(queue_row("a")))
        rows_view = theme_owner.own(GenerationQueueRowsView(surface_mode="panel"))
        rows_view.set_rows(
            (
                queue_row("pending", visual_role="pending"),
                queue_row(
                    "resolved",
                    title="Resolved workflow",
                    subtitle="Completed",
                    visual_role="resolved",
                ),
            )
        )

        assert panel.findChild(StrongBodyLabel, "GenerationQueuePanelTitle")
        assert isinstance(panel._empty_label, BodyLabel)
        assert dropdown.findChild(StrongBodyLabel, "GenerationQueueTitle")
        assert isinstance(dropdown._empty_label, BodyLabel)
        assert isinstance(row._title_label, StrongBodyLabel)
        assert isinstance(row._subtitle_label, CaptionLabel)
        separator = rows_view.findChild(QLabel, "GenerationQueueResolvedSeparator")
        assert isinstance(separator, CaptionLabel)


def test_row_surface_refreshes_on_theme_switch(
    theme_owner: ThemeWidgetOwner,
) -> None:
    """Generation queue row surfaces rebuild custom QSS after theme changes."""

    with theme_owner.using_theme(Theme.DARK):
        row = theme_owner.own(
            GenerationQueueItemRow(queue_row("a", visual_role="active"))
        )
        row.show()
        theme_owner.wait_until(row.isVisible)
        dark_style = row.styleSheet()
        dark_thumbnail_style = row._thumbnail_label.styleSheet()

        theme_owner.switch_theme(
            Theme.LIGHT,
            settled=lambda: (
                row.styleSheet() != dark_style
                and row._thumbnail_label.styleSheet() != dark_thumbnail_style
            ),
        )

        assert "rgba(255, 255, 255, 18)" not in row.styleSheet()
