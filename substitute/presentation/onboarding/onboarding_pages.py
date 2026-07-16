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

"""Provide polished onboarding pages for setup, repair, and reconfigure flows."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    IconWidget,
    LineEdit,
    PushButton,
    RadioButton,
)

from substitute.presentation.onboarding.onboarding_models import OnboardingTargetMode
from substitute.presentation.platform_path_guidance import (
    existing_comfy_example,
    managed_comfy_example,
    substitute_install_example,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_view import TerminalOutputView
from substitute.presentation.widgets.spin_box import SpinBox

_DANBOORU_SAFE_ONLY = "safe_only"
_DANBOORU_SAFE_AND_QUESTIONABLE = "safe_and_questionable"
_DANBOORU_ALL_RATINGS = "all_ratings"
_CIVITAI_SFW_ONLY = "sfw_only"
_CIVITAI_ALLOW_SOFT = "allow_soft"
_CIVITAI_ALLOW_ALL = "allow_all"


@dataclass(frozen=True)
class TargetModePresentation:
    """Describe the concise product-facing copy for one target mode."""

    title: str
    summary: str
    best_if: str
    meaning: str
    substitute_handles: str
    you_handle: str
    technical_note: str
    icon: object


_TARGET_MODE_PRESENTATION: dict[OnboardingTargetMode, TargetModePresentation] = {
    OnboardingTargetMode.MANAGED_LOCAL: TargetModePresentation(
        title="Set up ComfyUI here",
        summary="Substitute installs and prepares a local ComfyUI setup for you.",
        best_if="Best if you want the simplest path.",
        meaning="Substitute creates a local ComfyUI setup in the folder you choose.",
        substitute_handles="Substitute installs ComfyUI, prepares what it needs, and keeps required node packs ready.",
        you_handle="You mainly choose where the files live. Most people can leave the local address alone.",
        technical_note="By default, the managed ComfyUI folder is created as `comfyui` inside your Substitute folder.",
        icon=FIF.HOME,
    ),
    OnboardingTargetMode.ATTACHED_LOCAL: TargetModePresentation(
        title="Use my current ComfyUI",
        summary="Substitute adopts and starts the local ComfyUI setup you already use.",
        best_if="Best if you already have local ComfyUI set up.",
        meaning="Substitute uses your current local ComfyUI folder without reinstalling the repository.",
        substitute_handles="Substitute saves that folder, prepares the Python environment it needs, and starts ComfyUI for you.",
        you_handle="You keep your ComfyUI files and models. Substitute takes over launching it while the app is running.",
        technical_note="The ComfyUI folder is required so Substitute can launch it and inspect local custom-node files.",
        icon=FIF.LINK,
    ),
    OnboardingTargetMode.REMOTE: TargetModePresentation(
        title="Use remote ComfyUI",
        summary="Substitute connects to a ComfyUI server running on another machine.",
        best_if="Best if ComfyUI lives on another machine.",
        meaning="Substitute sends work to a remote ComfyUI server instead of starting one here.",
        substitute_handles="Substitute saves the remote address and prepares the local pieces it still needs for the canvas.",
        you_handle="You keep the remote ComfyUI server running and reachable from this computer.",
        technical_note="Some canvas features still need a local Python environment even when ComfyUI itself is remote.",
        icon=FIF.IOT,
    ),
}


class OnboardingHeroPanel(QFrame):
    """Render the slim page header shared by the onboarding pages."""

    def __init__(
        self,
        *,
        title: str,
        description: str,
        icon: object,
        eyebrow: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build the compact hero with icon badge, title, and supporting line."""

        super().__init__(parent)
        self.setObjectName("OnboardingHeroPanel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        badge = QFrame(self)
        badge.setObjectName("OnboardingHeroBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setSpacing(0)
        icon_widget = IconWidget(icon, badge)
        icon_widget.setFixedSize(22, 22)
        badge_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(5)

        eyebrow_label = CaptionLabel(eyebrow, self)
        eyebrow_label.setObjectName("OnboardingHeroEyebrow")
        text_layout.addWidget(eyebrow_label)

        self.title_label = BodyLabel(title, self)
        self.title_label.setObjectName("OnboardingPageTitle")
        self.title_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)

        self.description_label = CaptionLabel(description, self)
        self.description_label.setObjectName("OnboardingPageDescription")
        self.description_label.setWordWrap(True)
        text_layout.addWidget(self.description_label)

        layout.addLayout(text_layout, 1)


class OnboardingPageFrame(QFrame):
    """Render one onboarding page with a compact header and primary content body."""

    def __init__(
        self,
        *,
        title: str,
        description: str,
        icon: object,
        eyebrow: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build the shared page surface and expose a body layout for content."""

        super().__init__(parent)
        self.setObjectName("OnboardingPageFrame")

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addStretch(1)

        self.content_column = QWidget(self)
        self.content_column.setObjectName("OnboardingContentColumn")
        self.content_column.setMinimumWidth(820)
        self.content_column.setMaximumWidth(980)
        layout = QVBoxLayout(self.content_column)
        layout.setContentsMargins(4, 6, 4, 8)
        layout.setSpacing(18)

        self.hero_panel = OnboardingHeroPanel(
            title=title,
            description=description,
            icon=icon,
            eyebrow=eyebrow,
            parent=self,
        )
        layout.addWidget(self.hero_panel)

        self.body_layout = QVBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(14)
        layout.addLayout(self.body_layout)
        layout.addStretch(1)
        outer_layout.addWidget(self.content_column, 8)
        outer_layout.addStretch(1)


class OnboardingInfoPanel(QFrame):
    """Render a restrained supporting panel for secondary onboarding detail."""

    def __init__(
        self,
        *,
        title: str,
        description: str,
        detail_lines: tuple[str, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        """Build the supporting panel with one short description and optional bullets."""

        super().__init__(parent)
        self.setObjectName("OnboardingInfoPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        self.title_label = BodyLabel(title, self)
        self.title_label.setObjectName("OnboardingInfoTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.description_label = CaptionLabel(description, self)
        self.description_label.setObjectName("OnboardingInfoDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.detail_labels: list[CaptionLabel] = []
        for detail_line in detail_lines:
            detail_label = CaptionLabel(detail_line, self)
            detail_label.setObjectName("OnboardingInfoDetail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)
            self.detail_labels.append(detail_label)


class OnboardingFieldBlock(QFrame):
    """Render one labeled field with a concise user-facing helper line."""

    def __init__(
        self,
        *,
        label: str,
        helper_text: str,
        field: QWidget,
        trailing_widget: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the field block around the supplied field widget."""

        super().__init__(parent)
        self.setObjectName("OnboardingFieldBlock")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        label_widget = CaptionLabel(label, self)
        label_widget.setObjectName("OnboardingFieldLabel")
        layout.addWidget(label_widget)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(field, 1)
        if trailing_widget is not None:
            row.addWidget(trailing_widget)
        layout.addLayout(row)

        helper_label = CaptionLabel(helper_text, self)
        helper_label.setObjectName("OnboardingFieldHelper")
        helper_label.setWordWrap(True)
        layout.addWidget(helper_label)


class OnboardingSectionPanel(QFrame):
    """Render one primary content section inside a page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the generic section container used by onboarding pages."""

        super().__init__(parent)
        self.setObjectName("OnboardingSectionPanel")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(18, 16, 18, 16)
        self.content_layout.setSpacing(12)


class TargetModeCard(QFrame):
    """Render one selectable setup card for the target-mode page."""

    clicked = Signal(str)

    def __init__(
        self,
        *,
        mode: OnboardingTargetMode,
        presentation: TargetModePresentation,
        parent: QWidget | None = None,
    ) -> None:
        """Build the card using concise compare-first copy."""

        super().__init__(parent)
        self._mode = mode
        self.setObjectName(f"OnboardingTargetCard_{mode.value}")
        self.setProperty("targetMode", mode.value)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        badge = QFrame(self)
        badge.setObjectName("OnboardingTargetCardBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(9, 9, 9, 9)
        badge_layout.setSpacing(0)
        icon_widget = IconWidget(presentation.icon, badge)
        icon_widget.setFixedSize(20, 20)
        badge_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(4)

        self.title_label = BodyLabel(presentation.title, self)
        self.title_label.setObjectName("OnboardingTargetCardTitle")
        self.title_label.setWordWrap(True)
        text_column.addWidget(self.title_label)

        self.summary_label = CaptionLabel(presentation.summary, self)
        self.summary_label.setObjectName("OnboardingTargetCardSummary")
        self.summary_label.setWordWrap(True)
        text_column.addWidget(self.summary_label)
        header_row.addLayout(text_column, 1)
        layout.addLayout(header_row)

        self.best_if_label = CaptionLabel(presentation.best_if, self)
        self.best_if_label.setObjectName("OnboardingTargetCardBestIf")
        self.best_if_label.setWordWrap(True)
        layout.addWidget(self.best_if_label)

        layout.addStretch(1)

        self.selection_radio = RadioButton("Select", self)
        self.selection_radio.setObjectName(f"OnboardingTargetCardRadio_{mode.value}")
        self.selection_radio.setProperty("targetMode", mode.value)
        self.selection_radio.setAutoExclusive(False)
        self.selection_radio.clicked.connect(self._emit_clicked)
        layout.addWidget(self.selection_radio, alignment=Qt.AlignmentFlag.AlignLeft)

    def set_selected(self, selected: bool) -> None:
        """Apply the selected visual treatment to the card."""

        self.setProperty("selected", selected)
        self.selection_radio.setChecked(selected)
        self.selection_radio.setText("Selected" if selected else "Select")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit the selected target mode when the card is pressed."""

        self._emit_clicked()
        super().mousePressEvent(event)

    def _emit_clicked(self) -> None:
        """Emit the configured target mode for card and button activation."""

        self.clicked.emit(self._mode.value)


class TargetModeSummaryPanel(QFrame):
    """Render the selected-mode summary beneath the target-mode cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the compact summary block for the current target choice."""

        super().__init__(parent)
        self.setObjectName("OnboardingModeSummaryPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        self.meaning_label = CaptionLabel("", self)
        self.meaning_label.setObjectName("OnboardingModeSummaryText")
        self.meaning_label.setWordWrap(True)
        layout.addWidget(self.meaning_label)

        self.substitute_label = CaptionLabel("", self)
        self.substitute_label.setObjectName("OnboardingModeSummaryText")
        self.substitute_label.setWordWrap(True)
        layout.addWidget(self.substitute_label)

        self.you_label = CaptionLabel("", self)
        self.you_label.setObjectName("OnboardingModeSummaryText")
        self.you_label.setWordWrap(True)
        layout.addWidget(self.you_label)

        self.technical_label = CaptionLabel("", self)
        self.technical_label.setObjectName("OnboardingModeTechnicalNote")
        self.technical_label.setWordWrap(True)
        layout.addWidget(self.technical_label)

    def set_presentation(self, presentation: TargetModePresentation) -> None:
        """Render the selected target-mode summary lines."""

        self.meaning_label.setText(presentation.meaning)
        self.substitute_label.setText(presentation.substitute_handles)
        self.you_label.setText(presentation.you_handle)
        self.technical_label.setText(presentation.technical_note)


class InstallRootPage(OnboardingPageFrame):
    """Collect the installation root used for the visible Substitute setup."""

    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the first-run folder page with one primary action area."""

        super().__init__(
            title="Choose where Substitute should keep its setup",
            description="Pick the main folder for Substitute's files. If you let Substitute install ComfyUI for you, it will place that there too by default.",
            icon=FIF.FOLDER,
            eyebrow="Start here",
            parent=parent,
        )
        self.setObjectName("OnboardingWelcomePage")
        self.install_root_edit = LineEdit(self)
        self.install_root_edit.setObjectName("OnboardingInstallRootEdit")
        self.install_root_edit.setPlaceholderText(substitute_install_example())
        browse_button = PushButton("Browse...", self)
        browse_button.setObjectName("OnboardingInstallRootBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="Folder",
                helper_text="Substitute will keep its own settings and setup files here. You can still switch between managed, existing, or remote ComfyUI later.",
                field=self.install_root_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        support_label = CaptionLabel(
            "Substitute may create settings, a local runtime, cubes, and a `comfyui` folder here if you choose the managed setup.",
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
            title="Choose how Substitute should reach ComfyUI",
            description="Pick the setup that matches your current situation. You can change this later if your workflow changes.",
            icon=FIF.LINK,
            eyebrow="Choose your setup",
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
            label="Host",
            helper_text="This is the address Substitute will use to reach ComfyUI.",
            field=fields.host_edit,
            parent=parent,
        ),
        2,
    )
    row.addWidget(
        OnboardingFieldBlock(
            label="Port",
            helper_text="This is the port number used by that ComfyUI address.",
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

        title_label = BodyLabel("Setup summary", self)
        title_label.setObjectName("OnboardingInfoTitle")
        layout.addWidget(title_label)

        self.platform_label = CaptionLabel("", self)
        self.accelerator_label = CaptionLabel("", self)
        self.target_label = CaptionLabel("", self)
        self.python_label = CaptionLabel("", self)
        self.channel_label = CaptionLabel("", self)
        self.backend_label = CaptionLabel("", self)
        self.torch_channel_label = CaptionLabel("", self)
        self.stability_label = CaptionLabel("", self)

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

        self.torch_reason_label = CaptionLabel("", self)
        self.torch_reason_label.setObjectName("OnboardingRuntimeSummaryReason")
        self.torch_reason_label.setWordWrap(True)
        layout.addWidget(self.torch_reason_label)

        advanced_title = CaptionLabel("Advanced options", self)
        advanced_title.setObjectName("OnboardingFieldLabel")
        layout.addWidget(advanced_title)

        self.force_cpu_checkbox = CheckBox("Force CPU mode", self)
        self.edge_torch_checkbox = CheckBox("Prefer cutting-edge torch backend", self)
        self.edge_channel_checkbox = CheckBox("Use edge ComfyUI channel", self)

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

        self.platform_label.setText(f"Platform: {detected_platform or 'Detecting'}")
        self.accelerator_label.setText(
            f"Accelerator: {detected_accelerator or 'Detecting'}"
        )
        self.target_label.setText(
            f"Install target: {selected_install_target or 'Pending selection'}"
        )
        self.python_label.setText(
            f"Python: {selected_python_version or 'Pending selection'}"
        )
        self.channel_label.setText(
            f"ComfyUI channel: {selected_comfy_channel or 'Pending selection'}"
        )
        self.backend_label.setText(
            f"Backend: {selected_backend_policy or 'Pending selection'}"
        )
        self.torch_channel_label.setText(
            f"Torch channel: {selected_torch_channel or 'Pending selection'}"
        )
        self.torch_reason_label.setText(
            f"Reason: {selected_torch_reason or 'Pending selection'}"
        )
        self.stability_label.setText(
            f"Path stability: {selected_stability or 'Pending selection'}"
        )


class ManagedLocalPage(OnboardingPageFrame):
    """Collect the managed-local endpoint and workspace choices."""

    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the managed-local page with the form as the primary content."""

        super().__init__(
            title="Let Substitute set up ComfyUI for you",
            description="This is the easiest option for most people. Substitute installs ComfyUI, prepares it, and keeps the setup ready to use.",
            icon=FIF.HOME,
            eyebrow="Recommended for most people",
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
        browse_button = PushButton("Browse...", self)
        browse_button.setObjectName("OnboardingManagedWorkspaceBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addLayout(
            _build_endpoint_row(fields=fields, parent=self)
        )
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="ComfyUI folder",
                helper_text="This is where Substitute will place ComfyUI. Most people can keep the default location.",
                field=self.workspace_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        self.next_steps_panel = OnboardingInfoPanel(
            title="What happens next",
            description="Substitute saves this setup, installs ComfyUI in the folder above, picks the right backend for this machine, and prepares what it needs to run.",
            detail_lines=(
                "Most people can leave the local address unchanged.",
                "First-time setup can take a while because ComfyUI and Python packages may need to be installed.",
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
    python_browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the attached-local configuration page."""

        super().__init__(
            title="Use the ComfyUI setup you already have",
            description="Substitute will use this local ComfyUI folder, prepare what it needs, and start it for you.",
            icon=FIF.LINK,
            eyebrow="Keep your existing setup",
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
        browse_button = PushButton("Browse...", self)
        browse_button.setObjectName("OnboardingAttachedWorkspaceBrowseButton")
        browse_button.clicked.connect(self.browse_requested.emit)
        self.python_edit = LineEdit(self)
        self.python_edit.setObjectName("OnboardingAttachedPythonEdit")
        self.python_edit.setPlaceholderText(
            "Automatically detect from the ComfyUI folder"
        )
        python_browse_button = PushButton("Browse...", self)
        python_browse_button.setObjectName("OnboardingAttachedPythonBrowseButton")
        python_browse_button.clicked.connect(self.python_browse_requested.emit)

        section = OnboardingSectionPanel(self)
        section.content_layout.addLayout(
            _build_endpoint_row(fields=fields, parent=self)
        )
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="ComfyUI folder",
                helper_text="Choose the folder that contains your existing ComfyUI main.py file. Substitute will launch this copy when it starts.",
                field=self.workspace_edit,
                trailing_widget=browse_button,
                parent=self,
            )
        )
        section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="Python executable",
                helper_text="Leave this blank to detect Python automatically. If your setup is unusual, choose the Python executable ComfyUI uses.",
                field=self.python_edit,
                trailing_widget=python_browse_button,
                parent=self,
            )
        )
        section.content_layout.addWidget(
            OnboardingInfoPanel(
                title="What happens next",
                description="Substitute saves this folder as a local launch target and prepares the Python environment it needs.",
                detail_lines=(
                    "ComfyUI does not need to be running during setup.",
                    "Substitute will start it and then wait for the local address to respond.",
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
            title="Connect to ComfyUI on another machine",
            description="Use this when ComfyUI lives on another PC or server and you want Substitute to reach it from here.",
            icon=FIF.IOT,
            eyebrow="Remote connection",
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
                title="What happens next",
                description="Substitute saves the remote address and keeps the local pieces it still needs for the canvas on this computer.",
                detail_lines=(
                    "Host and port are the address of the remote ComfyUI server.",
                    "You keep that remote server running and reachable from this PC.",
                ),
                parent=self,
            )
        )
        self.body_layout.addWidget(section)


class FolderSetupPage(OnboardingPageFrame):
    """Collect model and output folder choices without exposing implementation detail."""

    managed_model_browse_requested = Signal()
    output_browse_requested = Signal()
    managed_model_default_requested = Signal()
    output_default_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the folder setup page."""

        super().__init__(
            title="Choose where files should live",
            description="These defaults work well for most people. Change them if you already keep models or finished images somewhere else.",
            icon=FIF.FOLDER,
            eyebrow="Folders",
            parent=parent,
        )
        self.setObjectName("OnboardingFolderSetupPage")
        self.content_column.setMinimumWidth(720)
        self.managed_model_root_edit = LineEdit(self)
        self.managed_model_root_edit.setObjectName("OnboardingManagedModelRootEdit")
        self.output_root_edit = LineEdit(self)
        self.output_root_edit.setObjectName("OnboardingOutputRootEdit")

        self.managed_model_browse_button = PushButton("Browse...", self)
        self.managed_model_browse_button.setObjectName(
            "OnboardingManagedModelRootBrowseButton"
        )
        self.managed_model_default_button = PushButton("Use default", self)
        self.managed_model_default_button.setObjectName(
            "OnboardingManagedModelRootDefaultButton"
        )
        self.output_browse_button = PushButton("Browse...", self)
        self.output_browse_button.setObjectName("OnboardingOutputRootBrowseButton")
        self.output_default_button = PushButton("Use default", self)
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
        self.managed_model_section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="Models folder",
                helper_text="ComfyUI looks here for checkpoints, LoRAs, VAEs, and other model files. You can keep the default or choose a folder you already use.",
                field=self.managed_model_root_edit,
                trailing_widget=model_buttons,
                parent=self,
            )
        )
        self.body_layout.addWidget(self.managed_model_section)

        output_section = OnboardingSectionPanel(self)
        output_buttons = self._button_row(
            self.output_browse_button,
            self.output_default_button,
        )
        output_section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="Output folder",
                helper_text="Substitute saves finished images here. The default keeps them with your Substitute files.",
                field=self.output_root_edit,
                trailing_widget=output_buttons,
                parent=self,
            )
        )
        self.body_layout.addWidget(output_section)

    def set_managed_model_visible(self, visible: bool) -> None:
        """Show model-folder controls only for managed-local setup."""

        self.managed_model_section.setVisible(visible)

    def _button_row(self, *buttons: PushButton) -> QWidget:
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

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the friendly integrations setup page."""

        super().__init__(
            title="Choose helpful extras",
            description="These features help with tags, model info, and preview image preferences. You can change them later in Settings.",
            icon=FIF.ROBOT,
            eyebrow="Helpful extras",
            parent=parent,
        )
        self.setObjectName("OnboardingIntegrationsPage")
        self.content_column.setMinimumWidth(900)
        danbooru_tag_help_row, self.danbooru_tag_help_checkbox = self._preference_row(
            "OnboardingDanbooruTagHelpSwitch",
            "Help with prompt tags",
            "Use Danbooru tag tools while writing prompts.",
        )
        self.danbooru_image_policy_combo = self._danbooru_policy_combo()
        danbooru_image_policy_block = OnboardingFieldBlock(
            label="Danbooru image rating",
            helper_text="Choose which Danbooru wiki preview image ratings Substitute may show.",
            field=self.danbooru_image_policy_combo,
            parent=self,
        )
        civitai_model_help_row, self.civitai_model_help_checkbox = self._preference_row(
            "OnboardingCivitaiModelHelpSwitch",
            "Help find model info",
            "Use CivitAI to help identify local models and missing recipe models.",
        )
        civitai_downloads_row, self.civitai_downloads_checkbox = self._preference_row(
            "OnboardingCivitaiDownloadsSwitch",
            "Offer model downloads",
            "When a recipe needs a missing model, Substitute can offer verified CivitAI downloads.",
        )
        self.civitai_thumbnail_policy_combo = self._civitai_thumbnail_policy_combo()
        civitai_thumbnail_policy_block = OnboardingFieldBlock(
            label="CivitAI thumbnail content",
            helper_text="Choose which CivitAI image levels may be used for model thumbnails.",
            field=self.civitai_thumbnail_policy_combo,
            parent=self,
        )
        self.civitai_api_key_edit = LineEdit(self)
        self.civitai_api_key_edit.setObjectName("OnboardingCivitaiApiKeyEdit")
        self.civitai_api_key_edit.setEchoMode(LineEdit.EchoMode.Password)
        self.civitai_api_key_status = CaptionLabel("", self)
        self.civitai_api_key_status.setObjectName("OnboardingCivitaiApiKeyStatus")

        choices_layout = QGridLayout()
        choices_layout.setContentsMargins(0, 0, 0, 0)
        choices_layout.setHorizontalSpacing(14)
        choices_layout.setVerticalSpacing(14)

        danbooru_section = OnboardingSectionPanel(self)
        danbooru_section.content_layout.addWidget(
            self._section_title("Danbooru", danbooru_section)
        )
        danbooru_section.content_layout.addWidget(danbooru_tag_help_row)
        danbooru_section.content_layout.addWidget(danbooru_image_policy_block)
        danbooru_section.content_layout.addStretch(1)

        civitai_section = OnboardingSectionPanel(self)
        civitai_section.content_layout.addWidget(
            self._section_title("CivitAI", civitai_section)
        )
        civitai_section.content_layout.addWidget(civitai_model_help_row)
        civitai_section.content_layout.addWidget(civitai_downloads_row)
        civitai_section.content_layout.addWidget(civitai_thumbnail_policy_block)

        api_section = OnboardingSectionPanel(self)
        api_section.content_layout.addWidget(
            OnboardingFieldBlock(
                label="CivitAI API key (optional)",
                helper_text="You can skip this and add one later in Settings.",
                field=self.civitai_api_key_edit,
                parent=self,
            )
        )
        api_section.content_layout.addWidget(self.civitai_api_key_status)

        choices_layout.addWidget(danbooru_section, 0, 0)
        choices_layout.addWidget(civitai_section, 0, 1)
        choices_layout.addWidget(api_section, 1, 0, 1, 2)
        choices_layout.setColumnStretch(0, 1)
        choices_layout.setColumnStretch(1, 1)
        self.body_layout.addLayout(choices_layout)

    def set_api_key_configured(self, configured: bool) -> None:
        """Render whether a CivitAI API key already exists without showing it."""

        self.civitai_api_key_status.setText(
            "API key already saved" if configured else ""
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
        label: str,
        helper_text: str,
    ) -> tuple[QFrame, CheckBox]:
        """Return a checkbox row with concise helper copy."""

        row = QFrame(self)
        row.setObjectName("OnboardingPreferenceRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        checkbox = CheckBox(label, row)
        checkbox.setObjectName(object_name)
        checkbox.setChecked(True)
        helper_label = CaptionLabel(helper_text, row)
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
        combo.addItem("Safe only", userData=_DANBOORU_SAFE_ONLY)
        combo.addItem(
            "Safe and questionable",
            userData=_DANBOORU_SAFE_AND_QUESTIONABLE,
        )
        combo.addItem("All ratings", userData=_DANBOORU_ALL_RATINGS)
        return combo

    def _civitai_thumbnail_policy_combo(self) -> ComboBox:
        """Create the CivitAI thumbnail content policy selector."""

        combo = ComboBox(self)
        combo.setObjectName("OnboardingCivitaiThumbnailPolicyCombo")
        combo.setMinimumWidth(260)
        combo.addItem("SFW only", userData=_CIVITAI_SFW_ONLY)
        combo.addItem("Allow soft", userData=_CIVITAI_ALLOW_SOFT)
        combo.addItem("Allow all", userData=_CIVITAI_ALLOW_ALL)
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

        label = BodyLabel(text, parent)
        label.setObjectName("OnboardingInfoTitle")
        return label


class ProvisioningPage(OnboardingPageFrame):
    """Display active provisioning status with technical details underneath."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the setup progress page with status-first hierarchy."""

        super().__init__(
            title="Finishing your setup",
            description="The first setup can take a few minutes.",
            icon=FIF.SYNC,
            eyebrow="Setup in progress",
            parent=parent,
        )
        self.setObjectName("OnboardingProvisioningPage")
        self.content_column.setMinimumWidth(760)

        self.status_panel = QFrame(self)
        self.status_panel.setObjectName("OnboardingStatusPanel")
        self.status_panel.setMinimumWidth(0)
        self.status_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        status_layout = QVBoxLayout(self.status_panel)
        status_layout.setContentsMargins(22, 20, 22, 20)
        status_layout.setSpacing(12)

        self.status_label = BodyLabel("Starting setup…", self.status_panel)
        self.status_label.setObjectName("OnboardingProgressStatus")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)

        self.detail_label = CaptionLabel(
            "You can follow the live output below while setup runs.",
            self.status_panel,
        )
        self.detail_label.setObjectName("OnboardingStatusDetail")
        self.detail_label.setWordWrap(True)
        status_layout.addWidget(self.detail_label)

        self.output_title_label = BodyLabel("Live Output", self.status_panel)
        self.output_title_label.setObjectName("OnboardingOutputTitle")
        status_layout.addWidget(self.output_title_label)

        self.details_surface = TerminalOutputView(
            self.status_panel,
            min_height=320,
            max_height=390,
        )
        status_layout.addWidget(self.details_surface)

        self.body_layout.addWidget(self.status_panel)

    def begin_progress(self) -> None:
        """Prepare the provisioning page for active work."""

        self.status_label.setText("Starting setup…")

    def mark_complete(self) -> None:
        """Render the setup as complete."""

    def mark_failed(self) -> None:
        """Render the setup as failed without clearing the log output."""

    def reset_progress(self) -> None:
        """Reset the provisioning page state before a retry begins."""

    def set_output_stream(self, stream: TerminalOutputStream | None) -> None:
        """Bind the shared onboarding output stream to the details surface."""

        self.details_surface.set_stream(stream)

    def append_log(self, line: str) -> None:
        """Append one non-empty log line to the details surface."""

        self.details_surface.append_line(line)

    def clear_details(self) -> None:
        """Reset the rendered details before another provisioning attempt."""

        self.details_surface.clear_output()

    def set_failure_guidance(
        self, *, user_message: str, steps: tuple[str, ...]
    ) -> None:
        """Render user-facing recovery guidance for a provisioning failure."""

        guidance_lines = [user_message, *[f"- {step}" for step in steps]]
        self.detail_label.setText("\n".join(line for line in guidance_lines if line))


class CompletionPage(OnboardingPageFrame):
    """Display a confident finish state after setup or repair succeeds."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the completion page with primary success and optional details."""

        super().__init__(
            title="Substitute is ready",
            description="Your setup has been saved. Review the summary below, then open Substitute or close this window if a restart is needed.",
            icon=FIF.ACCEPT,
            eyebrow="All set",
            parent=parent,
        )
        self.setObjectName("OnboardingCompletionPage")
        self.success_panel = QFrame(self)
        self.success_panel.setObjectName("OnboardingCompletionSurface")
        self.success_panel.setMinimumWidth(560)
        success_layout = QVBoxLayout(self.success_panel)
        success_layout.setContentsMargins(20, 20, 20, 20)
        success_layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(14)

        badge = QFrame(self.success_panel)
        badge.setObjectName("OnboardingCompletionBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setSpacing(0)
        icon_widget = IconWidget(FIF.ACCEPT, badge)
        icon_widget.setFixedSize(28, 28)
        badge_layout.addWidget(icon_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        summary_column = QVBoxLayout()
        summary_column.setContentsMargins(0, 0, 0, 0)
        summary_column.setSpacing(6)

        title_label = BodyLabel("What's ready", self.success_panel)
        title_label.setObjectName("OnboardingInfoTitle")
        summary_column.addWidget(title_label)

        self.summary_label = CaptionLabel("", self.success_panel)
        self.summary_label.setObjectName("OnboardingCompletionSummary")
        self.summary_label.setWordWrap(True)
        summary_column.addWidget(self.summary_label)
        header_row.addLayout(summary_column, 1)
        success_layout.addLayout(header_row)

        self.command_surface = QFrame(self.success_panel)
        self.command_surface.setObjectName("OnboardingCommandSurface")
        command_layout = QVBoxLayout(self.command_surface)
        command_layout.setContentsMargins(16, 14, 16, 14)
        command_layout.setSpacing(8)

        command_title = CaptionLabel("Advanced details", self.command_surface)
        command_title.setObjectName("OnboardingFieldLabel")
        command_layout.addWidget(command_title)

        self.command_label = BodyLabel("", self.command_surface)
        self.command_label.setObjectName("OnboardingCommandLabel")
        self.command_label.setWordWrap(True)
        self.command_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        command_layout.addWidget(self.command_label)
        success_layout.addWidget(self.command_surface)

        self.body_layout.addWidget(self.success_panel)


__all__ = [
    "AttachedLocalPage",
    "CompletionPage",
    "FolderSetupPage",
    "InstallRootPage",
    "IntegrationsPage",
    "ManagedLocalPage",
    "OnboardingPageFrame",
    "ProvisioningPage",
    "RemotePage",
    "TargetModePage",
]
