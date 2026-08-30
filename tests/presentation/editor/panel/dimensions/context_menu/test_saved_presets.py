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

"""Test saved-dimension menu presentation and commands."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalog,
    DimensionPresetItem,
    DimensionPresetSection,
)
from tests.presentation.editor.panel.dimensions.context_menu.support import (
    DimensionPanel as _Panel,
    FakeDimensionPresetSource as _FakeDimensionPresetSource,
    action as _action,
    add_dimension_row as _add_dimension_row,
    cleanup_widgets as _cleanup_widgets,
    ensure_worker_application as _ensure_app,
    install_recording_dimension_menu,
    spinbox as _spinbox,
    submenu as _submenu,
)


def test_dimension_group_with_saved_source_places_set_dimensions_before_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saved dimensions should appear before ratio and save should sit at the bottom."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetCatalog(
            sections=(
                DimensionPresetSection(
                    title="Global",
                    presets=(
                        DimensionPresetItem(
                            label="832 x 1216",
                            short_edge=832,
                            long_edge=1216,
                        ),
                    ),
                ),
            )
        )
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = menu_recording.root
        assert root_menu.entries == [
            ("action", "Swap width & height"),
            ("menu", "Set dimensions"),
            ("menu", "Set ratio by Width"),
            ("separator", ""),
            ("menu", "Save current dimensions"),
        ]
        assert [submenu.title for submenu in root_menu.submenus] == [
            "Set dimensions",
            "Set ratio by Width",
            "Save current dimensions",
        ]
        save_menu = _submenu(root_menu, "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == ["Save globally"]
    finally:
        _cleanup_widgets(app, content, panel)


def test_saved_dimension_actions_apply_portrait_and_landscape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saved dimension presets should write both fields in selected orientation."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetCatalog(
            sections=(
                DimensionPresetSection(
                    title="For Illustrious",
                    presets=(
                        DimensionPresetItem(
                            label="1024 x 1536",
                            short_edge=1024,
                            long_edge=1536,
                        ),
                    ),
                ),
                DimensionPresetSection(
                    title="Global",
                    presets=(
                        DimensionPresetItem(
                            label="SDXL square",
                            short_edge=1024,
                            long_edge=1024,
                        ),
                    ),
                ),
            ),
            model_save_label="Illustrious",
        )
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=512, key="source_width")
        height = _spinbox(panel, value=768, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        dimensions_menu = _submenu(menu_recording.root, "Set dimensions")
        assert dimensions_menu.entries == [
            ("menu", "Portrait"),
            ("menu", "Landscape"),
        ]
        portrait_menu = _submenu(dimensions_menu, "Portrait")
        landscape_menu = _submenu(dimensions_menu, "Landscape")
        assert portrait_menu.entries == [
            ("header", "For Illustrious"),
            ("action", "1024 x 1536"),
            ("separator", ""),
            ("header", "Global"),
            ("action", "SDXL square 1024 x 1024"),
        ]
        assert landscape_menu.entries == [
            ("header", "For Illustrious"),
            ("action", "1536 x 1024"),
            ("separator", ""),
            ("header", "Global"),
            ("action", "SDXL square 1024 x 1024"),
        ]
        assert [action.text() for action in portrait_menu.actions] == [
            "1024 x 1536",
            "SDXL square 1024 x 1024",
        ]
        assert [action.text() for action in landscape_menu.actions] == [
            "1536 x 1024",
            "SDXL square 1024 x 1024",
        ]

        _action(portrait_menu, "1024 x 1536").trigger()
        assert (width.value(), height.value()) == (1024, 1536)

        _action(landscape_menu, "1536 x 1024").trigger()
        assert (width.value(), height.value()) == (1536, 1024)

        _action(portrait_menu, "SDXL square 1024 x 1024").trigger()
        assert (width.value(), height.value()) == (1024, 1024)
    finally:
        _cleanup_widgets(app, content, panel)


def test_save_current_dimensions_actions_call_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save actions should pass current absolute dimensions to the source."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetCatalog(model_save_label="Illustrious")
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1024, key="source_width")
        height = _spinbox(panel, value=1536, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        save_menu = _submenu(menu_recording.root, "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == [
            "Save globally",
            "Save for Illustrious",
        ]
        _action(save_menu, "Save globally").trigger()
        _action(save_menu, "Save for Illustrious").trigger()

        assert source.global_saves == [(1024, 1536)]
        assert source.model_saves == [(1024, 1536)]
    finally:
        _cleanup_widgets(app, content, panel)


def test_save_only_dimension_row_menu_preserves_existing_save_hierarchy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restricted dimension row should expose saving without resize actions."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(
        DimensionPresetCatalog(model_save_label="Illustrious")
    )
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=960, key="source_width")
        height = _spinbox(panel, value=1344, key="source_height")
        built_row = _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )
        assert built_row.dimension_actions is not None

        built_row.dimension_actions.show_save_only()
        built_row.row.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = menu_recording.root
        assert root_menu.entries == [("menu", "Save current dimensions")]
        save_menu = _submenu(root_menu, "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == [
            "Save globally",
            "Save for Illustrious",
        ]
        _action(save_menu, "Save globally").trigger()
        assert source.global_saves == [(960, 1344)]
    finally:
        _cleanup_widgets(app, content, panel)


def test_save_for_model_is_omitted_without_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model-family save action should be absent when no family is available."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _FakeDimensionPresetSource(DimensionPresetCatalog())
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1024, key="source_width")
        height = _spinbox(panel, value=1536, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        save_menu = _submenu(menu_recording.root, "Save current dimensions")
        assert [action.text() for action in save_menu.actions] == ["Save globally"]
    finally:
        _cleanup_widgets(app, content, panel)


def test_menu_open_consumes_prepared_snapshot_without_loading_presets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saved dimensions should be rendered only from a prepared model."""

    class _PreparedOnlySource:
        """Expose a prepared model and reject foreground preparation/loading."""

        def __init__(self) -> None:
            """Initialize with no prepared saved dimensions."""

            self.current_calls = 0

        def current_dimension_preset_catalog(
            self,
        ) -> DimensionPresetCatalog | None:
            """Return no prepared dimensions for this menu invocation."""

            self.current_calls += 1
            return None

        def prepare_dimension_preset_catalog(self, *, reason: str) -> None:
            """Fail if context-menu opening tries to prepare data."""

            raise AssertionError(f"unexpected menu-open preparation: {reason}")

        def list_dimension_presets(self) -> DimensionPresetCatalog:
            """Fail if context-menu opening tries to load presets."""

            raise AssertionError("unexpected menu-open preset loading")

        def save_current_dimensions_globally(self, width: int, height: int) -> None:
            """Unused save method required by the protocol."""

            _ = (width, height)

        def save_current_dimensions_for_model(self, width: int, height: int) -> None:
            """Unused save method required by the protocol."""

            _ = (width, height)

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    source = _PreparedOnlySource()
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1024, key="source_width")
        height = _spinbox(panel, value=1536, key="source_height")
        _add_dimension_row(
            panel,
            content_layout,
            width=width,
            height=height,
            dimension_preset_source=source,
        )

        width.customContextMenuRequested.emit(QPoint(1, 1))

        assert source.current_calls == 1
        assert [submenu.title for submenu in menu_recording.root.submenus] == [
            "Set ratio by Width"
        ]
    finally:
        _cleanup_widgets(app, content, panel)
