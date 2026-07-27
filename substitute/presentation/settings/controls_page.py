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

"""Render the expandable Controls Settings page and keyboard binding recorder."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.controls import (
    ControlBindingService,
    GenerationControlCommand,
)
from substitute.presentation.controls import (
    KeyboardBindingValidationError,
    display_keyboard_binding,
    keyboard_binding_from_event,
    keyboard_modifier_preview,
)
from substitute.presentation.generation_action_icons import (
    CONTINUOUS_GENERATION_ACTION_ICON,
    GENERATE_ACTION_ICON,
    SKIP_GENERATION_ACTION_ICON,
    STOP_GENERATION_ACTION_ICON,
)
from substitute.presentation.localization import LocalizedPushButton
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
    SettingsSectionEntry,
)
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_row_factories import (
    build_settings_icon_widget,
)
from substitute.presentation.settings.settings_segmented_card import (
    SettingsSegmentedCard,
    SettingsSegmentedCardRow,
)


@dataclass(frozen=True, slots=True)
class _KeyboardControlDefinition:
    """Describe one generation command exposed through the Keyboard family."""

    command: GenerationControlCommand
    setting_id: str
    title: str
    description: str
    keywords: tuple[str, ...]
    icon: object


def _keyboard_control_definitions() -> tuple[_KeyboardControlDefinition, ...]:
    """Return the ordered generation commands supported by Keyboard controls."""

    return (
        _KeyboardControlDefinition(
            command=GenerationControlCommand.ACTIVATE,
            setting_id="controls.keyboard.activate",
            title=app_text("Activate Generate"),
            description=app_text(
                "Runs the currently selected regular or infinite generation action."
            ),
            keywords=("keyboard", "key", "hotkey", "generate", "start"),
            icon=GENERATE_ACTION_ICON,
        ),
        _KeyboardControlDefinition(
            command=GenerationControlCommand.TOGGLE_MODE,
            setting_id="controls.keyboard.toggle_mode",
            title=app_text("Toggle Regular / Infinite mode"),
            description=app_text(
                "Switches the primary Generate control and updates its visible mode."
            ),
            keywords=(
                "keyboard",
                "key",
                "hotkey",
                "generate",
                "regular",
                "infinite",
                "mode",
            ),
            icon=CONTINUOUS_GENERATION_ACTION_ICON,
        ),
        _KeyboardControlDefinition(
            command=GenerationControlCommand.SKIP,
            setting_id="controls.keyboard.skip",
            title=app_text("Skip generation"),
            description=app_text("Skips the active queued generation when available."),
            keywords=("keyboard", "key", "hotkey", "generation", "queue", "skip"),
            icon=SKIP_GENERATION_ACTION_ICON,
        ),
        _KeyboardControlDefinition(
            command=GenerationControlCommand.STOP,
            setting_id="controls.keyboard.stop",
            title=app_text("Stop generation"),
            description=app_text(
                "Stops continuous or queued generation when available."
            ),
            keywords=("keyboard", "key", "hotkey", "generation", "queue", "stop"),
            icon=STOP_GENERATION_ACTION_ICON,
        ),
    )


class ControlsSettingsPage(QWidget):
    """Render input families as self-contained segmented Settings cards."""

    def __init__(
        self,
        binding_service: ControlBindingService,
        *,
        capture_active_changed: Callable[[bool], None],
        parent: QWidget | None = None,
    ) -> None:
        """Create the first Controls page with its Keyboard input family."""

        super().__init__(parent)
        self._binding_service = binding_service
        self._capture_active_changed = capture_active_changed
        self._active_row: KeyboardControlBindingRow | None = None
        self._rows_by_setting_id: dict[str, KeyboardControlBindingRow] = {}
        self._build_layout()

    def _build_layout(self) -> None:
        """Create the keyboard segmented card without future-family special cases."""

        rows = tuple(
            _keyboard_control_row(
                definition,
                binding_service=self._binding_service,
                capture_started=self._capture_started,
                parent=self,
            )
            for definition in _keyboard_control_definitions()
        )
        self._rows_by_setting_id = {row.setting_id: row for row in rows}
        keyboard_group = SettingsCardGroup(
            app_text("Keyboard"),
            subtitle=app_text("Assign keyboard controls for generation actions."),
            cards=(SettingsSegmentedCard(rows=rows, parent=self),),
            parent=self,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(keyboard_group)
        layout.addStretch(1)

    def _capture_started(self, row: KeyboardControlBindingRow) -> None:
        """Ensure only one keyboard row owns global key capture at a time."""

        if self._active_row is not None and self._active_row is not row:
            self._active_row.cancel_capture()
        self._active_row = row
        self._capture_active_changed(True)

    def capture_finished(self, row: KeyboardControlBindingRow) -> None:
        """Release global capture only after the owning row finishes recording."""

        if self._active_row is row:
            self._active_row = None
            self._capture_active_changed(False)

    def refresh_bindings(self) -> None:
        """Refresh every row after a binding moves between commands."""

        for row in self._rows_by_setting_id.values():
            row.refresh_binding()

    def reveal_setting(self, setting_id: str) -> None:
        """Focus the Keyboard row selected from global Settings search."""

        row = self._rows_by_setting_id.get(setting_id)
        if row is not None:
            row.setFocus(Qt.FocusReason.OtherFocusReason)


class KeyboardControlBindingRow(SettingsSegmentedCardRow):
    """Render one keyboard-backed command with live capture and clear behavior."""

    def __init__(
        self,
        *,
        command: GenerationControlCommand,
        setting_id: str,
        title: str,
        description: str,
        icon: object,
        binding_service: ControlBindingService,
        capture_started: Callable[[KeyboardControlBindingRow], None],
        parent: QWidget,
    ) -> None:
        """Create a row whose trailing controls show and edit its saved binding."""

        self._command = command
        self.setting_id = setting_id
        self._binding_service = binding_service
        self._capture_started = capture_started
        self._capturing = False
        self._binding_edit = _KeyboardBindingEdit(parent)
        self._binding_edit.captureRequested.connect(self.start_capture)
        self._binding_edit.bindingCaptured.connect(self._save_captured_binding)
        self._binding_edit.captureCancelled.connect(self.cancel_capture)
        configure_settings_field_width(self._binding_edit, preferred_width=200)
        self._clear_button = LocalizedPushButton(app_text("Clear"), parent)
        controls = SettingsControlGroup(
            self._binding_edit,
            self._clear_button,
            spacing=6,
            parent=parent,
        )
        super().__init__(
            title=title,
            description=description,
            visual_widget=build_settings_icon_widget(icon, parent),
            trailing_widget=controls,
            parent=parent,
        )
        self.setObjectName(setting_id)
        self._clear_button.clicked.connect(self.clear_binding)
        self._refresh_binding()

    def start_capture(self) -> None:
        """Enter live keyboard capture and prevent shell bindings from firing."""

        self._capturing = True
        self._binding_edit.start_capture()
        self._capture_started(self)

    def cancel_capture(self) -> None:
        """Leave live capture without changing the saved binding."""

        if not self._capturing:
            return
        self._capturing = False
        self._binding_edit.stop_capture()
        page = self._controls_page()
        if page is not None:
            page.capture_finished(self)
        self._refresh_binding()

    def clear_binding(self) -> None:
        """Clear the explicit binding so this command no longer intercepts input."""

        self.cancel_capture()
        self._binding_service.set_binding(self._command.value, None)
        self._refresh_binding()

    def _save_captured_binding(self, binding: str) -> None:
        """Persist a validated capture, transferring it from another command if needed."""

        self._binding_service.set_binding(self._command.value, binding)
        page = self._controls_page()
        if page is not None:
            page.refresh_bindings()
        self.cancel_capture()

    def refresh_binding(self) -> None:
        """Refresh the visible binding after another row changes it."""

        self._refresh_binding()

    def _refresh_binding(self) -> None:
        """Reflect the currently persisted binding in the Keyboard field."""

        self._binding_edit.setText(
            display_keyboard_binding(
                self._binding_service.binding_for(self._command.value)
            )
        )

    def _controls_page(self) -> ControlsSettingsPage | None:
        """Return the containing Controls page when the row is still attached."""

        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, ControlsSettingsPage):
                return parent
            parent = parent.parentWidget()
        return None


def _keyboard_control_row(
    definition: _KeyboardControlDefinition,
    *,
    binding_service: ControlBindingService,
    capture_started: Callable[[KeyboardControlBindingRow], None],
    parent: QWidget,
) -> KeyboardControlBindingRow:
    """Create one Keyboard row from its shared command definition."""

    return KeyboardControlBindingRow(
        command=definition.command,
        setting_id=definition.setting_id,
        title=definition.title,
        description=definition.description,
        icon=definition.icon,
        binding_service=binding_service,
        capture_started=capture_started,
        parent=parent,
    )


def build_controls_search_catalog_entry(
    binding_service: ControlBindingService,
) -> SettingsPageEntry:
    """Build searchable Controls metadata backed by real Keyboard control rows."""

    definitions = _keyboard_control_definitions()
    return SettingsPageEntry(
        page_id="controls",
        title=app_text("Controls"),
        subtitle=app_text("Configure keyboard and future input controls."),
        icon=AppIcon.CURSOR_HOVER_20_REGULAR,
        order=25,
        sections=(
            SettingsSectionEntry(
                section_id="controls.keyboard",
                title=app_text("Keyboard"),
                subtitle=app_text("Assign keyboard controls for generation actions."),
                order=10,
                controls=tuple(
                    SettingsControlEntry(
                        setting_id=definition.setting_id,
                        title=definition.title,
                        description=definition.description,
                        keywords=definition.keywords,
                        order=index,
                        factory=lambda parent, item=definition: _keyboard_control_row(
                            item,
                            binding_service=binding_service,
                            capture_started=lambda _row: None,
                            parent=parent,
                        ),
                    )
                    for index, definition in enumerate(definitions, start=10)
                ),
            ),
        ),
    )


class _KeyboardBindingEdit(LineEdit):  # type: ignore[misc]
    """Capture one keyboard binding through a native Fluent text-field surface."""

    from PySide6.QtCore import Signal

    captureRequested = Signal()
    bindingCaptured = Signal(str)
    captureCancelled = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create a read-only display field that records a clicked key sequence."""

        super().__init__(parent)
        self._capturing = False
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start capture when the user clicks the binding field."""

        if event.button() == Qt.MouseButton.LeftButton:
            self.captureRequested.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def start_capture(self) -> None:
        """Focus the field and begin rendering key previews."""

        self._capturing = True
        self.setText(app_text("Press a key combination..."))
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def stop_capture(self) -> None:
        """Stop accepting capture events until the next explicit request."""

        self._capturing = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Preview modifiers and commit a valid binding without forwarding input."""

        if not self._capturing:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.captureCancelled.emit()
            event.accept()
            return
        preview = keyboard_modifier_preview(event)
        if preview:
            self.setText(preview)
        try:
            binding = keyboard_binding_from_event(event)
        except KeyboardBindingValidationError as error:
            if not preview:
                self.setText(error.message)
            event.accept()
            return
        self.bindingCaptured.emit(binding)
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Clear a modifier preview when the user releases it without a chord."""

        if not self._capturing:
            super().keyReleaseEvent(event)
            return
        if event.key() in {
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
        }:
            self.setText(app_text("Press a key combination..."))
        event.accept()


__all__ = [
    "ControlsSettingsPage",
    "KeyboardControlBindingRow",
    "build_controls_search_catalog_entry",
]
