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

"""Contract tests for editor-panel bottom-only overscroll behavior."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from substitute.presentation.editor.panel.widgets.scroll_surface import (
    EditorPanelScrollModel,
    EditorPanelScrollSurface,
)


def ensure_qapp() -> QApplication:
    """Return the live QApplication instance, creating one when needed."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 3) -> None:
    """Flush pending Qt layout and timer events."""

    for _ in range(cycles):
        app.processEvents()


def build_scroll_area(
    section_heights: tuple[int, ...],
) -> tuple[EditorPanelScrollSurface, QWidget, list[QWidget]]:
    """Create one editor scroll surface with fixed-height sections."""

    scroll_area = EditorPanelScrollSurface()
    scroll_area.setWidgetResizable(True)
    content = QWidget(scroll_area)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    sections: list[QWidget] = []
    for index, height in enumerate(section_heights):
        section = QLabel(f"section-{index}", content)
        section.setFixedHeight(height)
        layout.addWidget(section)
        sections.append(section)
    scroll_area.setWidget(content)
    return scroll_area, content, sections


def test_scroll_model_exposes_bottom_overscroll_without_top_slack() -> None:
    """Overflow content should gain bottom virtual overscroll without top slack."""

    model = EditorPanelScrollModel()
    model.set_viewport_height(200)
    model.set_content_height(480)
    model.set_content_present(True)

    assert model.should_show_scrollbar() is True
    assert model.overscroll_top() == 0
    assert model.overscroll_bottom() == 100
    assert model.rest_scroll_value() == 0
    assert model.max_scroll_value() == 380
    assert model.content_y_to_scroll_value(0) == 0


def test_bottom_overscroll_keeps_top_flush_and_bottom_scrollable() -> None:
    """The content top should clamp at zero while the bottom can scroll past content."""

    app = ensure_qapp()
    scroll_area, content, sections = build_scroll_area((120, 120, 120, 120))
    scroll_area.resize(320, 200)
    scroll_area.show()
    process_events(app)
    scroll_area._refresh_metrics()
    process_events(app)

    scroll_bar = scroll_area.verticalScrollBar()
    scroll_bar.setValue(0)
    process_events(app)

    assert scroll_area.overscroll_top() == 0
    assert scroll_area.overscroll_bottom() == 100
    assert content.pos().y() == 0
    assert sections[0].mapTo(scroll_area.viewport(), QPoint(0, 0)).y() == 0

    scroll_bar.setValue(scroll_bar.maximum())
    process_events(app)

    last_section_bottom = sections[-1].mapTo(scroll_area.viewport(), QPoint(0, 0)).y()
    last_section_bottom += sections[-1].height()

    assert scroll_bar.maximum() == 380
    assert last_section_bottom == 100


def test_bottom_overscroll_stays_disabled_when_content_fits() -> None:
    """Fitting content should not gain a synthetic scrollbar range."""

    app = ensure_qapp()
    scroll_area, _content, _sections = build_scroll_area((120,))
    scroll_area.resize(320, 200)
    scroll_area.show()
    process_events(app)
    scroll_area._refresh_metrics()
    process_events(app)

    assert scroll_area.overscroll_bottom() == 0
    assert scroll_area.verticalScrollBar().maximum() == 0


def test_scroll_surface_emits_metrics_refreshed_after_refresh() -> None:
    """Scroll metrics refresh should expose a deterministic layout-ready signal."""

    app = ensure_qapp()
    scroll_area, _content, _sections = build_scroll_area((120, 120, 120))
    refresh_count = 0

    def _record_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1

    scroll_area.metrics_refreshed.connect(_record_refresh)
    scroll_area.resize(320, 200)
    scroll_area.show()
    scroll_area.schedule_metrics_refresh()
    process_events(app)

    assert refresh_count >= 1


def test_scroll_surface_coalesces_repeated_refresh_requests() -> None:
    """Repeated refresh requests before the event loop should run once."""

    app = ensure_qapp()
    scroll_area, _content, _sections = build_scroll_area((120, 120, 120))
    refresh_count = 0

    def _record_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1

    scroll_area.metrics_refreshed.connect(_record_refresh)
    scroll_area.resize(320, 200)
    scroll_area.show()
    scroll_area.schedule_metrics_refresh()
    scroll_area.schedule_metrics_refresh()
    scroll_area.schedule_metrics_refresh()
    process_events(app)

    assert refresh_count == 1
    assert scroll_area._coalesced_refresh_count >= 2


def test_scroll_surface_refresh_metrics_now_runs_without_waiting_for_timer() -> None:
    """Synchronous refresh should settle metrics before the next event-loop turn."""

    app = ensure_qapp()
    scroll_area, _content, _sections = build_scroll_area((120, 120, 120))
    refresh_count = 0

    def _record_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1

    scroll_area.metrics_refreshed.connect(_record_refresh)
    scroll_area.resize(320, 200)
    scroll_area.show()
    process_events(app)
    scroll_area.schedule_metrics_refresh()

    scroll_area.refresh_metrics_now()

    assert refresh_count == 1
    assert scroll_area._refresh_pending is False
    assert scroll_area.verticalScrollBar().maximum() > 0


def test_scroll_surface_skips_unchanged_metrics_signature() -> None:
    """Unchanged metrics should not emit another layout-ready signal."""

    app = ensure_qapp()
    scroll_area, _content, _sections = build_scroll_area((120, 120, 120))
    refresh_count = 0

    def _record_refresh() -> None:
        nonlocal refresh_count
        refresh_count += 1

    scroll_area.metrics_refreshed.connect(_record_refresh)
    scroll_area.resize(320, 200)
    scroll_area.show()
    scroll_area.schedule_metrics_refresh()
    process_events(app)

    first_refresh_count = refresh_count
    scroll_area.schedule_metrics_refresh()
    process_events(app)

    assert first_refresh_count == 1
    assert refresh_count == first_refresh_count
    assert scroll_area._signature_skip_count >= 1
