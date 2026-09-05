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

"""Provide folder and optional-integration preference pages."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    LocalizationBindings,
    LocalizedComboItem,
    apply_application_text,
    render_application_text,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedCheckBox,
    LocalizedPushButton,
)


from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
)


from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingFieldBlock,
    OnboardingPageFrame,
    OnboardingSectionPanel,
)

_DANBOORU_SAFE_ONLY = "safe_only"
_DANBOORU_SAFE_AND_QUESTIONABLE = "safe_and_questionable"
_DANBOORU_ALL_RATINGS = "all_ratings"
_CIVITAI_SFW_ONLY = "sfw_only"
_CIVITAI_ALLOW_SOFT = "allow_soft"
_CIVITAI_ALLOW_ALL = "allow_all"


class FolderSetupPage(OnboardingPageFrame):
    """Collect model and output folder choices without exposing implementation detail."""

    managed_model_browse_requested = Signal()
    output_browse_requested = Signal()
    managed_model_default_requested = Signal()
    output_default_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the folder setup page."""

        super().__init__(
            title=app_text("Choose where files should live"),
            description=app_text(
                "These defaults work well for most people. Change them if you already keep models or finished images somewhere else."
            ),
            icon=FIF.FOLDER,
            parent=parent,
        )
        self.setObjectName("OnboardingFolderSetupPage")
        self.content_column.setMinimumWidth(720)
        self.managed_model_root_edit = LineEdit(self)
        self.managed_model_root_edit.setObjectName("OnboardingManagedModelRootEdit")
        self.output_root_edit = LineEdit(self)
        self.output_root_edit.setObjectName("OnboardingOutputRootEdit")

        self.managed_model_browse_button = LocalizedPushButton(
            app_text("Browse..."), self
        )
        self.managed_model_browse_button.setObjectName(
            "OnboardingManagedModelRootBrowseButton"
        )
        self.managed_model_default_button = LocalizedPushButton(
            app_text("Use default"), self
        )
        self.managed_model_default_button.setObjectName(
            "OnboardingManagedModelRootDefaultButton"
        )
        self.output_browse_button = LocalizedPushButton(app_text("Browse..."), self)
        self.output_browse_button.setObjectName("OnboardingOutputRootBrowseButton")
        self.output_default_button = LocalizedPushButton(app_text("Use default"), self)
        self.output_default_button.setObjectName("OnboardingOutputRootDefaultButton")

        self.managed_model_browse_button.clicked.connect(
            self.managed_model_browse_requested.emit
        )
        self.output_browse_button.clicked.connect(self.output_browse_requested.emit)
        self.managed_model_default_button.clicked.connect(
            self.managed_model_default_requested.emit
        )
        self.output_default_button.clicked.connect(self.output_default_requested.emit)

        self.managed_model_section = OnboardingSectionPanel(self)
        model_buttons = self._button_row(
            self.managed_model_browse_button,
            self.managed_model_default_button,
        )
        self.model_path_block = OnboardingFieldBlock(
            label=app_text("Existing models folder"),
            helper_text=app_text(
                "Choose the folder where your models are stored. Substitute will scan it without changing its contents."
            ),
            field=self.managed_model_root_edit,
            trailing_widget=model_buttons,
            parent=self,
        )
        self.managed_model_section.content_layout.addWidget(self.model_path_block)
        self.model_scan_status = LocalizedCaptionLabel("", self.managed_model_section)
        self.model_scan_status.setObjectName("OnboardingModelScanStatus")
        self.model_scan_status.setWordWrap(True)
        self.model_scan_status.hide()
        self.managed_model_section.content_layout.addWidget(self.model_scan_status)
        self.managed_model_section.hide()
        self.body_layout.addWidget(self.managed_model_section)

        self.output_section = OnboardingSectionPanel(self)
        output_buttons = self._button_row(
            self.output_browse_button,
            self.output_default_button,
        )
        self.output_section.content_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("Output folder"),
                helper_text=app_text(
                    "Substitute saves finished images here. The default keeps them "
                    "with your Substitute files."
                ),
                field=self.output_root_edit,
                trailing_widget=output_buttons,
                parent=self,
            )
        )
        self.body_layout.addWidget(self.output_section)

    def set_managed_model_visible(self, visible: bool) -> None:
        """Show model-folder controls for a local ComfyUI setup."""

        self.managed_model_section.setVisible(visible)
        self.model_path_block.setVisible(visible)

    def set_model_picker_visible(
        self,
        visible: bool,
        *,
        allow_default: bool,
    ) -> None:
        """Show the inline model-folder picker for the selected setup route."""

        self.managed_model_section.setVisible(visible)
        self.model_path_block.setVisible(visible)
        self.managed_model_default_button.setVisible(visible and allow_default)
        apply_application_text(
            self.hero_panel.description_label,
            app_text(
                "These defaults work well for most people. Change them if you already keep models or finished images somewhere else."
                if visible
                else "Substitute saves finished images here. The default keeps them with your Substitute files."
            ),
        )
        if not visible:
            self.model_scan_status.hide()

    def set_scan_status(self, message: ApplicationText) -> None:
        """Show scan state without changing the selected path."""

        self.model_scan_status.setText(message)
        self.model_scan_status.show()

    def reset_scan_status(self) -> None:
        """Hide stale scan feedback when entering the folder page."""

        self.model_scan_status.clear()
        self.model_scan_status.hide()

    def _button_row(self, *buttons: QWidget) -> QWidget:
        """Return a compact row for browse and default actions."""

        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for button in buttons:
            layout.addWidget(button)
        return container


class IntegrationsPage(OnboardingPageFrame):
    """Collect first-run helper integration preferences."""

    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the friendly integrations setup page."""

        super().__init__(
            title=app_text("Choose helpful extras"),
            description=app_text(
                "Optional services can help with prompts and models. You can change them later in Settings."
            ),
            icon=FIF.ROBOT,
            parent=parent,
        )
        self.setObjectName("OnboardingIntegrationsPage")
        self.content_column.setMinimumWidth(900)
        self._localization = LocalizationBindings(self)
        danbooru_tag_help_row, self.danbooru_tag_help_checkbox = self._preference_row(
            "OnboardingDanbooruTagHelpSwitch",
            app_text("Help with prompt tags"),
            app_text("Use Danbooru tag tools while writing prompts."),
        )
        self.danbooru_image_policy_combo = self._danbooru_policy_combo()
        self.danbooru_details = QWidget(self)
        danbooru_details_layout = QGridLayout(self.danbooru_details)
        danbooru_details_layout.setContentsMargins(0, 4, 0, 0)
        danbooru_details_layout.setHorizontalSpacing(22)
        danbooru_details_layout.setVerticalSpacing(12)
        danbooru_details_layout.addWidget(danbooru_tag_help_row, 0, 0)
        danbooru_details_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("Preview image content"),
                helper_text=app_text(
                    "Choose which Danbooru wiki preview image ratings Substitute may show."
                ),
                field=self.danbooru_image_policy_combo,
                parent=self.danbooru_details,
            ),
            0,
            1,
        )
        danbooru_details_layout.setColumnStretch(0, 1)
        danbooru_details_layout.setColumnStretch(1, 1)
        civitai_model_help_row, self.civitai_model_help_checkbox = self._preference_row(
            "OnboardingCivitaiModelHelpSwitch",
            app_text("Help find model info"),
            app_text(
                "Use CivitAI to help identify local models and missing recipe models."
            ),
        )
        civitai_downloads_row, self.civitai_downloads_checkbox = self._preference_row(
            "OnboardingCivitaiDownloadsSwitch",
            app_text("Offer model downloads"),
            app_text(
                "When a recipe needs a missing model, Substitute can offer verified "
                "CivitAI downloads."
            ),
        )
        self.civitai_thumbnail_policy_combo = self._civitai_thumbnail_policy_combo()
        self.civitai_api_key_edit = LineEdit(self)
        self.civitai_api_key_edit.setObjectName("OnboardingCivitaiApiKeyEdit")
        self.civitai_api_key_edit.setEchoMode(LineEdit.EchoMode.Password)
        self.civitai_api_key_status = LocalizedCaptionLabel("", self)
        self.civitai_api_key_status.setObjectName("OnboardingCivitaiApiKeyStatus")
        self.civitai_details = QWidget(self)
        civitai_details_layout = QGridLayout(self.civitai_details)
        civitai_details_layout.setContentsMargins(0, 4, 0, 0)
        civitai_details_layout.setHorizontalSpacing(22)
        civitai_details_layout.setVerticalSpacing(14)
        civitai_details_layout.addWidget(civitai_model_help_row, 0, 0)
        civitai_details_layout.addWidget(civitai_downloads_row, 0, 1)
        civitai_details_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("Thumbnail content"),
                helper_text=app_text(
                    "Choose which CivitAI image levels may be used for model thumbnails."
                ),
                field=self.civitai_thumbnail_policy_combo,
                parent=self.civitai_details,
            ),
            1,
            0,
        )
        civitai_details_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("API key (optional)"),
                helper_text=app_text(
                    "Add a CivitAI API key now, or leave this blank and add one later in Settings."
                ),
                field=self.civitai_api_key_edit,
                parent=self.civitai_details,
            ),
            1,
            1,
        )
        civitai_details_layout.addWidget(self.civitai_api_key_status, 2, 1)
        civitai_details_layout.setColumnStretch(0, 1)
        civitai_details_layout.setColumnStretch(1, 1)

        choices_layout = QVBoxLayout()
        choices_layout.setContentsMargins(0, 0, 0, 0)
        choices_layout.setSpacing(14)

        danbooru_section = OnboardingSectionPanel(self)
        danbooru_section.content_layout.addWidget(
            self._section_title("Danbooru", danbooru_section)
        )
        danbooru_section.content_layout.addWidget(self.danbooru_details)

        civitai_section = OnboardingSectionPanel(self)
        civitai_section.content_layout.addWidget(
            self._section_title("CivitAI", civitai_section)
        )
        civitai_section.content_layout.addWidget(self.civitai_details)

        choices_layout.addWidget(danbooru_section)
        choices_layout.addWidget(civitai_section)
        self.body_layout.addLayout(choices_layout)

    def set_api_key_configured(self, configured: bool) -> None:
        """Render whether a CivitAI API key already exists without showing it."""

        self.civitai_api_key_status.setText(
            app_text("API key already saved") if configured else ""
        )

    def danbooru_image_policy_value(self) -> str:
        """Return the selected Danbooru image rating policy value."""

        value = self.danbooru_image_policy_combo.currentData()
        if isinstance(value, str):
            return value
        return _DANBOORU_SAFE_ONLY

    def set_danbooru_image_policy(self, value: str) -> None:
        """Select the Danbooru image rating policy value when present."""

        self._set_combo_value(
            self.danbooru_image_policy_combo,
            value,
            fallback=_DANBOORU_SAFE_ONLY,
        )

    def civitai_thumbnail_policy_value(self) -> str:
        """Return the selected CivitAI thumbnail safety policy value."""

        value = self.civitai_thumbnail_policy_combo.currentData()
        if isinstance(value, str):
            return value
        return _CIVITAI_SFW_ONLY

    def set_civitai_thumbnail_policy(self, value: str) -> None:
        """Select the CivitAI thumbnail safety policy value when present."""

        self._set_combo_value(
            self.civitai_thumbnail_policy_combo,
            value,
            fallback=_CIVITAI_SFW_ONLY,
        )

    def _preference_row(
        self,
        object_name: str,
        label: ApplicationText,
        helper_text: ApplicationText,
    ) -> tuple[QFrame, CheckBox]:
        """Return a checkbox row with concise helper copy."""

        row = QFrame(self)
        row.setObjectName("OnboardingPreferenceRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        checkbox = LocalizedCheckBox(label, row)
        checkbox.setObjectName(object_name)
        checkbox.setChecked(True)
        helper_label = LocalizedCaptionLabel(helper_text, row)
        helper_label.setObjectName("OnboardingFieldHelper")
        helper_label.setWordWrap(True)
        layout.addWidget(checkbox)
        layout.addWidget(helper_label)
        return row, checkbox

    def _danbooru_policy_combo(self) -> ComboBox:
        """Create the Danbooru rating policy selector."""

        combo = ComboBox(self)
        combo.setObjectName("OnboardingDanbooruImagePolicyCombo")
        combo.setMinimumWidth(260)
        self._localization.bind_combo_items(
            combo,
            lambda: (
                LocalizedComboItem(
                    _DANBOORU_SAFE_ONLY,
                    render_application_text(app_text("Safe only")),
                ),
                LocalizedComboItem(
                    _DANBOORU_SAFE_AND_QUESTIONABLE,
                    render_application_text(app_text("Safe and questionable")),
                ),
                LocalizedComboItem(
                    _DANBOORU_ALL_RATINGS,
                    render_application_text(app_text("All ratings")),
                ),
            ),
        )
        return combo

    def _civitai_thumbnail_policy_combo(self) -> ComboBox:
        """Create the CivitAI thumbnail content policy selector."""

        combo = ComboBox(self)
        combo.setObjectName("OnboardingCivitaiThumbnailPolicyCombo")
        combo.setMinimumWidth(260)
        self._localization.bind_combo_items(
            combo,
            lambda: (
                LocalizedComboItem(
                    _CIVITAI_SFW_ONLY,
                    render_application_text(app_text("SFW only")),
                ),
                LocalizedComboItem(
                    _CIVITAI_ALLOW_SOFT,
                    render_application_text(app_text("Allow soft")),
                ),
                LocalizedComboItem(
                    _CIVITAI_ALLOW_ALL,
                    render_application_text(app_text("Allow all")),
                ),
            ),
        )
        return combo

    def _set_combo_value(
        self,
        combo: ComboBox,
        value: str,
        *,
        fallback: str,
    ) -> None:
        """Select a combo item by user data, falling back to the default value."""

        selected = self._combo_index_for_value(combo, value)
        if selected < 0:
            selected = self._combo_index_for_value(combo, fallback)
        if selected >= 0:
            combo.setCurrentIndex(selected)

    def _combo_index_for_value(self, combo: ComboBox, value: str) -> int:
        """Return the combo index for one user data value."""

        for index in range(combo.count()):
            if combo.itemData(index) == value:
                return index
        return -1

    def _section_title(self, text: str, parent: QWidget) -> BodyLabel:
        """Return a compact title for one integration subsection."""

        label = LocalizedBodyLabel(text, parent)
        label.setObjectName("OnboardingInfoTitle")
        return label
