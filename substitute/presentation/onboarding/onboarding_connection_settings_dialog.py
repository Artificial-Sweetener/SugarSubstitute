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

"""Present bounded expert connection and managed-runtime settings."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    set_localized_text,
    set_localized_window_title,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedCheckBox,
    LocalizedPushButton,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingFieldBlock,
    OnboardingSectionPanel,
)
from substitute.presentation.widgets.spin_box import SpinBox


_RUNTIME_INITIALISMS = {
    "amd": "AMD",
    "cpu": "CPU",
    "cuda": "CUDA",
    "linux": "Linux",
    "macos": "macOS",
    "nvidia": "NVIDIA",
    "windows": "Windows",
}


def _present_runtime_token(value: str | None, fallback: str) -> str:
    """Turn an internal runtime identifier into concise visible text."""

    if not value:
        return fallback
    words = value.replace("-", "_").split("_")
    return " ".join(
        _RUNTIME_INITIALISMS.get(
            word.casefold(),
            word.upper()
            if word.casefold().startswith("cu") and word[2:].isdigit()
            else word.capitalize(),
        )
        for word in words
    )


@dataclass(frozen=True)
class TargetEndpointFields:
    """Bundle endpoint widgets shared by target configuration surfaces."""

    host_edit: LineEdit
    port_spinbox: SpinBox


def build_endpoint_fields(parent: QWidget) -> TargetEndpointFields:
    """Build host and port controls owned by one connection surface."""

    host_edit = LineEdit(parent)
    host_edit.setPlaceholderText("127.0.0.1")
    port_spinbox = SpinBox(parent)
    port_spinbox.setRange(1, 65535)
    port_spinbox.setValue(8188)
    return TargetEndpointFields(host_edit=host_edit, port_spinbox=port_spinbox)


def build_endpoint_row(*, fields: TargetEndpointFields, parent: QWidget) -> QHBoxLayout:
    """Build the shared host-and-port field row."""

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


class ManagedRuntimeSummaryPanel(OnboardingSectionPanel):
    """Separate detected setup facts from explicit expert overrides."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build a concise detected summary followed by explained choices."""

        super().__init__(parent)
        self.setObjectName("ManagedRuntimeSummaryPanel")
        self.content_layout.setSpacing(7)

        detected_title = LocalizedBodyLabel(app_text("Detected setup"), self)
        detected_title.setObjectName("OnboardingInfoTitle")
        self.content_layout.addWidget(detected_title)

        self.detected_summary_label = LocalizedCaptionLabel("", self)
        self.detected_summary_label.setObjectName("OnboardingRuntimeDetectedSummary")
        self.detected_summary_label.setWordWrap(True)
        self.content_layout.addWidget(self.detected_summary_label)

        self.platform_label = LocalizedCaptionLabel("", self)
        self.accelerator_label = LocalizedCaptionLabel("", self)
        self.target_label = LocalizedCaptionLabel("", self)
        self.python_label = LocalizedCaptionLabel("", self)
        self.channel_label = LocalizedCaptionLabel("", self)
        self.backend_label = LocalizedCaptionLabel("", self)
        self.torch_channel_label = LocalizedCaptionLabel("", self)
        self.stability_label = LocalizedCaptionLabel("", self)
        for summary_label in (
            self.platform_label,
            self.accelerator_label,
            self.target_label,
            self.python_label,
            self.channel_label,
            self.backend_label,
            self.torch_channel_label,
            self.stability_label,
        ):
            summary_label.setObjectName("OnboardingRuntimeSummaryValue")
            summary_label.hide()

        self.torch_reason_label = LocalizedCaptionLabel("", self)
        self.torch_reason_label.setObjectName("OnboardingRuntimeSummaryReason")
        self.torch_reason_label.setWordWrap(True)
        self.torch_reason_label.hide()

        choices_title = LocalizedBodyLabel(app_text("Performance and updates"), self)
        choices_title.setObjectName("OnboardingInfoTitle")
        self.content_layout.addSpacing(5)
        self.content_layout.addWidget(choices_title)
        choices_description = LocalizedCaptionLabel(
            app_text("Change these only when you need a different runtime strategy."),
            self,
        )
        choices_description.setObjectName("OnboardingInfoDescription")
        choices_description.setWordWrap(True)
        self.content_layout.addWidget(choices_description)

        self.force_cpu_checkbox = LocalizedCheckBox(app_text("Use CPU instead"), self)
        self.edge_channel_checkbox = LocalizedCheckBox(
            app_text("Try preview ComfyUI builds"), self
        )
        self.edge_torch_checkbox = LocalizedCheckBox(
            app_text("Try preview Torch builds"), self
        )
        for checkbox in (
            self.force_cpu_checkbox,
            self.edge_channel_checkbox,
            self.edge_torch_checkbox,
        ):
            self.content_layout.addWidget(checkbox)

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
        """Render the detected hardware and selected runtime facts."""

        set_localized_text(
            self.detected_summary_label,
            "%1 · %2 · Python %3 · %4",
            _present_runtime_token(detected_platform, "Detecting"),
            _present_runtime_token(detected_accelerator, "Detecting"),
            selected_python_version or "Pending",
            _present_runtime_token(selected_backend_policy, "Pending"),
        )
        values = (
            (self.platform_label, "Platform: %1", detected_platform, "Detecting"),
            (
                self.accelerator_label,
                "Accelerator: %1",
                detected_accelerator,
                "Detecting",
            ),
            (
                self.target_label,
                "Install target: %1",
                selected_install_target,
                "Pending selection",
            ),
            (
                self.python_label,
                "Python: %1",
                selected_python_version,
                "Pending selection",
            ),
            (
                self.channel_label,
                "ComfyUI channel: %1",
                selected_comfy_channel,
                "Pending selection",
            ),
            (
                self.backend_label,
                "Backend: %1",
                selected_backend_policy,
                "Pending selection",
            ),
            (
                self.torch_channel_label,
                "Torch channel: %1",
                selected_torch_channel,
                "Pending selection",
            ),
            (
                self.stability_label,
                "Path stability: %1",
                selected_stability,
                "Pending selection",
            ),
        )
        for label, template, value, fallback in values:
            presented_value = (
                selected_python_version or fallback
                if label is self.python_label
                else _present_runtime_token(value, fallback)
            )
            set_localized_text(
                label,
                template,
                presented_value,
            )
        set_localized_text(
            self.torch_reason_label,
            "Reason: %1",
            selected_torch_reason or "Pending selection",
        )


class ConnectionSettingsDialog(QDialog):
    """Keep expert connection settings bounded outside the centered main page."""

    def __init__(
        self,
        *,
        managed_runtime: bool,
        parent: QWidget,
    ) -> None:
        """Build one focused connection dialog, optionally with runtime choices."""

        super().__init__(parent)
        self.setObjectName("OnboardingConnectionSettingsDialog")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        set_localized_window_title(
            self,
            "Advanced ComfyUI settings" if managed_runtime else "Connection settings",
        )
        self.resize(820, 560 if managed_runtime else 330)
        self.setMinimumSize(720, 500 if managed_runtime else 300)
        self.setMaximumSize(920, 660 if managed_runtime else 390)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        title = LocalizedBodyLabel(
            app_text(
                "Advanced ComfyUI settings"
                if managed_runtime
                else "Connection settings"
            ),
            self,
        )
        title.setObjectName("OnboardingDialogTitle")
        layout.addWidget(title)
        description = LocalizedCaptionLabel(
            app_text(
                "Review the detected setup or change expert connection and runtime choices."
                if managed_runtime
                else "Change the address Substitute uses for this ComfyUI setup."
            ),
            self,
        )
        description.setObjectName("OnboardingInfoDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        endpoint_section = OnboardingSectionPanel(self)
        endpoint_title = LocalizedBodyLabel(app_text("Connection"), self)
        endpoint_title.setObjectName("OnboardingInfoTitle")
        endpoint_section.content_layout.addWidget(endpoint_title)
        fields = build_endpoint_fields(self)
        self.host_edit = fields.host_edit
        self.port_spinbox = fields.port_spinbox
        endpoint_section.content_layout.addLayout(
            build_endpoint_row(fields=fields, parent=endpoint_section)
        )
        layout.addWidget(endpoint_section)

        self.runtime_summary_panel: ManagedRuntimeSummaryPanel | None = None
        if managed_runtime:
            self.runtime_summary_panel = ManagedRuntimeSummaryPanel(self)
            layout.addWidget(self.runtime_summary_panel)
        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        done_button = LocalizedPushButton(app_text("Done"), self)
        done_button.setObjectName("OnboardingConnectionSettingsDoneButton")
        done_button.clicked.connect(self.accept)
        actions.addWidget(done_button)
        layout.addLayout(actions)

    def present(self) -> None:
        """Show the retained dialog centered over the installer window."""

        parent = self.parentWidget()
        if parent is None:
            self.show()
            return
        host_window = parent.window()
        root = host_window.findChild(QWidget, "OnboardingRoot")
        if root is not None:
            self.setFont(root.font())
            self.setStyleSheet(root.styleSheet())
        frame = self.frameGeometry()
        frame.moveCenter(host_window.frameGeometry().center())
        self.move(frame.topLeft())
        self.show()
        self.raise_()
        self.activateWindow()


__all__ = [
    "ConnectionSettingsDialog",
    "ManagedRuntimeSummaryPanel",
    "TargetEndpointFields",
    "build_endpoint_fields",
    "build_endpoint_row",
]
