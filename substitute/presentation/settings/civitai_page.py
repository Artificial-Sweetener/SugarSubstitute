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

"""Render CivitAI integration preferences in Settings."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.localization import LocalizedSwitchButton

from sugarsubstitute_shared.presentation.localization import (
    LocalizedComboItem,
    apply_application_text,
    render_application_text,
    set_localized_placeholder,
    set_localized_text,
    set_localized_combo_items,
)
from substitute.presentation.localization import LocalizedPushButton

from typing import Any

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    ComboBox,
    IconWidget,
    IndicatorPosition,
    LineEdit,
    SwitchButton,
)

from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
)
from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.civitai_credential_status import (
    api_key_status_text,
)
from substitute.presentation.settings.settings_cache_size import format_cache_size
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_TOP_MARGIN,
)
from substitute.presentation.settings.path_pattern_token_autocomplete import (
    PathPatternTokenAutocomplete,
    PathPatternTokenSuggestion,
)
from substitute.presentation.resources.app_icon import AppIcon

_COMBO_WIDTH = 220
_API_KEY_WIDTH = 320
_DOWNLOAD_PATTERN_WIDTH = 360
_DOWNLOAD_PREVIEW_WIDTH = 420


class CivitaiSettingsPage(QWidget):
    """Expose CivitAI policy, credentials, and cache maintenance."""

    def __init__(
        self,
        *,
        preference_service: CivitaiPreferenceService,
        credential_service: CivitaiCredentialService,
        cache_service: CivitaiCacheService,
        parent: QWidget | None = None,
    ) -> None:
        """Build the dedicated CivitAI settings page."""

        super().__init__(parent)
        self._preference_service = preference_service
        self._credential_service = credential_service
        self._cache_service = cache_service
        self._is_loading = False
        self._metadata_lookup_switch = self._switch()
        self._missing_model_lookup_switch = self._switch()
        self._thumbnail_downloads_switch = self._switch()
        self._downloads_switch = self._switch()
        self._thumbnail_policy_combo = self._thumbnail_policy_combo_widget()
        self.download_path_pattern_edit = self._download_path_pattern_edit()
        self.download_path_preview_edit = self._download_path_preview_edit()
        self.download_token_autocomplete: PathPatternTokenAutocomplete | None = None
        self._api_key_edit = LineEdit(self)
        set_localized_placeholder(self._api_key_edit, "Paste CivitAI API key")
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        configure_settings_field_width(
            self._api_key_edit,
            preferred_width=_API_KEY_WIDTH,
        )
        self._api_key_status_label = BodyLabel("", self)
        self._api_key_set_button = LocalizedPushButton(app_text("Set/update"), self)
        self._api_key_test_button = LocalizedPushButton(app_text("Test"), self)
        self._api_key_clear_button = LocalizedPushButton(app_text("Clear"), self)
        self._cache_summary_label = BodyLabel("", self)
        self._install_download_token_autocomplete()
        self._build_layout()
        self.reload()

    def reload(self) -> None:
        """Reload visible controls from persisted CivitAI settings."""

        preferences = self._preference_service.load_preferences()
        cache_summary = self._cache_service.cache_summary()
        self._is_loading = True
        try:
            self._metadata_lookup_switch.setChecked(preferences.metadata_lookup_enabled)
            self._missing_model_lookup_switch.setChecked(
                preferences.missing_model_lookup_enabled
            )
            self._thumbnail_downloads_switch.setChecked(
                preferences.thumbnail_downloads_enabled
            )
            self._downloads_switch.setChecked(preferences.downloads_enabled)
            self.download_path_pattern_edit.setText(preferences.download_path_pattern)
            self._set_combo_data(
                self._thumbnail_policy_combo,
                preferences.thumbnail_safety_policy.value,
            )
            self._thumbnail_policy_combo.setEnabled(
                preferences.thumbnail_downloads_enabled
            )
            self._api_key_edit.clear()
            storage_status = self._credential_service.storage_status()
            storage_available = storage_status.available
            self._api_key_set_button.setEnabled(storage_available)
            self._api_key_clear_button.setEnabled(storage_available)
            apply_application_text(
                self._api_key_status_label,
                api_key_status_text(
                    status=storage_status,
                    has_key=(
                        self._credential_service.has_api_key()
                        if storage_available
                        else False
                    ),
                ),
            )
            set_localized_text(
                self._cache_summary_label,
                "%1 provider records, %2 thumbnail sources, %3 variants, %4",
                cache_summary.provider_record_count,
                cache_summary.thumbnail_source_count,
                cache_summary.thumbnail_variant_count,
                format_cache_size(cache_summary.thumbnail_bytes),
            )
        finally:
            self._is_loading = False
        self._refresh_download_path_preview()

    def selected_thumbnail_policy_value(self) -> str:
        """Return the currently selected CivitAI thumbnail safety policy."""

        value = self._thumbnail_policy_combo.currentData()
        assert isinstance(value, str)
        return value

    def cache_summary_text(self) -> str:
        """Return visible cache summary text for tests and diagnostics."""

        return str(self._cache_summary_label.text())

    def api_key_status_text(self) -> str:
        """Return visible API key status text for tests and diagnostics."""

        return str(self._api_key_status_label.text())

    def set_download_path_pattern(self, pattern: str) -> None:
        """Set the CivitAI download path pattern and refresh the preview."""

        self.download_path_pattern_edit.setText(pattern)
        self._refresh_download_path_preview()

    def download_path_preview_text(self) -> str:
        """Return the current CivitAI download path preview text."""

        return str(self.download_path_preview_edit.text())

    def _build_layout(self) -> None:
        """Create the CivitAI settings layout and grouped controls."""

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)
        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        content_layout.addWidget(
            SettingsCardGroup(
                app_text("API key"),
                cards=(
                    self._api_key_status_row(),
                    self._api_key_actions_row(),
                ),
                parent=self,
            )
        )
        content_layout.addWidget(
            SettingsCardGroup(
                app_text("Lookup and downloads"),
                cards=(
                    self._metadata_lookup_row(),
                    self._missing_model_lookup_row(),
                    self._downloads_row(),
                ),
                parent=self,
            )
        )
        content_layout.addWidget(
            SettingsCardGroup(
                app_text("Download organization"),
                cards=(
                    self._download_path_pattern_row(),
                    self._download_path_preview_row(),
                ),
                parent=self,
            )
        )
        content_layout.addWidget(
            SettingsCardGroup(
                app_text("Thumbnails"),
                cards=(
                    self._thumbnail_downloads_row(),
                    self._thumbnail_policy_row(),
                ),
                parent=self,
            )
        )
        content_layout.addWidget(
            SettingsCardGroup(
                app_text("Cache"),
                cards=(
                    self._cache_summary_row(),
                    self._cache_actions_row(),
                ),
                parent=self,
            )
        )
        content_layout.addStretch(1)
        page_layout.addWidget(content)
        page_layout.addStretch(1)

    def _api_key_status_row(self) -> SettingsCard:
        """Create the read-only API key status row."""

        return SettingsCard(
            visual_widget=self._icon_widget(
                AppIcon.PLUG_CONNECTED_CHECKMARK_20_REGULAR
            ),
            title=app_text("API key status"),
            description=app_text(
                "Used for authenticated CivitAI lookups and downloads."
            ),
            trailing_widget=SettingsControlGroup(
                self._api_key_status_label,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=680,
            parent=self,
        )

    def _api_key_actions_row(self) -> SettingsCard:
        """Create the API key set, test, and clear controls."""

        self._api_key_set_button.clicked.connect(self._set_api_key)
        self._api_key_test_button.clicked.connect(self._test_api_key)
        self._api_key_clear_button.clicked.connect(self._clear_api_key)
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.KEY_20_REGULAR),
            title=app_text("API key"),
            description=app_text(
                "The key is stored in your operating system's secure credential store."
            ),
            trailing_widget=SettingsControlGroup(
                self._api_key_edit,
                self._api_key_set_button,
                self._api_key_test_button,
                self._api_key_clear_button,
                spacing=6,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=780,
            parent=self,
        )

    def _metadata_lookup_row(self) -> InteractiveSettingsCard:
        """Create the startup metadata lookup toggle row."""

        self._metadata_lookup_switch.checkedChanged.connect(
            self._set_metadata_lookup_enabled
        )
        return self._toggle_row(
            icon=AppIcon.DATABASE_SEARCH_20_REGULAR,
            title=app_text("Look up local model metadata"),
            description=app_text(
                "Query CivitAI for hashes already known in the local model cache."
            ),
            switch=self._metadata_lookup_switch,
        )

    def _missing_model_lookup_row(self) -> InteractiveSettingsCard:
        """Create the missing recipe model lookup toggle row."""

        self._missing_model_lookup_switch.checkedChanged.connect(
            self._set_missing_model_lookup_enabled
        )
        return self._toggle_row(
            icon=AppIcon.BOX_SEARCH_20_REGULAR,
            title=app_text("Look up missing recipe models"),
            description=app_text(
                "Use CivitAI only after local recipe model matching fails."
            ),
            switch=self._missing_model_lookup_switch,
        )

    def _downloads_row(self) -> InteractiveSettingsCard:
        """Create the CivitAI model downloads toggle row."""

        self._downloads_switch.checkedChanged.connect(self._set_downloads_enabled)
        return self._toggle_row(
            icon=AppIcon.ARROW_DOWNLOAD_20_REGULAR,
            title=app_text("Offer verified model downloads"),
            description=app_text(
                "Allow missing-model resolution to offer CivitAI downloads."
            ),
            switch=self._downloads_switch,
        )

    def _download_path_pattern_edit(self) -> LineEdit:
        """Create the CivitAI download pattern field."""

        edit = LineEdit(self)
        edit.setObjectName("CivitaiDownloadPathPatternEdit")
        configure_settings_field_width(edit, preferred_width=_DOWNLOAD_PATTERN_WIDTH)
        edit.textChanged.connect(lambda _text: self._refresh_download_path_preview())
        edit.editingFinished.connect(self._save_download_path_pattern)
        return edit

    def _download_path_preview_edit(self) -> LineEdit:
        """Create the read-only CivitAI download path preview field."""

        edit = LineEdit(self)
        edit.setObjectName("CivitaiDownloadPathPreviewEdit")
        edit.setReadOnly(True)
        configure_settings_field_width(edit, preferred_width=_DOWNLOAD_PREVIEW_WIDTH)
        return edit

    def _download_path_pattern_row(self) -> SettingsCard:
        """Create the CivitAI download folder pattern row."""

        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.FOLDER_OPEN_20_REGULAR),
            title=app_text("Model folder pattern"),
            description=app_text(
                "Organize downloaded models inside the matching Comfy model folder."
            ),
            trailing_widget=SettingsControlGroup(
                self.download_path_pattern_edit,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=640,
            parent=self,
        )

    def _download_path_preview_row(self) -> SettingsCard:
        """Create the CivitAI download path preview row."""

        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.DOCUMENT_TEXT_20_REGULAR),
            title=app_text("Download path preview"),
            description=app_text("Shows an example path using the current pattern."),
            trailing_widget=SettingsControlGroup(
                self.download_path_preview_edit,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=680,
            parent=self,
        )

    def _thumbnail_downloads_row(self) -> InteractiveSettingsCard:
        """Create the CivitAI thumbnail downloads toggle row."""

        self._thumbnail_downloads_switch.checkedChanged.connect(
            self._set_thumbnail_downloads_enabled
        )
        return self._toggle_row(
            icon=AppIcon.IMAGE_MULTIPLE_20_REGULAR,
            title=app_text("Download CivitAI thumbnails"),
            description=app_text(
                "Download provider images for model picker thumbnails."
            ),
            switch=self._thumbnail_downloads_switch,
        )

    def _thumbnail_policy_row(self) -> SettingsCard:
        """Create the thumbnail safety policy row."""

        self._thumbnail_policy_combo.currentIndexChanged.connect(
            self._set_thumbnail_safety_policy
        )
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.SHIELD_CHECKMARK_20_REGULAR),
            title=app_text("Thumbnail safety"),
            description=app_text(
                "Control which CivitAI images may be used as thumbnails."
            ),
            trailing_widget=SettingsControlGroup(
                self._thumbnail_policy_combo,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=640,
            parent=self,
        )

    def _cache_summary_row(self) -> SettingsCard:
        """Create the read-only cache summary row."""

        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.DATABASE_SEARCH_20_REGULAR),
            title=app_text("Cache usage"),
            description=app_text(
                "Summarizes cached CivitAI provider metadata and thumbnails."
            ),
            trailing_widget=SettingsControlGroup(
                self._cache_summary_label,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=680,
            parent=self,
        )

    def _cache_actions_row(self) -> SettingsCard:
        """Create cache maintenance controls."""

        clear_thumbnails_button = LocalizedPushButton(
            app_text("Clear thumbnails"), self
        )
        clear_thumbnails_button.clicked.connect(self._clear_thumbnails)
        clear_metadata_button = LocalizedPushButton(app_text("Clear metadata"), self)
        clear_metadata_button.clicked.connect(self._clear_metadata)
        refresh_button = LocalizedPushButton(app_text("Refresh"), self)
        refresh_button.clicked.connect(self._refresh_metadata)
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.BROOM_20_REGULAR),
            title=app_text("Cache maintenance"),
            description=app_text(
                "Clear or refresh CivitAI-facing cached model metadata."
            ),
            trailing_widget=SettingsControlGroup(
                clear_thumbnails_button,
                clear_metadata_button,
                refresh_button,
                spacing=6,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=720,
            parent=self,
        )

    def _toggle_row(
        self,
        *,
        icon: Any,
        title: str,
        description: str,
        switch: SwitchButton,
    ) -> InteractiveSettingsCard:
        """Create one clickable toggle settings row."""

        row = InteractiveSettingsCard(
            visual_widget=self._icon_widget(icon),
            title=title,
            description=description,
            trailing_widget=switch,
            reserve_visual_space=True,
            parent=self,
        )
        row.activated.connect(lambda: switch.setChecked(not switch.isChecked()))
        return row

    def _switch(self) -> SwitchButton:
        """Create a standard on/off settings switch."""

        switch = LocalizedSwitchButton(
            "Off", self, indicatorPos=IndicatorPosition.RIGHT
        )
        return switch

    def _thumbnail_policy_combo_widget(self) -> ComboBox:
        """Create the fixed-width thumbnail safety policy combo."""

        combo = ComboBox(self)
        configure_settings_field_width(combo, preferred_width=_COMBO_WIDTH)
        set_localized_combo_items(
            combo,
            (
                LocalizedComboItem("disabled", app_text("Disabled")),
                LocalizedComboItem("sfw_only", app_text("SFW only")),
                LocalizedComboItem("allow_soft", app_text("Allow soft")),
                LocalizedComboItem("allow_all", app_text("Allow all")),
            ),
        )
        return combo

    def _install_download_token_autocomplete(self) -> None:
        """Attach token autocomplete to the CivitAI download pattern field."""

        suggestions = tuple(
            PathPatternTokenSuggestion(
                token=token.placeholder,
                description=token.description,
            )
            for token in self._preference_service.supported_download_path_token_descriptions()
        )
        self.download_token_autocomplete = PathPatternTokenAutocomplete(
            self.download_path_pattern_edit,
            suggestions,
        )

    def _set_api_key(self) -> None:
        """Persist the API key from the current editor."""

        key = self._api_key_edit.text().strip()
        if not key:
            set_localized_text(self._api_key_status_label, "Enter an API key first")
            return
        storage_status = self._credential_service.storage_status()
        if not storage_status.available:
            apply_application_text(
                self._api_key_status_label,
                api_key_status_text(status=storage_status, has_key=False),
            )
            return
        try:
            self._credential_service.save_api_key(key)
        except CredentialStorageUnavailableError as error:
            self._api_key_status_label.setText(str(error))
            return
        self.reload()

    def _test_api_key(self) -> None:
        """Test the current API key or stored key and show a concise result."""

        key = self._api_key_edit.text().strip() or None
        result = self._credential_service.test_api_key(key)
        apply_application_text(self._api_key_status_label, result.message)

    def _clear_api_key(self) -> None:
        """Clear the stored CivitAI API key."""

        self._credential_service.clear_api_key()
        self.reload()

    def _set_metadata_lookup_enabled(self, enabled: bool) -> None:
        """Persist local metadata lookup enablement."""

        if not self._is_loading:
            self._preference_service.set_metadata_lookup_enabled(enabled)

    def _set_missing_model_lookup_enabled(self, enabled: bool) -> None:
        """Persist missing recipe model lookup enablement."""

        if not self._is_loading:
            self._preference_service.set_missing_model_lookup_enabled(enabled)

    def _set_thumbnail_downloads_enabled(self, enabled: bool) -> None:
        """Persist thumbnail download enablement."""

        if self._is_loading:
            return
        self._preference_service.set_thumbnail_downloads_enabled(enabled)
        self._thumbnail_policy_combo.setEnabled(enabled)

    def _set_thumbnail_safety_policy(self, _index: int) -> None:
        """Persist the selected thumbnail safety policy."""

        if self._is_loading:
            return
        value = self._thumbnail_policy_combo.currentData()
        if isinstance(value, str):
            self._preference_service.set_thumbnail_safety_policy_value(value)

    def _set_downloads_enabled(self, enabled: bool) -> None:
        """Persist CivitAI model download enablement."""

        if not self._is_loading:
            self._preference_service.set_downloads_enabled(enabled)

    def _refresh_download_path_preview(self) -> None:
        """Render the CivitAI download destination preview."""

        if self._is_loading:
            return
        preferences = (
            self._preference_service.load_preferences().with_download_path_pattern(
                self.download_path_pattern_edit.text()
            )
        )
        try:
            preview = self._preference_service.render_download_path_preview(preferences)
        except Exception as error:
            self.download_path_preview_edit.setText(str(error))
            return
        self.download_path_preview_edit.setText(preview.display_path)

    def _save_download_path_pattern(self) -> None:
        """Persist the CivitAI download organization pattern if valid."""

        if self._is_loading:
            return
        result = self._preference_service.set_download_path_pattern(
            self.download_path_pattern_edit.text()
        )
        if not result.succeeded:
            self.download_path_preview_edit.setText(
                render_application_text(result.message)
            )
            return
        self._is_loading = True
        try:
            self.download_path_pattern_edit.setText(
                result.preferences.download_path_pattern
            )
        finally:
            self._is_loading = False
        if result.preview is not None:
            self.download_path_preview_edit.setText(result.preview.display_path)

    def _clear_thumbnails(self) -> None:
        """Delete cached CivitAI thumbnail data and refresh the summary."""

        self._cache_service.clear_civitai_thumbnails()
        self.reload()

    def _clear_metadata(self) -> None:
        """Delete cached CivitAI metadata and thumbnails."""

        self._cache_service.clear_civitai_metadata()
        self.reload()

    def _refresh_metadata(self) -> None:
        """Request metadata refresh using the current policy."""

        self._cache_service.refresh_civitai_metadata()
        self.reload()

    def _icon_widget(self, icon: Any) -> IconWidget:
        """Create one fixed-size Settings card icon."""

        widget = IconWidget(icon, self)
        widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
        return widget

    def _set_combo_data(self, combo: ComboBox, value: object) -> None:
        """Set one combo item by user data."""

        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return


__all__ = ["CivitaiSettingsPage"]
