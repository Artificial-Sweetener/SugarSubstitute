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

"""Collect installer folder choices through one focused presentation owner."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, LineEdit  # type: ignore[import-untyped]
from sugarsubstitute_shared.localization import ApplicationText, app_text
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPushButton,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingFieldBlock,
    OnboardingPageFrame,
    OnboardingSectionPanel,
)


class FolderSetupPage(OnboardingPageFrame):
    """Collect one shared models folder and one output folder."""

    managed_model_browse_requested = Signal()
    output_browse_requested = Signal()
    managed_model_default_requested = Signal()
    output_default_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the folder setup page."""

        super().__init__(
            title=app_text("Choose where models and outputs should live"),
            description=app_text(
                "Use the suggested models folder or choose one already used by another WebUI."
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
        self.model_path_block = OnboardingFieldBlock(
            label=app_text("Models folder"),
            helper_text=app_text(
                "Substitute and ComfyUI use this folder in place, without moving or reorganizing its models."
            ),
            field=self.managed_model_root_edit,
            trailing_widget=self._button_row(
                self.managed_model_browse_button,
                self.managed_model_default_button,
            ),
            parent=self,
        )
        self.managed_model_section.content_layout.addWidget(self.model_path_block)
        self.model_scan_status = LocalizedCaptionLabel("", self.managed_model_section)
        self.model_scan_status.setObjectName("OnboardingModelScanStatus")
        self.model_scan_status.setWordWrap(True)
        self.model_scan_status.hide()
        self.managed_model_section.content_layout.addWidget(self.model_scan_status)
        self.body_layout.addWidget(self.managed_model_section)

        self.output_section = OnboardingSectionPanel(self)
        self.output_section.content_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("Output folder"),
                helper_text=app_text(
                    "Substitute saves finished images here. The default keeps them "
                    "with your Substitute files."
                ),
                field=self.output_root_edit,
                trailing_widget=self._button_row(
                    self.output_browse_button,
                    self.output_default_button,
                ),
                parent=self,
            )
        )
        self.body_layout.addWidget(self.output_section)

    def set_managed_model_visible(self, visible: bool) -> None:
        """Show model-folder controls for a local ComfyUI setup."""

        self.managed_model_section.setVisible(visible)
        self.model_path_block.setVisible(visible)

    def configure_model_picker(self, *, allow_default: bool) -> None:
        """Configure the one models-folder picker for the selected setup route."""

        self.managed_model_section.show()
        self.model_path_block.show()
        self.managed_model_default_button.setVisible(allow_default)

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
