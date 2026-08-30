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

"""Verify Prompt Editor wheel-adjustment Settings behavior."""

from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.infrastructure.persistence import (
    FilePromptEditorPreferenceRepository,
)
from substitute.presentation.settings.prompt_editor_page import PromptEditorSettingsPage
from tests.support.qt.lifecycle import ensure_qt_application


def test_prompt_editor_page_exposes_wheel_hover_adjustment_switch(
    tmp_path: Path,
) -> None:
    """Prompt editor settings should expose the wheel interaction policy."""

    app = ensure_qt_application()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)

    app.processEvents()

    assert page._wheel_hover_adjust_row is not None
    assert page._wheel_hover_adjust_row.title_label.text() == "Wheel adjust after hover"
    assert page.is_wheel_hover_adjustment_enabled() is True


def test_prompt_editor_page_persists_wheel_hover_adjustment_mode_and_notifies(
    tmp_path: Path,
) -> None:
    """Toggling wheel hover adjustment should persist and notify the shell callback."""

    app = ensure_qt_application()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.set_wheel_hover_adjustment_enabled(False)
    app.processEvents()

    assert (
        service.load_preferences().wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    assert page.is_wheel_hover_adjustment_enabled() is False
    assert calls == ["changed"]


def test_prompt_editor_page_row_click_toggles_wheel_hover_adjustment(
    tmp_path: Path,
) -> None:
    """Clicking the wheel adjustment row should toggle the interaction switch."""

    app = ensure_qt_application()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.show()
    app.processEvents()
    assert page._wheel_hover_adjust_row is not None

    QTest.mouseClick(page._wheel_hover_adjust_row, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert (
        service.load_preferences().wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    assert page.is_wheel_hover_adjustment_enabled() is False
    assert calls == ["changed"]


def test_prompt_editor_page_reload_reflects_wheel_adjustment_mode(
    tmp_path: Path,
) -> None:
    """Reload should sync wheel adjustment switch state from persisted preferences."""

    app = ensure_qt_application()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)
    service.set_wheel_adjustment_mode(PromptWheelAdjustmentMode.FOCUS_REQUIRED)

    page.reload()
    app.processEvents()

    assert page.is_wheel_hover_adjustment_enabled() is False
