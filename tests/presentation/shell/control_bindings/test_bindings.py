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

"""Verify persisted controls, safe keyboard capture, and generation dispatch."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest

from substitute.application.controls import (
    ControlBindingService,
    GenerationControlCommand,
)
from substitute.domain.controls import (
    ControlBindingPreferences,
    default_control_binding_preferences,
)
from substitute.presentation.controls import (
    KeyboardBindingValidationError,
    display_keyboard_binding,
    keyboard_binding_from_event,
    keyboard_modifier_preview,
)
from substitute.presentation.shell.control_binding_dispatcher import (
    ControlBindingDispatcher,
)
from substitute.presentation.shell.generation_action_state import GenerationActionState
from substitute.presentation.settings.controls_page import (
    ControlsSettingsPage,
    KeyboardControlBindingRow,
    build_controls_search_catalog_entry,
)
from substitute.presentation.settings.settings_search import search_settings_catalog
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


class _Repository:
    """Hold a binding snapshot in memory for application-service tests."""

    def __init__(self) -> None:
        """Initialize empty persisted preferences."""

        self.preferences = default_control_binding_preferences()

    def load(self) -> ControlBindingPreferences:
        """Return the saved preference snapshot."""

        return self.preferences

    def save(self, preferences: ControlBindingPreferences) -> None:
        """Retain one saved preference snapshot."""

        self.preferences = preferences


class _GenerationActions:
    """Record generation action callbacks reached through a binding."""

    def __init__(self) -> None:
        """Initialize action counters."""

        self.generate_calls = 0
        self.skip_calls = 0
        self.stop_calls = 0

    def on_generate_clicked(self) -> None:
        """Record primary generation activation."""

        self.generate_calls += 1

    def on_skip_generation_clicked(self) -> None:
        """Record generation skip activation."""

        self.skip_calls += 1

    def on_stop_generation_clicked(self) -> None:
        """Record generation stop activation."""

        self.stop_calls += 1


class _GenerationActionController:
    """Expose a fixed available generation presentation state."""

    def __init__(self) -> None:
        """Initialize the selected-mode update record."""

        self.selected_modes: list[str] = []

    def generation_action_state(self) -> GenerationActionState:
        """Return a workflow state where all generation controls are available."""

        return GenerationActionState(
            selected_mode="generate",
            continuous_active=False,
            backend_ready=True,
            workflow_runnable=True,
            settings_route_active=False,
            queue_has_active=True,
            queue_has_cancellable=True,
            pending_queue_count=1,
            queue_has_visible_jobs=True,
            queue_panel_visible=False,
        )

    def set_generation_selected_mode(self, mode: str) -> None:
        """Record the mode selected by the toggle command."""

        self.selected_modes.append(mode)


def test_keyboard_capture_rejects_plain_typing_and_accepts_home_cluster() -> None:
    """Keyboard controls should reserve navigation keys without capturing prompt text."""

    plain_letter = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_H, Qt.KeyboardModifier.NoModifier
    )
    home = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier
    )

    with pytest.raises(KeyboardBindingValidationError):
        keyboard_binding_from_event(plain_letter)

    assert keyboard_binding_from_event(home) == "Home"


def test_keyboard_capture_previews_held_modifiers_before_a_key_is_chosen() -> None:
    """Capture feedback should expose incomplete modifier combinations live."""

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Alt,
        Qt.KeyboardModifier.AltModifier,
    )

    assert keyboard_modifier_preview(event) == "Alt +"


def test_keyboard_binding_display_uses_spaced_chord_separators() -> None:
    """Saved shortcut text should match the spacing used by its live preview."""

    assert display_keyboard_binding("Alt+A") == "Alt + A"


def test_binding_service_transfers_duplicate_binding_to_new_command() -> None:
    """Recording an assigned key should move it to the newly selected command."""

    service = ControlBindingService(_Repository())
    service.set_binding(GenerationControlCommand.ACTIVATE.value, "Home")

    service.set_binding(GenerationControlCommand.STOP.value, "Home")

    assert service.binding_for(GenerationControlCommand.ACTIVATE.value) is None
    assert service.binding_for(GenerationControlCommand.STOP.value) == "Home"

    service.set_binding(GenerationControlCommand.STOP.value, "Home")

    assert service.binding_for(GenerationControlCommand.STOP.value) == "Home"

    service.set_binding(GenerationControlCommand.ACTIVATE.value, None)

    assert service.binding_for(GenerationControlCommand.ACTIVATE.value) is None


def test_generation_binding_consumes_home_before_prompt_input_and_uses_button_action() -> (
    None
):
    """A configured Home binding should invoke Generate instead of editor navigation."""

    service = ControlBindingService(_Repository())
    service.set_binding(GenerationControlCommand.ACTIVATE.value, "Home")
    actions = _GenerationActions()
    controller = _GenerationActionController()
    shell = SimpleNamespace(
        controls_keyboard_capture_active=False,
        control_binding_service=service,
        generation_action_controller=controller,
        workspace_generation_actions=actions,
        _current_generate_mode="generate",
    )
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier
    )

    assert ControlBindingDispatcher(shell).handle_event(event) is True
    assert actions.generate_calls == 1
    assert event.isAccepted()


def test_generation_mode_binding_uses_authoritative_mode_selection() -> None:
    """The mode binding should select through the same controller as the menu."""

    service = ControlBindingService(_Repository())
    service.set_binding(GenerationControlCommand.TOGGLE_MODE.value, "F8")
    actions = _GenerationActions()
    controller = _GenerationActionController()
    shell = SimpleNamespace(
        controls_keyboard_capture_active=False,
        control_binding_service=service,
        generation_action_controller=controller,
        workspace_generation_actions=actions,
        _current_generate_mode="generate",
    )
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_F8, Qt.KeyboardModifier.NoModifier
    )

    assert ControlBindingDispatcher(shell).handle_event(event) is True
    assert controller.selected_modes == ["continuous"]


def test_controls_page_starts_with_one_keyboard_segmented_card() -> None:
    """Keyboard controls should capture through a Fluent field with only Clear beside it."""

    _ = ensure_qt_application()
    service = ControlBindingService(_Repository())
    capture_states: list[bool] = []

    page = ControlsSettingsPage(
        service,
        capture_active_changed=capture_states.append,
    )
    try:
        rows = page.findChildren(KeyboardControlBindingRow)

        assert len(rows) == 4
        row = rows[0]
        QTest.mouseClick(row._binding_edit, Qt.MouseButton.LeftButton)
        assert capture_states == [True]
        QTest.keyClick(row._binding_edit, Qt.Key.Key_F8)
        assert capture_states == [True, False]
        assert row._binding_edit.text() == "F8"
        assert row._clear_button.text() == "Clear"
        row._clear_button.click()
        assert row._binding_edit.text() == "Not set"
    finally:
        page.close()
        destroy_qt_object(page)


def test_controls_page_reassigns_an_existing_shortcut_and_refreshes_both_rows() -> None:
    """Capturing an occupied shortcut should visibly move it to the current row."""

    _ = ensure_qt_application()
    page = ControlsSettingsPage(
        ControlBindingService(_Repository()),
        capture_active_changed=lambda _active: None,
    )
    try:
        activate_row, toggle_mode_row = page.findChildren(KeyboardControlBindingRow)[:2]

        QTest.mouseClick(activate_row._binding_edit, Qt.MouseButton.LeftButton)
        QTest.keyClick(activate_row._binding_edit, Qt.Key.Key_F8)
        QTest.mouseClick(toggle_mode_row._binding_edit, Qt.MouseButton.LeftButton)
        QTest.keyClick(toggle_mode_row._binding_edit, Qt.Key.Key_F8)

        assert activate_row._binding_edit.text() == "Not set"
        assert toggle_mode_row._binding_edit.text() == "F8"
    finally:
        page.close()
        destroy_qt_object(page)


@pytest.mark.parametrize(
    ("key", "preview"),
    (
        (Qt.Key.Key_Alt, "Alt +"),
        (Qt.Key.Key_Control, "Ctrl +"),
    ),
)
def test_modifier_preview_clears_on_release_without_saving_a_binding(
    key: Qt.Key,
    preview: str,
) -> None:
    """Alt and Ctrl alone should remain temporary capture previews, never bindings."""

    _ = ensure_qt_application()
    service = ControlBindingService(_Repository())
    page = ControlsSettingsPage(service, capture_active_changed=lambda _active: None)
    try:
        row = page.findChildren(KeyboardControlBindingRow)[0]

        QTest.mouseClick(row._binding_edit, Qt.MouseButton.LeftButton)
        QTest.keyPress(row._binding_edit, key)

        assert row._binding_edit.text() == preview
        assert service.binding_for(GenerationControlCommand.ACTIVATE.value) is None

        QTest.keyRelease(row._binding_edit, key)

        assert row._binding_edit.text() == "Press a key combination..."
        assert service.binding_for(GenerationControlCommand.ACTIVATE.value) is None
    finally:
        page.close()
        destroy_qt_object(page)


def test_controls_catalog_populates_sidebar_metadata_and_keyboard_search() -> None:
    """Controls metadata must be ordered and expose every Keyboard command to search."""

    catalog_entry = build_controls_search_catalog_entry(
        ControlBindingService(_Repository())
    )

    assert catalog_entry.page_id == "controls"
    assert catalog_entry.order == 25
    assert tuple(
        result.setting_id
        for result in search_settings_catalog((catalog_entry,), "keyboard")
    ) == (
        "controls.keyboard.activate",
        "controls.keyboard.toggle_mode",
        "controls.keyboard.skip",
        "controls.keyboard.stop",
    )
