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

"""Render prompt editor feature preferences in Settings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    IconWidget,
    IndicatorPosition,
    PushButton,
    SwitchButton,
)

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorPreferenceService,
    PromptFeatureDefinition,
    PromptWheelAdjustmentMode,
    prompt_feature_definitions,
)
from substitute.application.prompt_wildcards import (
    PromptWildcardFileManagementService,
    PromptWildcardPreferenceService,
)
from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_control_group import SettingsControlGroup
from substitute.presentation.settings.prompt_editor_icons import (
    PROMPT_WHEEL_ADJUSTMENT_SETTINGS_ICON,
    PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON,
    PROMPT_WILDCARD_RESOLUTION_SETTINGS_ICON,
    prompt_feature_settings_icon,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_TOP_MARGIN,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.settings.prompt_editor_page")
_HIDDEN_FEATURES = {
    PromptEditorFeature.DANBOORU_URL_IMPORT,
    PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
}


class PromptEditorSettingsPage(QWidget):
    """Expose prompt editor feature toggles backed by user preferences."""

    def __init__(
        self,
        *,
        preference_service: PromptEditorPreferenceService,
        wildcard_preference_service: PromptWildcardPreferenceService | None = None,
        wildcard_file_management_service: (
            PromptWildcardFileManagementService | None
        ) = None,
        open_wildcard_management_modal: Callable[[QWidget | None], None] | None = None,
        preferences_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the prompt editor settings page."""

        super().__init__(parent)
        self._preference_service = preference_service
        self._wildcard_preference_service = wildcard_preference_service
        self._wildcard_file_management_service = wildcard_file_management_service
        self._open_wildcard_management_modal = open_wildcard_management_modal
        self._preferences_changed = preferences_changed
        self._is_loading_wildcards = False
        self._feature_switches: dict[PromptEditorFeature, SwitchButton] = {}
        self._feature_rows: dict[PromptEditorFeature, InteractiveSettingsCard] = {}
        self._wheel_hover_adjust_switch: SwitchButton | None = None
        self._wheel_hover_adjust_row: InteractiveSettingsCard | None = None
        self._wildcard_resolve_switch: SwitchButton | None = None
        self._wildcard_management_row_widget: SettingsCard | None = None
        self._build_layout()
        self.reload()

    def reload(self) -> None:
        """Reload visible toggle state from persisted preferences."""

        preferences = self._preference_service.load_preferences()
        for feature, switch in self._feature_switches.items():
            switch.blockSignals(True)
            switch.setChecked(preferences.user_allows(feature))
            switch.blockSignals(False)
        if self._wheel_hover_adjust_switch is not None:
            self._wheel_hover_adjust_switch.blockSignals(True)
            self._wheel_hover_adjust_switch.setChecked(
                preferences.wheel_adjustment_mode
                is PromptWheelAdjustmentMode.HOVER_DWELL
            )
            self._wheel_hover_adjust_switch.blockSignals(False)
        if (
            self._wildcard_preference_service is not None
            and self._wildcard_resolve_switch is not None
        ):
            wildcard_preferences = self._wildcard_preference_service.load_preferences()
            self._is_loading_wildcards = True
            try:
                self._wildcard_resolve_switch.setChecked(
                    wildcard_preferences.resolve_on_generation
                )
            finally:
                self._is_loading_wildcards = False

    def feature_labels(self) -> tuple[str, ...]:
        """Return visible feature labels for tests and diagnostics."""

        return tuple(
            definition.label
            for definition in prompt_feature_definitions()
            if definition.feature not in _HIDDEN_FEATURES
        )

    def is_feature_allowed(self, feature: PromptEditorFeature) -> bool:
        """Return whether one feature toggle is currently checked."""

        return bool(self._feature_switches[feature].isChecked())

    def set_feature_allowed(
        self,
        feature: PromptEditorFeature,
        allowed: bool,
    ) -> None:
        """Set one feature toggle through the same path a user click uses."""

        self._feature_switches[feature].setChecked(allowed)

    def set_wildcard_resolution_enabled(self, enabled: bool) -> None:
        """Set wildcard preprocessing through the same path a user click uses."""

        if self._wildcard_resolve_switch is not None:
            self._wildcard_resolve_switch.setChecked(enabled)

    def is_wheel_hover_adjustment_enabled(self) -> bool:
        """Return whether hover dwell can authorize wheel adjustment."""

        return bool(
            self._wheel_hover_adjust_switch is not None
            and self._wheel_hover_adjust_switch.isChecked()
        )

    def set_wheel_hover_adjustment_enabled(self, enabled: bool) -> None:
        """Set wheel hover adjustment through the same path a user click uses."""

        if self._wheel_hover_adjust_switch is not None:
            self._wheel_hover_adjust_switch.setChecked(enabled)

    def _build_layout(self) -> None:
        """Create the prompt feature settings controls layout."""

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)
        content = self._build_content_widget()
        page_layout.addWidget(content)
        page_layout.addStretch(1)

    def _build_content_widget(self) -> QWidget:
        """Create the prompt feature controls content widget."""

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        content_layout.addWidget(
            SettingsCardGroup(
                "Interaction",
                cards=(self._wheel_hover_adjustment_row(),),
                parent=self,
            )
        )
        feature_cards: list[SettingsCard] = []
        for definition in prompt_feature_definitions():
            if definition.feature in _HIDDEN_FEATURES:
                continue
            feature_cards.append(self._feature_row(definition))
        content_layout.addWidget(
            SettingsCardGroup(
                "Editor features",
                cards=tuple(feature_cards),
                parent=self,
            )
        )
        wildcard_cards: list[SettingsCard] = []
        if self._wildcard_preference_service is not None:
            wildcard_cards.append(self._wildcard_resolution_row())
        if (
            self._wildcard_file_management_service is not None
            or self._open_wildcard_management_modal is not None
        ):
            wildcard_cards.append(self._wildcard_management_row())
        if wildcard_cards:
            content_layout.addWidget(
                SettingsCardGroup(
                    "Wildcards",
                    cards=tuple(wildcard_cards),
                    parent=self,
                )
            )
        content_layout.addStretch(1)
        return content

    def _feature_row(
        self, definition: PromptFeatureDefinition
    ) -> InteractiveSettingsCard:
        """Create one feature preference row."""

        feature = definition.feature
        switch = SwitchButton("Off", self, indicatorPos=IndicatorPosition.RIGHT)
        switch.setOnText("On")
        switch.setOffText("Off")
        switch.checkedChanged.connect(
            lambda checked, item=feature: self._set_feature_allowed(item, checked)
        )
        row = InteractiveSettingsCard(
            visual_widget=self._icon_widget(prompt_feature_settings_icon(feature)),
            title=definition.label,
            description=definition.description,
            trailing_widget=switch,
            reserve_visual_space=True,
            parent=self,
        )
        self._feature_switches[feature] = switch
        self._feature_rows[feature] = row
        row.activated.connect(lambda item=feature: self._toggle_feature_from_row(item))
        return row

    def _wheel_hover_adjustment_row(self) -> InteractiveSettingsCard:
        """Create the mouse-wheel hover adjustment policy row."""

        switch = SwitchButton("Off", self, indicatorPos=IndicatorPosition.RIGHT)
        switch.setOnText("On")
        switch.setOffText("Off")
        switch.checkedChanged.connect(self._set_wheel_hover_adjustment_enabled)
        row = InteractiveSettingsCard(
            visual_widget=self._icon_widget(PROMPT_WHEEL_ADJUSTMENT_SETTINGS_ICON),
            title="Wheel adjust after hover",
            description=(
                "When off, click or focus a control before the mouse wheel can "
                "change it."
            ),
            trailing_widget=switch,
            reserve_visual_space=True,
            parent=self,
        )
        self._wheel_hover_adjust_switch = switch
        self._wheel_hover_adjust_row = row
        row.activated.connect(lambda: switch.setChecked(not switch.isChecked()))
        return row

    def _wildcard_resolution_row(self) -> InteractiveSettingsCard:
        """Create the wildcard generation preprocessing toggle row."""

        switch = SwitchButton("Off", self, indicatorPos=IndicatorPosition.RIGHT)
        switch.setOnText("On")
        switch.setOffText("Off")
        switch.checkedChanged.connect(self._set_wildcard_resolution_enabled)
        self._wildcard_resolve_switch = switch
        row = InteractiveSettingsCard(
            visual_widget=self._icon_widget(PROMPT_WILDCARD_RESOLUTION_SETTINGS_ICON),
            title="Resolve wildcards on generation",
            description=(
                "Expand wildcard prompt text before sending queued workflows to Comfy."
            ),
            trailing_widget=switch,
            reserve_visual_space=True,
            parent=self,
        )
        row.activated.connect(lambda: switch.setChecked(not switch.isChecked()))
        return row

    def _wildcard_management_row(self) -> SettingsCard:
        """Create the user wildcard folder management action row."""

        manage_button = PushButton("Manage", self)
        manage_button.clicked.connect(self._open_wildcard_management)
        open_button = PushButton("Open folder", self)
        open_button.clicked.connect(self._open_wildcard_folder)
        refresh_button = PushButton("Refresh", self)
        refresh_button.clicked.connect(self._refresh_wildcard_catalog)
        controls = self._control_row(
            manage_button,
            open_button,
            refresh_button,
        )
        row = SettingsCard(
            visual_widget=self._icon_widget(PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON),
            title="Manage wildcards",
            description="Edit user wildcard files and refresh prompt metadata.",
            trailing_widget=controls,
            reserve_visual_space=True,
            parent=self,
        )
        self._wildcard_management_row_widget = row
        return row

    def _toggle_feature_from_row(self, feature: PromptEditorFeature) -> None:
        """Invert one feature switch when its row body is clicked."""

        switch = self._feature_switches[feature]
        switch.setChecked(not switch.isChecked())

    def _set_feature_allowed(
        self,
        feature: PromptEditorFeature,
        allowed: bool,
    ) -> None:
        """Persist one feature preference change."""

        self._preference_service.set_feature_allowed(feature, allowed)
        if self._preferences_changed is not None:
            self._preferences_changed()

    def _set_wheel_hover_adjustment_enabled(self, enabled: bool) -> None:
        """Persist whether pointer hover dwell may authorize wheel adjustment."""

        self._preference_service.set_wheel_adjustment_mode(
            PromptWheelAdjustmentMode.HOVER_DWELL
            if enabled
            else PromptWheelAdjustmentMode.FOCUS_REQUIRED
        )
        if self._preferences_changed is not None:
            self._preferences_changed()

    def _set_wildcard_resolution_enabled(self, enabled: bool) -> None:
        """Persist whether wildcard preprocessing runs during generation."""

        if self._wildcard_preference_service is None:
            return
        if self._is_loading_wildcards:
            return
        self._wildcard_preference_service.set_resolve_on_generation(enabled)

    def _control_row(self, *widgets: QWidget) -> QWidget:
        """Create a compact right-aligned control group for one settings row."""

        return SettingsControlGroup(*widgets, parent=self)

    def _icon_widget(self, icon: Any) -> IconWidget:
        """Create one fixed-size Settings card icon."""

        widget = IconWidget(icon, self)
        widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
        return widget

    def _open_wildcard_management(self) -> None:
        """Open the reusable wildcard management modal."""

        if self._open_wildcard_management_modal is not None:
            self._open_wildcard_management_modal(self)

    def _open_wildcard_folder(self) -> None:
        """Open the managed user wildcard folder in the desktop file manager."""

        if self._wildcard_file_management_service is None:
            return
        root = self._wildcard_file_management_service.root_path()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    def _refresh_wildcard_catalog(self) -> None:
        """Refresh wildcard catalog caches after external file edits."""

        if self._wildcard_file_management_service is not None:
            self._wildcard_file_management_service.refresh_cache()


__all__ = ["PromptEditorSettingsPage"]
