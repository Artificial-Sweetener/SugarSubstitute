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

"""Contract tests for QFluent-owned theme awareness in custom widgets."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QLabel,
    QSpinBox,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    StrongBodyLabel,
    SubtitleLabel,
    Theme,
    setTheme,
)

from substitute.presentation.editor.panel.widgets.cube_section import CubeSectionBuilder
from substitute.presentation.generation.queue_dropdown import (
    GenerationQueueDropdownView,
)
from substitute.presentation.generation.queue_item_row import GenerationQueueItemRow
from substitute.presentation.generation.queue_list_view import QueueJobRowView
from substitute.presentation.generation.queue_panel import GenerationQueuePanel
from substitute.presentation.generation.queue_rows_view import GenerationQueueRowsView
from substitute.presentation.widgets import DoubleSpinBox, SpinBox
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.theme_switch_test_helpers import (
    dispose_widgets,
    fluent_theme,
    is_qfluent_managed,
    process_events,
)


def _show_spin_box_for_text_rect(widget: QAbstractSpinBox) -> None:
    """Show a spin box at the editor numeric-field size before geometry checks."""

    widget.setFixedSize(48, 33)
    widget.show()
    process_events()


if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real QFluent theme-awareness widget tests require non-xdist execution",
        allow_module_level=True,
    )


def test_substitute_spin_boxes_register_with_qfluent_spinbox_style() -> None:
    """Custom spin boxes should keep behavior while QFluent owns their styling."""

    with fluent_theme(Theme.DARK):
        raw_spin_box = QSpinBox()
        raw_double_spin_box = QDoubleSpinBox()
        raw_hidden_spin_box = QSpinBox()
        raw_hidden_double_spin_box = QDoubleSpinBox()
        raw_hidden_spin_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        raw_hidden_double_spin_box.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        spin_box = SpinBox()
        double_spin_box = DoubleSpinBox()
        try:
            for widget in (
                raw_spin_box,
                raw_double_spin_box,
                raw_hidden_spin_box,
                raw_hidden_double_spin_box,
                spin_box,
                double_spin_box,
            ):
                _show_spin_box_for_text_rect(widget)

            assert is_qfluent_managed(spin_box)
            assert is_qfluent_managed(double_spin_box)
            assert spin_box.property("transparent") is True
            assert double_spin_box.property("transparent") is True
            assert spin_box.property("symbolVisible") is True
            assert double_spin_box.property("symbolVisible") is True
            assert spin_box.sizeHint() == raw_spin_box.sizeHint()
            assert spin_box.minimumSizeHint() == raw_spin_box.minimumSizeHint()
            assert double_spin_box.sizeHint() == raw_double_spin_box.sizeHint()
            assert (
                double_spin_box.minimumSizeHint()
                == raw_double_spin_box.minimumSizeHint()
            )
            assert spin_box.lineEdit().geometry() == raw_spin_box.lineEdit().geometry()
            assert (
                double_spin_box.lineEdit().geometry()
                == raw_double_spin_box.lineEdit().geometry()
            )

            dark_spin_style = spin_box.styleSheet()
            dark_double_style = double_spin_box.styleSheet()
            setTheme(Theme.LIGHT)
            process_events()

            assert spin_box.styleSheet() != dark_spin_style
            assert double_spin_box.styleSheet() != dark_double_style

            spin_box.setSymbolVisible(False)
            double_spin_box.setSymbolVisible(False)
            process_events()
            assert spin_box.property("symbolVisible") is False
            assert double_spin_box.property("symbolVisible") is False
            assert spin_box.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
            assert (
                double_spin_box.buttonSymbols()
                == QAbstractSpinBox.ButtonSymbols.NoButtons
            )
            assert spin_box.sizeHint() == raw_hidden_spin_box.sizeHint()
            assert spin_box.minimumSizeHint() == raw_hidden_spin_box.minimumSizeHint()
            assert double_spin_box.sizeHint() == raw_hidden_double_spin_box.sizeHint()
            assert (
                double_spin_box.minimumSizeHint()
                == raw_hidden_double_spin_box.minimumSizeHint()
            )
            assert (
                spin_box.lineEdit().geometry()
                == raw_hidden_spin_box.lineEdit().geometry()
            )
            assert (
                double_spin_box.lineEdit().geometry()
                == raw_hidden_double_spin_box.lineEdit().geometry()
            )
            assert double_spin_box.textFromValue(1.2500000000) == "1.25"
        finally:
            dispose_widgets(
                raw_spin_box,
                raw_double_spin_box,
                raw_hidden_spin_box,
                raw_hidden_double_spin_box,
                spin_box,
                double_spin_box,
            )


def test_cube_section_title_uses_qfluent_label_primitive() -> None:
    """Cube section titles should be QFluent labels managed by QFluent styling."""

    class _Panel(QWidget):
        """Provide the editor-panel attributes needed to build a cube section."""

        def __init__(self) -> None:
            super().__init__()
            self.cube_headers: dict[str, QWidget] = {}
            self._cube_visibility_btns: dict[str, QWidget] = {}
            self._cube_visibility_menus: dict[str, object] = {}
            self._last_behavior_snapshot = type(
                "Snapshot",
                (),
                {
                    "field_specs_by_alias": {},
                    "reveal_entries_by_alias": {},
                },
            )()
            setattr(
                self,
                "scroll",
                SimpleNamespace(schedule_metrics_refresh=lambda: None),
            )

        def _build_behavior_snapshot(self) -> object:
            """Return the already configured behavior snapshot."""

            return self._last_behavior_snapshot

    with fluent_theme(Theme.DARK):
        panel = _Panel()
        try:
            cube_state = type("CubeState", (), {"buffer": {"nodes": {}}, "ui": None})()
            del cube_state
            CubeSectionBuilder(panel).build_cube_section("SDXL/Text to Image")
            title = panel.cube_headers["SDXL/Text to Image"]

            assert isinstance(title, SubtitleLabel)
            assert is_qfluent_managed(title)
        finally:
            dispose_widgets(panel)


def test_toolbar_omits_file_buttons_after_app_orb_menu_takes_file_actions() -> None:
    """Toolbar should leave file actions to the app orb menu."""

    from substitute.presentation.shell.app_orb_action_cluster import (
        APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME,
        APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME,
    )
    from substitute.presentation.shell.main_window_menu import build_main_window_menu

    with fluent_theme(Theme.DARK):
        host = QWidget()
        try:
            widgets = build_main_window_menu(
                host,
                workspace_controller=object(),
            )
            host.resize(420, widgets.menu_bar.height())
            host.show()
            process_events()

            assert widgets.orb_action_cluster is not None
            assert (
                widgets.cube_stack_mode_button.objectName()
                == APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME
            )
            assert (
                widgets.override_dropdown_btn.objectName()
                == APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME
            )
            assert not hasattr(widgets, "load_button")
            assert not hasattr(widgets, "save_button")
            assert not hasattr(widgets, "save_as_action")
            assert not hasattr(widgets, "export_action")

            setTheme(Theme.LIGHT)
            process_events()

            assert (
                widgets.cube_stack_mode_button.objectName()
                == APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME
            )
            assert (
                widgets.override_dropdown_btn.objectName()
                == APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME
            )
        finally:
            dispose_widgets(host)


def test_model_picker_combo_uses_qfluent_custom_light_dark_style() -> None:
    """Model picker combo styling should refresh without forcing white text."""

    with fluent_theme(Theme.DARK):
        combo = _ModelPickerComboSurface()
        try:
            combo.show()
            process_events()

            assert is_qfluent_managed(combo)
            dark_style = combo.styleSheet()
            setTheme(Theme.LIGHT)
            process_events()

            light_text = combo.palette().color(QPalette.ColorRole.Text)
            assert combo.styleSheet() != dark_style
            assert light_text != QColor("white")
        finally:
            dispose_widgets(combo)


class _QueueService:
    """Minimal queue service double for queue widget construction."""

    def add_observer(self, _observer: object) -> None:
        """Accept queue observer registration."""

    def cancel_job(self, _job_id: str) -> None:
        """Accept cancel requests."""

    def remove_terminal_job(self, _job_id: str) -> None:
        """Accept remove requests."""

    def move_pending_job(self, _job_id: str, _target_index: int) -> None:
        """Accept move requests."""


def _queue_row(
    job_id: str,
    *,
    title: str = "Workflow #001",
    subtitle: str = "Next",
    visual_role: Literal["active", "pending", "resolved"] = "pending",
) -> QueueJobRowView:
    """Return a queue row view for theme-awareness widget tests."""

    return QueueJobRowView(
        job_id=job_id,
        title=title,
        subtitle=subtitle,
        status="pending",
        action=None,
        visual_role=visual_role,
    )


def test_generation_queue_labels_use_qfluent_label_primitives() -> None:
    """Generation queue text should use QFluent labels instead of dark-only QLabel QSS."""

    with fluent_theme(Theme.DARK):
        panel = GenerationQueuePanel(cast(Any, _QueueService()))
        dropdown = GenerationQueueDropdownView()
        row = GenerationQueueItemRow(_queue_row("a"))
        rows_view = GenerationQueueRowsView(surface_mode="panel")
        try:
            rows_view.set_rows(
                (
                    _queue_row("pending", visual_role="pending"),
                    _queue_row(
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
        finally:
            dispose_widgets(panel, dropdown, row, rows_view)


def test_generation_queue_row_surface_refreshes_on_qfluent_theme_switch() -> None:
    """Generation queue row surfaces should rebuild custom QSS after theme changes."""

    with fluent_theme(Theme.DARK):
        row = GenerationQueueItemRow(_queue_row("a", visual_role="active"))
        try:
            row.show()
            process_events()
            dark_style = row.styleSheet()
            dark_thumbnail_style = row._thumbnail_label.styleSheet()

            setTheme(Theme.LIGHT)
            process_events()

            assert row.styleSheet() != dark_style
            assert row._thumbnail_label.styleSheet() != dark_thumbnail_style
            assert "rgba(255, 255, 255, 18)" not in row.styleSheet()
        finally:
            dispose_widgets(row)
