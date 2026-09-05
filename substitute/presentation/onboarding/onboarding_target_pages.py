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

"""Provide installation-root and ComfyUI target selection pages."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedPushButton,
)

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    LineEdit,
)

from substitute.presentation.onboarding.onboarding_models import OnboardingTargetMode
from substitute.presentation.platform_path_guidance import (
    existing_comfy_example,
    managed_comfy_example,
    substitute_install_example,
)
from substitute.presentation.onboarding.onboarding_connection_settings_dialog import (
    ConnectionSettingsDialog,
    build_endpoint_fields,
    build_endpoint_row,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingFieldBlock,
    OnboardingPageFrame,
    OnboardingSectionPanel,
    TargetModeCard,
    _TARGET_MODE_PRESENTATION,
)


class InstallRootPage(OnboardingPageFrame):
    """Collect the installation root used for the visible Substitute setup."""

    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the first-run folder page with one primary action area."""

        super().__init__(
            title=app_text("Choose where Substitute should keep its setup"),
            description=app_text(
                "Pick the main folder for Substitute's files. If you let Substitute install ComfyUI for you, it will place that there too by default."
            ),
            icon=FIF.FOLDER,
            parent=parent,
        )
        self.setObjectName("OnboardingWelcomePage")
        self.install_root_edit = LineEdit(self)
        self.install_root_edit.setObjectName("OnboardingInstallRootEdit")
        self.install_root_edit.setPlaceholderText(substitute_install_example())
        browse_button = LocalizedPushButton(app_text("Browse..."), self)
        browse_button.setObjectName("OnboardingInstallRootBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("Folder"),
                helper_text=app_text(
                    "Substitute will keep its own settings and setup files here. You "
                    "can still switch between managed, existing, or remote ComfyUI "
                    "later."
                ),
                field=self.install_root_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        support_label = LocalizedCaptionLabel(
            app_text(
                "Substitute may create settings, a local runtime, cubes, and a `comfyui` folder here if you choose the managed setup."
            ),
            section,
        )
        support_label.setObjectName("OnboardingSectionSupport")
        support_label.setWordWrap(True)
        section.content_layout.addWidget(support_label)
        self.body_layout.addWidget(section)


class TargetModePage(OnboardingPageFrame):
    """Collect the user-facing ComfyUI setup choice with card-only selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the target-mode page using cards as the only visible selector."""

        super().__init__(
            title=app_text("Choose how Substitute should reach ComfyUI"),
            description=app_text("Choose the way you use ComfyUI."),
            icon=FIF.LINK,
            parent=parent,
        )
        self._selected_mode = OnboardingTargetMode.MANAGED_LOCAL
        self.setObjectName("OnboardingTargetModePage")

        decision_panel = OnboardingSectionPanel(self)
        self.card_layout = QGridLayout()
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setHorizontalSpacing(14)
        self.card_layout.setVerticalSpacing(14)
        self.mode_cards: dict[OnboardingTargetMode, TargetModeCard] = {}
        modes = (
            OnboardingTargetMode.MANAGED_LOCAL,
            OnboardingTargetMode.ATTACHED_LOCAL,
            OnboardingTargetMode.REMOTE,
        )
        for column, mode in enumerate(modes):
            card = TargetModeCard(
                mode=mode,
                presentation=_TARGET_MODE_PRESENTATION[mode],
                parent=self,
            )
            card.clicked.connect(self._handle_card_clicked)
            self.card_layout.addWidget(card, 0, column)
            self.mode_cards[mode] = card
        decision_panel.content_layout.addLayout(self.card_layout)

        self.body_layout.addWidget(decision_panel)

        self.set_selected_mode(self._selected_mode)

    def selected_mode(self) -> OnboardingTargetMode:
        """Return the active target-mode selection."""

        return self._selected_mode

    def set_selected_mode(self, mode: OnboardingTargetMode) -> None:
        """Apply the selected mode to the cards and summary panel."""

        self._selected_mode = mode
        for card_mode, card in self.mode_cards.items():
            card.set_selected(card_mode is mode)

    def _handle_card_clicked(self, route_key: str) -> None:
        """Update the selected mode from a clicked card."""

        self.set_selected_mode(OnboardingTargetMode(route_key))


class ManagedLocalPage(OnboardingPageFrame):
    """Collect the managed-local endpoint and workspace choices."""

    browse_requested = Signal()
    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the managed-local page with the form as the primary content."""

        super().__init__(
            title=app_text("Let Substitute set up ComfyUI for you"),
            description=app_text(
                "Choose where ComfyUI should live. Substitute handles the rest."
            ),
            icon=FIF.HOME,
            parent=parent,
        )
        self.setObjectName("OnboardingManagedLocalPage")
        self.connection_settings_dialog = ConnectionSettingsDialog(
            managed_runtime=True,
            parent=self,
        )
        self.host_edit = self.connection_settings_dialog.host_edit
        self.host_edit.setObjectName("OnboardingManagedHostEdit")
        self.port_spinbox = self.connection_settings_dialog.port_spinbox
        self.port_spinbox.setObjectName("OnboardingManagedPortSpinBox")
        runtime_summary_panel = self.connection_settings_dialog.runtime_summary_panel
        if runtime_summary_panel is None:
            raise RuntimeError("Managed connection settings require runtime controls")
        self.runtime_summary_panel = runtime_summary_panel
        self.workspace_edit = LineEdit(self)
        self.workspace_edit.setObjectName("OnboardingManagedWorkspaceEdit")
        self.workspace_edit.setPlaceholderText(managed_comfy_example())
        browse_button = LocalizedPushButton(app_text("Browse..."), self)
        browse_button.setObjectName("OnboardingManagedWorkspaceBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("ComfyUI folder"),
                helper_text=app_text("You can keep the suggested location."),
                field=self.workspace_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        self.advanced_button = LocalizedPushButton(app_text("Advanced settings"), self)
        self.advanced_button.setObjectName("OnboardingAdvancedButton")
        self.advanced_button.clicked.connect(self.connection_settings_dialog.present)
        section.content_layout.addWidget(
            self.advanced_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        self.body_layout.addWidget(section)


class AttachedLocalPage(OnboardingPageFrame):
    """Collect the launch details for an existing local ComfyUI setup."""

    browse_requested = Signal()
    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the attached-local configuration page."""

        super().__init__(
            title=app_text("Use the ComfyUI setup you already have"),
            description=app_text("Choose the ComfyUI folder you already use."),
            icon=FIF.LINK,
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedLocalPage")
        self.connection_settings_dialog = ConnectionSettingsDialog(
            managed_runtime=False,
            parent=self,
        )
        self.host_edit = self.connection_settings_dialog.host_edit
        self.host_edit.setObjectName("OnboardingAttachedHostEdit")
        self.port_spinbox = self.connection_settings_dialog.port_spinbox
        self.port_spinbox.setObjectName("OnboardingAttachedPortSpinBox")
        self.workspace_edit = LineEdit(self)
        self.workspace_edit.setObjectName("OnboardingAttachedWorkspaceEdit")
        self.workspace_edit.setPlaceholderText(existing_comfy_example())
        browse_button = LocalizedPushButton(app_text("Browse..."), self)
        browse_button.setObjectName("OnboardingAttachedWorkspaceBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("ComfyUI folder"),
                helper_text=app_text(
                    "Choose the folder that contains your existing ComfyUI main.py "
                    "file. Substitute will launch this copy when it starts."
                ),
                field=self.workspace_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        self.advanced_button = LocalizedPushButton(
            app_text("Connection settings"), self
        )
        self.advanced_button.clicked.connect(self.connection_settings_dialog.present)
        section.content_layout.addWidget(self.advanced_button)
        self.body_layout.addWidget(section)


class RemotePage(OnboardingPageFrame):
    """Collect the connection details for a remote ComfyUI server."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the remote setup page with form-first composition."""

        super().__init__(
            title=app_text("Connect to ComfyUI on another machine"),
            description=app_text("Enter the address of the ComfyUI server."),
            icon=FIF.IOT,
            parent=parent,
        )
        self.setObjectName("OnboardingRemotePage")
        fields = build_endpoint_fields(self)
        self.host_edit = fields.host_edit
        self.host_edit.setObjectName("OnboardingRemoteHostEdit")
        self.port_spinbox = fields.port_spinbox
        self.port_spinbox.setObjectName("OnboardingRemotePortSpinBox")

        section = OnboardingSectionPanel(self)
        section.content_layout.addLayout(build_endpoint_row(fields=fields, parent=self))
        self.body_layout.addWidget(section)
