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
from sugarsubstitute_shared.presentation.localization import (
    set_localized_text,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedCheckBox,
    LocalizedPushButton,
)

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
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
from substitute.presentation.widgets.spin_box import SpinBox

from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingFieldBlock,
    OnboardingInfoPanel,
    OnboardingPageFrame,
    OnboardingSectionPanel,
    TargetModeCard,
    TargetModeSummaryPanel,
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
            eyebrow=app_text("Start here"),
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
            description=app_text(
                "Pick the setup that matches your current situation. You can change this later if your workflow changes."
            ),
            icon=FIF.LINK,
            eyebrow=app_text("Choose your setup"),
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

        self.summary_panel = TargetModeSummaryPanel(self)
        decision_panel.content_layout.addWidget(self.summary_panel)
        self.body_layout.addWidget(decision_panel)

        self.set_selected_mode(self._selected_mode)

    def selected_mode(self) -> OnboardingTargetMode:
        """Return the active target-mode selection."""

        return self._selected_mode

    def set_selected_mode(self, mode: OnboardingTargetMode) -> None:
        """Apply the selected mode to the cards and summary panel."""

        self._selected_mode = mode
        self.summary_panel.set_presentation(_TARGET_MODE_PRESENTATION[mode])
        for card_mode, card in self.mode_cards.items():
            card.set_selected(card_mode is mode)

    def _handle_card_clicked(self, route_key: str) -> None:
        """Update the selected mode from a clicked card."""

        self.set_selected_mode(OnboardingTargetMode(route_key))


@dataclass(frozen=True)
class TargetEndpointFields:
    """Bundle endpoint widgets reused across the target-specific forms."""

    host_edit: LineEdit
    port_spinbox: SpinBox


def _build_endpoint_fields(parent: QWidget) -> TargetEndpointFields:
    """Build the reusable host and port widgets."""

    host_edit = LineEdit(parent)
    host_edit.setPlaceholderText("127.0.0.1")
    port_spinbox = SpinBox(parent)
    port_spinbox.setRange(1, 65535)
    port_spinbox.setValue(8188)
    return TargetEndpointFields(host_edit=host_edit, port_spinbox=port_spinbox)


def _build_endpoint_row(
    *, fields: TargetEndpointFields, parent: QWidget
) -> QHBoxLayout:
    """Build the shared host-and-port row for target configuration pages."""

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(14)
    row.addWidget(
        OnboardingFieldBlock(
            label=app_text("Host"),
            helper_text=app_text(
                "This is the address Substitute will use to reach ComfyUI."
            ),
            field=fields.host_edit,
            parent=parent,
        ),
        2,
    )
    row.addWidget(
        OnboardingFieldBlock(
            label=app_text("Port"),
            helper_text=app_text(
                "This is the port number used by that ComfyUI address."
            ),
            field=fields.port_spinbox,
            parent=parent,
        ),
        1,
    )
    return row


class ManagedRuntimeSummaryPanel(QFrame):
    """Render the detected managed install strategy and advanced override toggles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the managed runtime summary surface and override controls."""

        super().__init__(parent)
        self.setObjectName("ManagedRuntimeSummaryPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        title_label = LocalizedBodyLabel(app_text("Setup summary"), self)
        title_label.setObjectName("OnboardingInfoTitle")
        layout.addWidget(title_label)

        self.platform_label = LocalizedCaptionLabel("", self)
        self.accelerator_label = LocalizedCaptionLabel("", self)
        self.target_label = LocalizedCaptionLabel("", self)
        self.python_label = LocalizedCaptionLabel("", self)
        self.channel_label = LocalizedCaptionLabel("", self)
        self.backend_label = LocalizedCaptionLabel("", self)
        self.torch_channel_label = LocalizedCaptionLabel("", self)
        self.stability_label = LocalizedCaptionLabel("", self)

        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(12)
        summary_grid.setVerticalSpacing(6)
        summary_fields = (
            (self.platform_label, 0, 0),
            (self.accelerator_label, 0, 1),
            (self.target_label, 1, 0),
            (self.python_label, 1, 1),
            (self.channel_label, 2, 0),
            (self.backend_label, 2, 1),
            (self.torch_channel_label, 3, 0),
            (self.stability_label, 3, 1),
        )
        for summary_label, row, column in summary_fields:
            summary_label.setObjectName("OnboardingRuntimeSummaryValue")
            summary_label.setWordWrap(True)
            summary_grid.addWidget(summary_label, row, column)
        summary_grid.setColumnStretch(0, 1)
        summary_grid.setColumnStretch(1, 1)
        layout.addLayout(summary_grid)

        self.torch_reason_label = LocalizedCaptionLabel("", self)
        self.torch_reason_label.setObjectName("OnboardingRuntimeSummaryReason")
        self.torch_reason_label.setWordWrap(True)
        layout.addWidget(self.torch_reason_label)

        advanced_title = LocalizedCaptionLabel(app_text("Advanced options"), self)
        advanced_title.setObjectName("OnboardingFieldLabel")
        layout.addWidget(advanced_title)

        self.force_cpu_checkbox = LocalizedCheckBox(app_text("Force CPU mode"), self)
        self.edge_torch_checkbox = LocalizedCheckBox(
            app_text("Prefer cutting-edge torch backend"), self
        )
        self.edge_channel_checkbox = LocalizedCheckBox(
            app_text("Use edge ComfyUI channel"), self
        )

        advanced_grid = QGridLayout()
        advanced_grid.setContentsMargins(0, 0, 0, 0)
        advanced_grid.setHorizontalSpacing(12)
        advanced_grid.setVerticalSpacing(6)
        advanced_grid.addWidget(self.force_cpu_checkbox, 0, 0)
        advanced_grid.addWidget(self.edge_channel_checkbox, 0, 1)
        advanced_grid.addWidget(self.edge_torch_checkbox, 1, 0, 1, 2)
        advanced_grid.setColumnStretch(0, 1)
        advanced_grid.setColumnStretch(1, 1)
        layout.addLayout(advanced_grid)

    def update_summary(
        self,
        *,
        detected_platform: str | None,
        detected_accelerator: str | None,
        selected_install_target: str | None,
        selected_python_version: str | None,
        selected_comfy_channel: str | None,
        selected_backend_policy: str | None,
        selected_torch_channel: str | None,
        selected_torch_reason: str | None,
        selected_stability: str | None,
    ) -> None:
        """Render the current detected hardware and install selection summary."""

        set_localized_text(
            self.platform_label,
            "Platform: %1",
            detected_platform or "Detecting",
        )
        set_localized_text(
            self.accelerator_label,
            "Accelerator: %1",
            detected_accelerator or "Detecting",
        )
        set_localized_text(
            self.target_label,
            "Install target: %1",
            selected_install_target or "Pending selection",
        )
        set_localized_text(
            self.python_label,
            "Python: %1",
            selected_python_version or "Pending selection",
        )
        set_localized_text(
            self.channel_label,
            "ComfyUI channel: %1",
            selected_comfy_channel or "Pending selection",
        )
        set_localized_text(
            self.backend_label,
            "Backend: %1",
            selected_backend_policy or "Pending selection",
        )
        set_localized_text(
            self.torch_channel_label,
            "Torch channel: %1",
            selected_torch_channel or "Pending selection",
        )
        set_localized_text(
            self.torch_reason_label,
            "Reason: %1",
            selected_torch_reason or "Pending selection",
        )
        set_localized_text(
            self.stability_label,
            "Path stability: %1",
            selected_stability or "Pending selection",
        )


class ManagedLocalPage(OnboardingPageFrame):
    """Collect the managed-local endpoint and workspace choices."""

    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the managed-local page with the form as the primary content."""

        super().__init__(
            title=app_text("Let Substitute set up ComfyUI for you"),
            description=app_text(
                "This is the easiest option for most people. Substitute installs ComfyUI, prepares it, and keeps the setup ready to use."
            ),
            icon=FIF.HOME,
            eyebrow=app_text("Recommended for most people"),
            parent=parent,
        )
        self.setObjectName("OnboardingManagedLocalPage")
        fields = _build_endpoint_fields(self)
        self.host_edit = fields.host_edit
        self.host_edit.setObjectName("OnboardingManagedHostEdit")
        self.port_spinbox = fields.port_spinbox
        self.port_spinbox.setObjectName("OnboardingManagedPortSpinBox")
        self.workspace_edit = LineEdit(self)
        self.workspace_edit.setObjectName("OnboardingManagedWorkspaceEdit")
        self.workspace_edit.setPlaceholderText(managed_comfy_example())
        browse_button = LocalizedPushButton(app_text("Browse..."), self)
        browse_button.setObjectName("OnboardingManagedWorkspaceBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addLayout(
            _build_endpoint_row(fields=fields, parent=self)
        )
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label=app_text("ComfyUI folder"),
                helper_text=app_text(
                    "This is where Substitute will place ComfyUI. Most people can "
                    "keep the default location."
                ),
                field=self.workspace_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        self.next_steps_panel = OnboardingInfoPanel(
            title=app_text("What happens next"),
            description=app_text(
                "Substitute saves this setup, installs ComfyUI in the folder above, picks the right backend for this machine, and prepares what it needs to run."
            ),
            detail_lines=(
                app_text("Most people can leave the local address unchanged."),
                app_text(
                    "First-time setup can take a while because ComfyUI and Python "
                    "packages may need to be installed."
                ),
            ),
            parent=self,
        )
        self.runtime_summary_panel = ManagedRuntimeSummaryPanel(self)
        setup_details_layout = QHBoxLayout()
        setup_details_layout.setContentsMargins(0, 0, 0, 0)
        setup_details_layout.setSpacing(14)
        setup_details_layout.addWidget(self.next_steps_panel, 5)
        setup_details_layout.addWidget(self.runtime_summary_panel, 7)
        section.content_layout.addLayout(setup_details_layout)
        self.body_layout.addWidget(section)


class AttachedLocalPage(OnboardingPageFrame):
    """Collect the launch details for an existing local ComfyUI setup."""

    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the attached-local configuration page."""

        super().__init__(
            title=app_text("Use the ComfyUI setup you already have"),
            description=app_text(
                "Substitute will use this local ComfyUI folder, prepare what it needs, and start it for you."
            ),
            icon=FIF.LINK,
            eyebrow=app_text("Keep your existing setup"),
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedLocalPage")
        fields = _build_endpoint_fields(self)
        self.host_edit = fields.host_edit
        self.host_edit.setObjectName("OnboardingAttachedHostEdit")
        self.port_spinbox = fields.port_spinbox
        self.port_spinbox.setObjectName("OnboardingAttachedPortSpinBox")
        self.workspace_edit = LineEdit(self)
        self.workspace_edit.setObjectName("OnboardingAttachedWorkspaceEdit")
        self.workspace_edit.setPlaceholderText(existing_comfy_example())
        browse_button = LocalizedPushButton(app_text("Browse..."), self)
        browse_button.setObjectName("OnboardingAttachedWorkspaceBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addLayout(
            _build_endpoint_row(fields=fields, parent=self)
        )
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
        section.content_layout.addWidget(
            OnboardingInfoPanel(
                title=app_text("What happens next"),
                description=app_text(
                    "Substitute saves this folder as a local launch target and prepares the Python environment it needs."
                ),
                detail_lines=(
                    app_text("ComfyUI does not need to be running during setup."),
                    app_text(
                        "Substitute will start it and then wait for the local address "
                        "to respond."
                    ),
                ),
                parent=self,
            )
        )
        self.body_layout.addWidget(section)


class RemotePage(OnboardingPageFrame):
    """Collect the connection details for a remote ComfyUI server."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the remote setup page with form-first composition."""

        super().__init__(
            title=app_text("Connect to ComfyUI on another machine"),
            description=app_text(
                "Use this when ComfyUI lives on another PC or server and you want Substitute to reach it from here."
            ),
            icon=FIF.IOT,
            eyebrow=app_text("Remote connection"),
            parent=parent,
        )
        self.setObjectName("OnboardingRemotePage")
        fields = _build_endpoint_fields(self)
        self.host_edit = fields.host_edit
        self.host_edit.setObjectName("OnboardingRemoteHostEdit")
        self.port_spinbox = fields.port_spinbox
        self.port_spinbox.setObjectName("OnboardingRemotePortSpinBox")

        section = OnboardingSectionPanel(self)
        section.content_layout.addLayout(
            _build_endpoint_row(fields=fields, parent=self)
        )
        section.content_layout.addWidget(
            OnboardingInfoPanel(
                title=app_text("What happens next"),
                description=app_text(
                    "Substitute saves the remote address and keeps the local pieces it still needs for the canvas on this computer."
                ),
                detail_lines=(
                    app_text(
                        "Host and port are the address of the remote ComfyUI server."
                    ),
                    app_text(
                        "You keep that remote server running and reachable from this "
                        "PC."
                    ),
                ),
                parent=self,
            )
        )
        self.body_layout.addWidget(section)
