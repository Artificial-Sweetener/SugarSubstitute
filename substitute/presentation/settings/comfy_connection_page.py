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

"""Render Comfy target connection preferences in Settings."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    ApplicationText,
    apply_application_text,
    app_text,
    set_localized_placeholder,
    set_localized_text,
    translate_application_text,
)
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
    LocalizedRadioButton,
)

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QFileDialog,
    QButtonGroup,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    IconWidget,
    LineEdit,
    SpinBox,
)

from substitute.application.onboarding import (
    ComfyConnectionSaveResult,
    ComfyConnectionSettingsDraft,
    ComfyConnectionSettingsService,
    ComfyConnectionSettingsSnapshot,
    ComfyTargetMode,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskResult,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    SettingsCard,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_infobar import SettingsInfoBar
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_TOP_MARGIN,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.platform_path_guidance import existing_comfy_example

_LOAD_SNAPSHOT_TASK_ID = "comfy_connection.load_snapshot"
_SAVE_DRAFT_TASK_ID = "comfy_connection.save_draft"
_TEST_ENDPOINT_TASK_ID = "comfy_connection.test_endpoint"
_MODE_OPTIONS: tuple[tuple[ApplicationText, ComfyTargetMode, ApplicationText], ...] = (
    (
        app_text("Managed local"),
        ComfyTargetMode.MANAGED_LOCAL,
        app_text(
            "Substitute stores, prepares, and launches this local ComfyUI installation."
        ),
    ),
    (
        app_text("Existing local"),
        ComfyTargetMode.ATTACHED_LOCAL,
        app_text("Substitute launches and prepares a ComfyUI folder you already have."),
    ),
    (
        app_text("Remote"),
        ComfyTargetMode.REMOTE,
        app_text("Substitute connects to a ComfyUI server you run separately."),
    ),
)
_HOST_FIELD_WIDTH = 180
_PORT_FIELD_MIN_WIDTH = 86
_PATH_FIELD_WIDTH = 360


class _ComfySourceSelector(QWidget):
    """Expose Comfy target modes as visible radio options."""

    modeChanged = Signal(object)

    def __init__(
        self,
        options: tuple[tuple[ApplicationText, ComfyTargetMode, ApplicationText], ...],
        parent: QWidget | None = None,
    ) -> None:
        """Create the visible source selector for one Settings page."""

        super().__init__(parent)
        self._options = options
        self._buttons: dict[ComfyTargetMode, LocalizedRadioButton] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self.setObjectName("ComfyConnectionSourceSelector")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_layout()

    def option_labels(self) -> tuple[str, ...]:
        """Return the visible source option labels."""

        return tuple(button.text() for button in self._buttons.values())

    def selected_mode(self) -> ComfyTargetMode:
        """Return the currently selected source mode."""

        for mode, button in self._buttons.items():
            if button.isChecked():
                return mode
        return ComfyTargetMode.MANAGED_LOCAL

    def set_selected_mode(self, mode: ComfyTargetMode) -> None:
        """Select one source mode."""

        button = self._buttons.get(mode)
        if button is not None:
            button.setChecked(True)

    def _build_layout(self) -> None:
        """Build all radio option rows."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for label, mode, description in self._options:
            layout.addWidget(self._build_option_row(label, mode, description))
        self.set_selected_mode(ComfyTargetMode.MANAGED_LOCAL)

    def _build_option_row(
        self,
        label: ApplicationText,
        mode: ComfyTargetMode,
        description: ApplicationText,
    ) -> QWidget:
        """Create one radio option row."""

        row = QWidget(self)
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row.setStyleSheet("background-color: transparent; border: none;")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        button = LocalizedRadioButton(label, row)
        button.setObjectName(f"ComfyConnectionSource{mode.value.title()}Radio")
        button.toggled.connect(
            lambda checked, selected_mode=mode: self._emit_mode_if_checked(
                checked,
                selected_mode,
            )
        )
        self._buttons[mode] = button
        self._button_group.addButton(button)
        row_layout.addWidget(button)

        description_label = LocalizedCaptionLabel(description, row)
        description_label.setWordWrap(True)
        description_label.setContentsMargins(24, 0, 0, 0)
        row_layout.addWidget(description_label)
        return row

    def _emit_mode_if_checked(
        self,
        checked: bool,
        mode: ComfyTargetMode,
    ) -> None:
        """Emit mode changes only for the newly checked option."""

        if checked:
            self.modeChanged.emit(mode)


class ComfyConnectionSettingsPage(QWidget):
    """Expose persisted Comfy target settings as compact Settings rows."""

    def __init__(
        self,
        *,
        service: ComfyConnectionSettingsService,
        open_reconfigure_window: Callable[[], object],
        show_restart_requirements: Callable[[], None] | None = None,
        parent: QWidget | None = None,
        task_runner_factory: SettingsAsyncTaskRunnerFactory,
    ) -> None:
        """Build the Comfy connection Settings page."""

        super().__init__(parent)
        self._service = service
        self._open_reconfigure_window = open_reconfigure_window
        self._show_restart_requirements = show_restart_requirements
        self._loaded_draft: ComfyConnectionSettingsDraft | None = None
        self._managed_model_root_uses_default = True
        self._model_root_management_available = False
        self._default_managed_model_root: str | None = None
        self._is_loading = False
        self._save_in_flight = False
        self._task_generation = 0
        self._active_task_generations: dict[str, int] = {}
        self._async_runner = task_runner_factory(
            self,
            owner_id="comfy_connection_settings",
        )
        self._async_runner.taskCompleted.connect(self._apply_task_result)
        self._build_layout()
        self.reload()

    def reload(self) -> None:
        """Request a non-blocking reload of persisted Comfy target settings."""

        self._set_load_busy(True)
        self._run_task(
            task_id=_LOAD_SNAPSHOT_TASK_ID,
            operation=self._service.load_snapshot,
        )

    def mode_options(self) -> tuple[str, ...]:
        """Return visible target-mode option labels for tests."""

        return self.source_selector.option_labels()

    def selected_mode(self) -> ComfyTargetMode:
        """Return the currently selected target mode."""

        return self._selected_mode()

    def set_selected_mode(self, mode: ComfyTargetMode) -> None:
        """Select one target mode through the same path as user input."""

        self.source_selector.set_selected_mode(mode)

    def is_managed_folder_row_visible(self) -> bool:
        """Return whether the managed folder row is visible."""

        return not self.managed_folder_row.isHidden()

    def is_model_folder_row_visible(self) -> bool:
        """Return whether the managed model folder row is visible."""

        return not self.model_folder_row.isHidden()

    def is_existing_folder_row_visible(self) -> bool:
        """Return whether the existing local folder row is visible."""

        return not self.existing_folder_row.isHidden()

    def save_changes(self) -> None:
        """Persist the current draft through the page save path."""

        self._save_changes()

    def discard_changes(self) -> None:
        """Restore controls from the last loaded draft."""

        self._discard_changes()

    def test_connection(self) -> None:
        """Probe the current host and port through the page test path."""

        self._test_connection()

    def _build_layout(self) -> None:
        """Create the Comfy connection settings controls layout."""

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)
        content = self._build_content_widget()
        page_layout.addWidget(content)
        page_layout.addStretch(1)

    def _build_content_widget(self) -> QWidget:
        """Create the settings rows for Comfy connection editing."""

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        self.source_row = self._build_source_row()
        self.endpoint_row = self._build_endpoint_row()
        self.managed_folder_row = self._build_managed_folder_row()
        self.model_folder_row = self._build_model_folder_row()
        self.existing_folder_row = self._build_existing_folder_row()
        self.existing_python_row = self._build_existing_python_row()
        self.setup_action_row = self._build_setup_action_row()
        self.connection_feedback_bar = SettingsInfoBar(self)
        self.connection_check_row = self._build_connection_check_row()
        self.actions_widget = self._build_actions_widget()

        self.source_group = SettingsCardGroup(
            app_text("ComfyUI source"),
            cards=(self.source_row,),
            parent=self,
        )
        self.configuration_group = SettingsCardGroup(
            app_text("Managed local setup"),
            cards=(
                self.managed_folder_row,
                self.model_folder_row,
                self.existing_folder_row,
                self.existing_python_row,
                self.endpoint_row,
                self.setup_action_row,
            ),
            parent=self,
        )
        self.connection_check_group = SettingsCardGroup(
            app_text("Connection check"),
            cards=(self.connection_feedback_bar, self.connection_check_row),
            parent=self,
        )
        layout.addWidget(self.source_group)
        layout.addWidget(self.configuration_group)
        layout.addWidget(self.connection_check_group)
        layout.addWidget(self.actions_widget)
        layout.addStretch(1)
        return content

    def _build_source_row(self) -> SettingsCard:
        """Create the visible ComfyUI source selection row."""

        self.source_selector = _ComfySourceSelector(_MODE_OPTIONS, self)
        self.source_selector.modeChanged.connect(self._on_source_mode_changed)
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR),
            title=app_text("ComfyUI source"),
            description=app_text(
                "Choose the ComfyUI instance Substitute uses for image generation."
            ),
            trailing_widget=self.source_selector,
            reserve_visual_space=True,
            content_alignment="vertical",
            parent=self,
        )

    def _build_connection_check_row(self) -> SettingsCard:
        """Create the connection-test and saved-settings refresh row."""

        refresh_button = LocalizedPushButton(app_text("Refresh"), self)
        refresh_button.clicked.connect(self.reload)
        self.refresh_button = refresh_button
        test_button = LocalizedPushButton(app_text("Test connection"), self)
        test_button.clicked.connect(self._test_connection)
        self.test_button = test_button
        controls = self._control_row(refresh_button, test_button)
        return SettingsCard(
            visual_widget=self._icon_widget(
                AppIcon.PLUG_CONNECTED_CHECKMARK_20_REGULAR
            ),
            title=app_text("Connection check"),
            description=app_text("Loading ComfyUI connection settings."),
            trailing_widget=controls,
            reserve_visual_space=True,
            parent=self,
        )

    def _build_endpoint_row(self) -> SettingsCard:
        """Create the host and port editing row."""

        self.host_edit = LineEdit(self)
        self.host_edit.setObjectName("ComfyConnectionHostEdit")
        configure_settings_field_width(
            self.host_edit,
            preferred_width=_HOST_FIELD_WIDTH,
        )
        self.host_edit.setPlaceholderText("127.0.0.1")
        self.host_edit.textChanged.connect(self._on_draft_changed)
        self.port_spinbox = SpinBox(self)
        self.port_spinbox.setObjectName("ComfyConnectionPortSpinBox")
        self.port_spinbox.setRange(1, 65535)
        self.port_spinbox.setSymbolVisible(False)
        self.port_spinbox.setFixedWidth(_port_field_width(self.port_spinbox))
        self.port_spinbox.setFixedHeight(self.host_edit.minimumHeight())
        self.port_spinbox.valueChanged.connect(self._on_draft_changed)
        controls = self._control_row(self.host_edit, self.port_spinbox)
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.GLOBE_DESKTOP_20_REGULAR),
            title=app_text("Local endpoint"),
            description=app_text(
                "Substitute connects to the local ComfyUI process at this address."
            ),
            trailing_widget=controls,
            reserve_visual_space=True,
            parent=self,
        )

    def _build_managed_folder_row(self) -> SettingsCard:
        """Create the managed-local workspace path row."""

        self.managed_folder_edit = self._path_edit("ComfyConnectionManagedFolderEdit")
        self.managed_folder_edit.textChanged.connect(
            self._on_managed_folder_text_changed
        )
        browse_button = LocalizedPushButton(app_text("Browse"), self)
        browse_button.clicked.connect(self._browse_managed_folder)
        controls = self._control_row(self.managed_folder_edit, browse_button)
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.SERVER_20_REGULAR),
            title=app_text("ComfyUI folder"),
            description=app_text(
                "Substitute stores the managed ComfyUI installation in this folder."
            ),
            trailing_widget=controls,
            reserve_visual_space=True,
            parent=self,
        )

    def _build_model_folder_row(self) -> SettingsCard:
        """Create the managed-local model root path row."""

        self.model_folder_edit = self._path_edit("ComfyConnectionModelFolderEdit")
        set_localized_placeholder(self.model_folder_edit, "Path on the ComfyUI host")
        self.model_folder_edit.textChanged.connect(self._on_model_root_text_changed)
        browse_button = LocalizedPushButton(app_text("Browse"), self)
        browse_button.clicked.connect(self._browse_model_folder)
        self.model_folder_browse_button = browse_button
        default_button = LocalizedPushButton(app_text("Use default"), self)
        default_button.clicked.connect(self._use_default_model_folder)
        self.model_folder_default_button = default_button
        controls = self._control_row(
            self.model_folder_edit,
            browse_button,
            default_button,
        )
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.CUBE_MULTIPLE_20_REGULAR),
            title=app_text("Model folder"),
            description=(
                app_text(
                    "Changes this ComfyUI installation's model folder, including when "
                    "ComfyUI starts on its own."
                )
            ),
            trailing_widget=controls,
            reserve_visual_space=True,
            parent=self,
        )

    def _build_existing_folder_row(self) -> SettingsCard:
        """Create the existing-local workspace path row."""

        self.existing_folder_edit = self._path_edit("ComfyConnectionExistingFolderEdit")
        self.existing_folder_edit.setPlaceholderText(existing_comfy_example())
        self.existing_folder_edit.textChanged.connect(self._on_draft_changed)
        browse_button = LocalizedPushButton(app_text("Browse"), self)
        browse_button.clicked.connect(self._browse_existing_folder)
        clear_button = LocalizedPushButton(app_text("Clear"), self)
        clear_button.clicked.connect(self.existing_folder_edit.clear)
        controls = self._control_row(
            self.existing_folder_edit,
            browse_button,
            clear_button,
        )
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.FOLDER_OPEN_20_REGULAR),
            title=app_text("ComfyUI folder"),
            description=(
                app_text(
                    "Choose the folder that contains the ComfyUI installation "
                    "Substitute should launch."
                )
            ),
            trailing_widget=controls,
            reserve_visual_space=True,
            parent=self,
        )

    def _build_existing_python_row(self) -> SettingsCard:
        """Create the attached-local Python executable row."""

        self.existing_python_edit = self._path_edit("ComfyConnectionExistingPythonEdit")
        set_localized_placeholder(self.existing_python_edit, "Automatically detect")
        self.existing_python_edit.textChanged.connect(self._on_draft_changed)
        browse_button = LocalizedPushButton(app_text("Browse"), self)
        browse_button.clicked.connect(self._browse_existing_python)
        clear_button = LocalizedPushButton(app_text("Auto-detect"), self)
        clear_button.clicked.connect(self.existing_python_edit.clear)
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.SERVER_20_REGULAR),
            title=app_text("Python executable"),
            description=app_text(
                "The Python environment this ComfyUI installation uses."
            ),
            trailing_widget=self._control_row(
                self.existing_python_edit,
                browse_button,
                clear_button,
            ),
            reserve_visual_space=True,
            parent=self,
        )

    def _build_setup_action_row(self) -> SettingsCard:
        """Create the local setup wizard action row."""

        wizard_button = LocalizedPushButton(app_text("Open setup wizard"), self)
        wizard_button.clicked.connect(self._open_reconfigure_window)
        self.wizard_button = wizard_button
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.TOOLBOX_20_REGULAR),
            title=app_text("Setup wizard"),
            description=app_text("Open guided setup for this local ComfyUI source."),
            trailing_widget=wizard_button,
            reserve_visual_space=True,
            parent=self,
        )

    def _build_actions_widget(self) -> QWidget:
        """Create the page-level save and discard command area."""

        widget = QWidget(self)
        widget.setObjectName("ComfyConnectionActions")
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        widget.setStyleSheet("background-color: transparent; border: none;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        self.save_button = LocalizedPrimaryPushButton(app_text("Save changes"), widget)
        self.save_button.clicked.connect(self._save_changes)
        self.discard_button = LocalizedPushButton(app_text("Discard changes"), widget)
        self.discard_button.clicked.connect(self._discard_changes)
        layout.addWidget(
            SettingsControlGroup(
                self.discard_button,
                self.save_button,
                parent=widget,
            )
        )
        return widget

    def _path_edit(self, object_name: str) -> LineEdit:
        """Create a fixed-width path edit used by folder rows."""

        edit = LineEdit(self)
        edit.setObjectName(object_name)
        configure_settings_field_width(edit, preferred_width=_PATH_FIELD_WIDTH)
        return edit

    def _control_row(self, *widgets: QWidget) -> QWidget:
        """Create a compact right-aligned control group for one settings row."""

        return SettingsControlGroup(*widgets, parent=self)

    def _icon_widget(self, icon: Any) -> IconWidget:
        """Create one fixed-size Settings card icon."""

        widget = IconWidget(icon, self)
        widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
        return widget

    def _apply_snapshot(self, snapshot: ComfyConnectionSettingsSnapshot) -> None:
        """Mirror one service snapshot into the editable controls."""

        self._loaded_draft = _draft_from_snapshot(snapshot)
        self._model_root_management_available = snapshot.model_root_management_available
        self._default_managed_model_root = snapshot.default_managed_model_root
        self._apply_draft(self._loaded_draft)
        self.connection_feedback_bar.clear()
        apply_application_text(
            self.connection_check_row.description_label,
            snapshot.status_message,
        )
        self._sync_mode_rows()
        self._sync_dirty_state()

    def _apply_draft(self, draft: ComfyConnectionSettingsDraft) -> None:
        """Mirror one editable draft into the form controls."""

        self._is_loading = True
        try:
            self._set_mode(draft.mode)
            self.host_edit.setText(draft.host)
            self.port_spinbox.setValue(draft.port)
            self._managed_model_root_uses_default = (
                draft.managed_model_root_uses_default
            )
            self.model_folder_edit.setText(_path_text(draft.managed_model_root))
            if draft.mode is ComfyTargetMode.MANAGED_LOCAL:
                self.managed_folder_edit.setText(
                    _path_text(draft.managed_workspace_path)
                )
                self.existing_folder_edit.setText("")
                self.existing_python_edit.setText("")
            elif draft.mode is ComfyTargetMode.ATTACHED_LOCAL:
                self.managed_folder_edit.setText("")
                self.existing_folder_edit.setText(
                    _path_text(draft.attached_workspace_path)
                )
                self.existing_python_edit.setText(
                    _path_text(draft.attached_python_executable)
                )
            else:
                self.managed_folder_edit.setText("")
                self.existing_folder_edit.setText("")
                self.existing_python_edit.setText("")
        finally:
            self._is_loading = False
        self._sync_mode_rows()
        self._sync_dirty_state()

    def _set_mode(self, mode: ComfyTargetMode) -> None:
        """Select one target mode without changing unrelated form fields."""

        self.source_selector.set_selected_mode(mode)

    def _selected_mode(self) -> ComfyTargetMode:
        """Return the current source selector mode."""

        return self.source_selector.selected_mode()

    def _on_source_mode_changed(self, mode: object) -> None:
        """Handle source selector changes using the normal draft-change path."""

        if not isinstance(mode, ComfyTargetMode):
            return
        self._on_draft_changed()

    def _on_draft_changed(self, *_args: object) -> None:
        """Update dependent rows and save state after a form edit."""

        if self._is_loading:
            return
        self._sync_mode_rows()
        self._sync_dirty_state()

    def _on_managed_folder_text_changed(self, *_args: object) -> None:
        """Keep the default model folder aligned with the managed workspace."""

        if self._is_loading:
            self._on_draft_changed()
            return
        if self._managed_model_root_uses_default:
            self._set_model_folder_text(
                _path_text(
                    _default_model_root(_optional_path(self.managed_folder_edit.text()))
                )
            )
        self._on_draft_changed()

    def _set_model_folder_text(self, text: str) -> None:
        """Set model-folder text without changing the default/override flag."""

        was_loading = self._is_loading
        self._is_loading = True
        try:
            self.model_folder_edit.setText(text)
        finally:
            self._is_loading = was_loading

    def _sync_mode_rows(self) -> None:
        """Project the selected source mode into the visible settings layout."""

        mode = self._selected_mode()
        is_managed = mode is ComfyTargetMode.MANAGED_LOCAL
        is_existing = mode is ComfyTargetMode.ATTACHED_LOCAL
        is_remote = mode is ComfyTargetMode.REMOTE
        self.managed_folder_row.setVisible(is_managed)
        self.model_folder_row.setVisible(self._model_root_management_available)
        self.model_folder_browse_button.setVisible(not is_remote)
        self.existing_folder_row.setVisible(is_existing)
        self.existing_python_row.setVisible(is_existing)
        self.setup_action_row.setVisible(not is_remote)
        if is_remote:
            self.configuration_group.set_heading(app_text("Remote server"))
            set_localized_text(self.endpoint_row.title_label, "Server endpoint")
            set_localized_text(
                self.endpoint_row.description_label,
                "Substitute connects to this ComfyUI server.",
            )
            return
        if is_existing:
            self.configuration_group.set_heading(app_text("Existing local setup"))
        else:
            self.configuration_group.set_heading(app_text("Managed local setup"))
        set_localized_text(self.endpoint_row.title_label, "Local endpoint")
        set_localized_text(
            self.endpoint_row.description_label,
            "Substitute connects to the local ComfyUI process at this address.",
        )

    def _sync_dirty_state(self) -> None:
        """Enable page actions only when the draft differs from loaded state."""

        is_dirty = self._loaded_draft is not None and (
            self._current_draft() != self._loaded_draft
        )
        self.save_button.setEnabled(is_dirty and not self._save_in_flight)
        self.discard_button.setEnabled(is_dirty and not self._save_in_flight)

    def _current_draft(self) -> ComfyConnectionSettingsDraft:
        """Return the current form values as a save draft."""

        return ComfyConnectionSettingsDraft(
            mode=self._selected_mode(),
            host=self.host_edit.text(),
            port=self.port_spinbox.value(),
            managed_workspace_path=_optional_path(self.managed_folder_edit.text()),
            attached_workspace_path=_optional_path(self.existing_folder_edit.text()),
            attached_python_executable=_optional_path(self.existing_python_edit.text()),
            managed_model_root=_optional_text(self.model_folder_edit.text()),
            managed_model_root_uses_default=self._managed_model_root_uses_default,
        )

    def _test_connection(self) -> None:
        """Test the current endpoint without saving form changes."""

        host = self.host_edit.text()
        port = self.port_spinbox.value()
        self.test_button.setEnabled(False)
        self._run_task(
            task_id=_TEST_ENDPOINT_TASK_ID,
            operation=lambda: self._service.test_endpoint(host, port),
        )

    def _render_test_result(self, result: ComfyConnectionSaveResult) -> None:
        """Render one endpoint-test result in the status row."""

        apply_application_text(
            self.connection_check_row.description_label,
            result.message,
        )
        self.connection_feedback_bar.show_message(
            severity="success" if result.succeeded else "error",
            title=(
                app_text("Connection check succeeded")
                if result.succeeded
                else app_text("Connection check failed")
            ),
            message=result.message,
        )

    def _save_changes(self) -> None:
        """Validate and persist the current Comfy target draft."""

        draft = self._current_draft()
        self._save_in_flight = True
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self._run_task(
            task_id=_SAVE_DRAFT_TASK_ID,
            operation=lambda: self._service.save_draft(draft),
        )

    def _discard_changes(self) -> None:
        """Restore the last loaded connection draft."""

        if self._loaded_draft is None:
            return
        self._apply_draft(self._loaded_draft)
        self.connection_feedback_bar.clear()

    def _run_task(
        self,
        *,
        task_id: str,
        operation: Callable[[], object],
    ) -> None:
        """Schedule one Comfy connection operation on the Settings async runner."""

        self._task_generation += 1
        self._active_task_generations[task_id] = self._task_generation
        self._async_runner.run(
            task_id=task_id,
            generation=self._task_generation,
            operation=operation,
            context={"page": "comfy_connection"},
        )

    def _apply_task_result(self, payload: object) -> None:
        """Apply one completed async Comfy connection task result."""

        if not isinstance(payload, SettingsAsyncTaskResult):
            return
        if payload.generation != self._active_task_generations.get(payload.task_id):
            return
        self._active_task_generations.pop(payload.task_id, None)
        if payload.task_id == _LOAD_SNAPSHOT_TASK_ID:
            self._apply_load_result(payload)
        elif payload.task_id == _TEST_ENDPOINT_TASK_ID:
            self._apply_test_result(payload)
        elif payload.task_id == _SAVE_DRAFT_TASK_ID:
            self._apply_save_result(payload)

    def _apply_load_result(self, result: SettingsAsyncTaskResult) -> None:
        """Bind a loaded snapshot or show the existing degraded load state."""

        self._set_load_busy(False)
        if isinstance(result.value, ComfyConnectionSettingsSnapshot):
            self._apply_snapshot(result.value)
            return
        self.save_button.setEnabled(False)

    def _apply_test_result(self, result: SettingsAsyncTaskResult) -> None:
        """Render a completed connection test result."""

        self.test_button.setEnabled(True)
        if isinstance(result.value, ComfyConnectionSaveResult):
            self._render_test_result(result.value)

    def _apply_save_result(self, result: SettingsAsyncTaskResult) -> None:
        """Apply a completed save command result."""

        self._save_in_flight = False
        if isinstance(result.value, ComfyConnectionSaveResult):
            if result.value.succeeded:
                if (
                    result.value.restart_snapshot is not None
                    and result.value.restart_snapshot.count > 0
                    and self._show_restart_requirements is not None
                ):
                    self._show_restart_requirements()
                self.reload()
                return
            self._sync_dirty_state()
            return
        self._sync_dirty_state()

    def _set_load_busy(self, busy: bool) -> None:
        """Disable load-related actions while a snapshot load is in flight."""

        self.refresh_button.setEnabled(not busy)

    def _browse_managed_folder(self) -> None:
        """Prompt for a managed ComfyUI workspace folder."""

        selected = QFileDialog.getExistingDirectory(
            self,
            translate_application_text("Choose Managed ComfyUI Folder"),
            self.managed_folder_edit.text(),
        )
        if selected:
            self.managed_folder_edit.setText(selected)

    def _browse_existing_folder(self) -> None:
        """Prompt for an existing local ComfyUI workspace folder."""

        selected = QFileDialog.getExistingDirectory(
            self,
            translate_application_text("Choose Existing ComfyUI Folder"),
            self.existing_folder_edit.text(),
        )
        if selected:
            self.existing_folder_edit.setText(selected)

    def _browse_existing_python(self) -> None:
        """Prompt for the Python executable used by existing local ComfyUI."""

        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            translate_application_text("Choose ComfyUI Python Executable"),
            self.existing_python_edit.text(),
            translate_application_text(
                "Python executable (python.exe python);;All files (*)"
            ),
        )
        if selected:
            self.existing_python_edit.setText(selected)

    def _browse_model_folder(self) -> None:
        """Prompt for a managed ComfyUI model folder."""

        selected = QFileDialog.getExistingDirectory(
            self,
            translate_application_text("Choose Model Folder"),
            self.model_folder_edit.text(),
        )
        if selected:
            self._managed_model_root_uses_default = False
            self.model_folder_edit.setText(selected)

    def _use_default_model_folder(self) -> None:
        """Reset the model folder to the connected ComfyUI host's default."""

        self._set_model_folder_text(_path_text(self._default_managed_model_root))
        self._managed_model_root_uses_default = True
        self._on_draft_changed()

    def _on_model_root_text_changed(self, *_args: object) -> None:
        """Treat direct model-folder edits as explicit overrides."""

        if not self._is_loading:
            self._managed_model_root_uses_default = False
        self._on_draft_changed()


def _optional_path(text: str) -> Path | None:
    """Return a path from non-empty text."""

    stripped = text.strip()
    return Path(stripped) if stripped else None


def _optional_text(text: str) -> str | None:
    """Return stripped text unless the field is empty."""

    stripped = text.strip()
    return stripped or None


def _path_text(path: Path | str | None) -> str:
    """Return display text for an optional path."""

    return "" if path is None else str(path)


def _default_model_root(workspace: Path | None) -> Path | None:
    """Return the default models folder for one managed ComfyUI workspace."""

    return workspace / "models" if workspace is not None else None


def _port_field_width(spinbox: SpinBox) -> int:
    """Return a compact port width sized for typed five-digit ports."""

    return max(_PORT_FIELD_MIN_WIDTH, int(spinbox.sizeHint().width()))


def _draft_from_snapshot(
    snapshot: ComfyConnectionSettingsSnapshot,
) -> ComfyConnectionSettingsDraft:
    """Return the editable draft represented by a loaded snapshot."""

    target = snapshot.target
    managed_path = (
        target.workspace_path if target.mode is ComfyTargetMode.MANAGED_LOCAL else None
    )
    attached_path = (
        target.workspace_path if target.mode is ComfyTargetMode.ATTACHED_LOCAL else None
    )
    return ComfyConnectionSettingsDraft(
        mode=target.mode,
        host=target.endpoint.host,
        port=target.endpoint.port,
        managed_workspace_path=managed_path,
        attached_workspace_path=attached_path,
        attached_python_executable=(
            target.python_binding.executable
            if target.python_binding is not None
            else None
        ),
        managed_model_root=_path_text(
            snapshot.managed_model_root or _default_model_root(managed_path)
        ),
        managed_model_root_uses_default=snapshot.managed_model_root_uses_default,
    )


__all__ = ["ComfyConnectionSettingsPage"]
