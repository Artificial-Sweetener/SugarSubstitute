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

"""Render the dedicated qfluent onboarding, repair, and reconfigure window."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QMouseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    IconWidget,
    PrimaryPushButton,
    PushButton,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)

from substitute.application.onboarding import OnboardingProvisioningFailure
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
    initial_onboarding_page,
)
from substitute.presentation.onboarding.onboarding_pages import (
    AttachedLocalPage,
    CompletionPage,
    FolderSetupPage,
    InstallRootPage,
    IntegrationsPage,
    ManagedLocalPage,
    ProvisioningPage,
    RemotePage,
    TargetModePage,
)
from substitute.presentation.resources.app_icon import application_icon
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from substitute.shared.logging.logger import get_logger, log_warning


_FLOW_SUMMARY_BY_MODE = {
    OnboardingFlowMode.FIRST_RUN: "Choose a folder and connect Substitute to ComfyUI.",
    OnboardingFlowMode.REPAIR: "Fix the saved setup so Substitute can open again.",
    OnboardingFlowMode.RECONFIGURE: "Change the saved setup or ComfyUI connection.",
}

_STEP_TITLES = (
    "Choose a folder",
    "Pick a setup",
    "Confirm the details",
    "Finish setup",
)

_ONBOARDING_WINDOW_WIDTH = 1260
_ONBOARDING_WINDOW_HEIGHT = 800

_LOGGER = get_logger("presentation.onboarding.onboarding_window")


@dataclass(frozen=True)
class ProgressPresentation:
    """Describe the compact rail progress copy for one page."""

    step_number: int
    step_count: int
    title: str
    helper: str


_PROGRESS_BY_PAGE = {
    OnboardingPageId.WELCOME: ProgressPresentation(
        step_number=1,
        step_count=4,
        title="Choose a folder",
        helper="You can change the ComfyUI connection later.",
    ),
    OnboardingPageId.TARGET_MODE: ProgressPresentation(
        step_number=2,
        step_count=4,
        title="Pick a setup",
        helper="Most people should start with the first option.",
    ),
    OnboardingPageId.MANAGED_LOCAL: ProgressPresentation(
        step_number=3,
        step_count=4,
        title="Confirm the details",
        helper="The defaults usually work well for first-time setup.",
    ),
    OnboardingPageId.ATTACHED_LOCAL: ProgressPresentation(
        step_number=3,
        step_count=4,
        title="Confirm the details",
        helper="Choose the existing ComfyUI folder Substitute should launch.",
    ),
    OnboardingPageId.REMOTE: ProgressPresentation(
        step_number=3,
        step_count=4,
        title="Confirm the details",
        helper="Use the server address this computer can reach.",
    ),
    OnboardingPageId.FOLDERS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title="Confirm the details",
        helper="Keep the defaults or point Substitute at your folders.",
    ),
    OnboardingPageId.INTEGRATIONS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title="Confirm the details",
        helper="Helpful extras can be changed later in Settings.",
    ),
    OnboardingPageId.PROVISIONING: ProgressPresentation(
        step_number=4,
        step_count=4,
        title="Finish setup",
        helper="This can take a little while the first time.",
    ),
    OnboardingPageId.COMPLETION: ProgressPresentation(
        step_number=4,
        step_count=4,
        title="Ready to launch",
        helper="You're almost done.",
    ),
}


class OnboardingIssuePanel(QFrame):
    """Render repair-mode issues in a supportive inline surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the issue panel used for repair and incomplete setup states."""

        super().__init__(parent)
        self.setObjectName("OnboardingIssuePanel")
        self._text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        self.icon_widget = IconWidget(FIF.INFO, self)
        self.icon_widget.setFixedSize(16, 16)
        header_row.addWidget(self.icon_widget, alignment=Qt.AlignmentFlag.AlignTop)

        self.title_label = CaptionLabel("Let's get this setup back on track", self)
        self.title_label.setObjectName("OnboardingIssueTitle")
        self.title_label.setWordWrap(True)
        header_row.addWidget(self.title_label, 1, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        self.body_label = CaptionLabel("", self)
        self.body_label.setObjectName("OnboardingIssueBody")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

    def set_issue_content(self, *, title: str, body: str, detail: str) -> None:
        """Render the issue headline, user guidance, and technical detail."""

        self.title_label.setText(title)
        self.body_label.setText(body)
        self.setToolTip(detail)
        self._text = "\n".join(part for part in (title, body, detail) if part)

    def setText(self, text: str) -> None:
        """Preserve the label-like API used by existing tests."""

        self.set_issue_content(title=self.title_label.text(), body=text, detail="")

    def text(self) -> str:
        """Return the rendered issue copy for contract tests."""

        return self._text


class OnboardingStepItem(QFrame):
    """Render one compact numbered onboarding step inside the rail."""

    def __init__(
        self,
        *,
        index: int,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build the compact numbered step row used for guided progress."""

        super().__init__(parent)
        self.setObjectName("OnboardingStepItem")
        self.setProperty("stepState", "inactive")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.index_label = BodyLabel(str(index), self)
        self.index_label.setObjectName("OnboardingStepNumber")
        layout.addWidget(self.index_label, alignment=Qt.AlignmentFlag.AlignTop)

        self.title_label = CaptionLabel(title, self)
        self.title_label.setObjectName("OnboardingStepTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label, 1)

    def set_state(self, *, active: bool, complete: bool) -> None:
        """Apply the visual state for the current, completed, or pending step."""

        if active:
            state = "active"
        elif complete:
            state = "complete"
        else:
            state = "inactive"
        self.setProperty("stepState", state)
        self.index_label.setProperty("stepState", state)
        self.title_label.setProperty("stepState", state)
        for widget in (self, self.index_label, self.title_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class OnboardingWindow(SubstituteWindowFrame):
    """Render a polished onboarding surface inside the shared Substitute shell."""

    launch_requested = Signal(object)
    close_requested = Signal()

    def __init__(
        self,
        *,
        controller: OnboardingController,
        install_root_locked: bool = False,
        initial_geometry: tuple[int, int, int, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the onboarding shell and connect it to the controller."""

        super().__init__(parent, create_menu_container=False)
        self._controller = controller
        self._install_root_locked = install_root_locked
        self._initial_geometry = initial_geometry
        self._current_page = self._initial_page()
        self._provisioning_started = False
        self._last_completion: OnboardingCompletion | None = None
        self._emit_close_requested_on_close = True
        self._drag_widgets: set[QWidget] = set()
        self._provisioning_output_stream = TerminalOutputStream(max_lines=2000)

        self.setObjectName("OnboardingWindow")
        self.setWindowTitle(self._window_title(controller.flow_mode))
        self.setWindowIcon(application_icon())
        self.setFixedSize(_ONBOARDING_WINDOW_WIDTH, _ONBOARDING_WINDOW_HEIGHT)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()

        self._build_ui()
        self.titleBar.raise_()
        self._install_drag_regions()
        self._apply_styles()
        connect_theme_refresh(self, self._apply_styles)
        self._connect_signals()
        self._apply_draft(controller.draft)
        self._render_issues()
        self._show_page(self._current_page)
        self._place_initial_window()

    def _build_ui(self) -> None:
        """Build the shell, quiet orientation rail, and dominant content area."""

        self.root_container = QWidget(self)
        self.root_container.setObjectName("OnboardingRoot")

        root_layout = QVBoxLayout(self.root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.content_surface = QWidget(self.root_container)
        self.content_surface.setObjectName("OnboardingSurface")
        surface_layout = QHBoxLayout(self.content_surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        self.identity_rail = QFrame(self.content_surface)
        self.identity_rail.setObjectName("OnboardingIdentityRail")
        self.identity_rail.setFixedWidth(280)
        rail_layout = QVBoxLayout(self.identity_rail)
        rail_layout.setContentsMargins(24, 24, 18, 18)
        rail_layout.setSpacing(14)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(12)

        self.app_icon_badge = QFrame(self.identity_rail)
        self.app_icon_badge.setObjectName("OnboardingIconBadge")
        badge_layout = QVBoxLayout(self.app_icon_badge)
        badge_layout.setContentsMargins(10, 10, 10, 10)
        badge_layout.setSpacing(0)
        self.app_icon = QLabel(self.app_icon_badge)
        self.app_icon.setPixmap(application_icon().pixmap(26, 26))
        self.app_icon.setFixedSize(26, 26)
        badge_layout.addWidget(self.app_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(self.app_icon_badge, alignment=Qt.AlignmentFlag.AlignTop)

        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(4)

        self.flow_title_label = BodyLabel(
            self._window_title(self._controller.flow_mode).replace("Substitute ", ""),
            self.identity_rail,
        )
        self.flow_title_label.setObjectName("OnboardingRailTitle")
        self.flow_title_label.setWordWrap(True)
        brand_text.addWidget(self.flow_title_label)

        self.flow_summary_label = CaptionLabel(
            _FLOW_SUMMARY_BY_MODE[self._controller.flow_mode],
            self.identity_rail,
        )
        self.flow_summary_label.setObjectName("OnboardingRailSummary")
        self.flow_summary_label.setWordWrap(True)
        brand_text.addWidget(self.flow_summary_label)
        brand_row.addLayout(brand_text, 1)
        rail_layout.addLayout(brand_row)

        self.progress_count_label = CaptionLabel("", self.identity_rail)
        self.progress_count_label.setObjectName("OnboardingProgressCount")
        rail_layout.addWidget(self.progress_count_label)

        self.progress_title_label = BodyLabel("", self.identity_rail)
        self.progress_title_label.setObjectName("OnboardingProgressTitle")
        self.progress_title_label.setWordWrap(True)
        rail_layout.addWidget(self.progress_title_label)

        self.progress_helper_label = CaptionLabel("", self.identity_rail)
        self.progress_helper_label.setObjectName("OnboardingProgressHelper")
        self.progress_helper_label.setWordWrap(True)
        rail_layout.addWidget(self.progress_helper_label)

        self.step_items: list[OnboardingStepItem] = []
        for index, title in enumerate(_STEP_TITLES, start=1):
            step_item = OnboardingStepItem(
                index=index,
                title=title,
                parent=self.identity_rail,
            )
            rail_layout.addWidget(step_item)
            self.step_items.append(step_item)

        self.issue_banner = OnboardingIssuePanel(self.identity_rail)
        rail_layout.addWidget(self.issue_banner)
        rail_layout.addStretch(1)

        self.content_panel = QFrame(self.content_surface)
        self.content_panel.setObjectName("OnboardingContentPanel")
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(24, 24, 24, 18)
        content_layout.setSpacing(14)

        self.page_stage = QWidget(self.content_panel)
        self.page_stage.setObjectName("OnboardingPageStage")
        page_stage_layout = QVBoxLayout(self.page_stage)
        page_stage_layout.setContentsMargins(0, 0, 0, 0)
        page_stage_layout.setSpacing(0)
        page_stage_layout.addStretch(1)

        self.page_stack = QStackedWidget(self.content_panel)
        self.page_stack.setObjectName("OnboardingPageStack")
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        page_stage_layout.addWidget(
            self.page_stack,
            0,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        page_stage_layout.addStretch(1)
        content_layout.addWidget(self.page_stage, 1)

        self.install_root_page = InstallRootPage(self.content_panel)
        self.target_mode_page = TargetModePage(self.content_panel)
        self.managed_local_page = ManagedLocalPage(self.content_panel)
        self.attached_local_page = AttachedLocalPage(self.content_panel)
        self.remote_page = RemotePage(self.content_panel)
        self.folder_setup_page = FolderSetupPage(self.content_panel)
        self.integrations_page = IntegrationsPage(self.content_panel)
        self.provisioning_page = ProvisioningPage(self.content_panel)
        self.provisioning_page.set_output_stream(self._provisioning_output_stream)
        self.completion_page = CompletionPage(self.content_panel)
        self._pages = {
            OnboardingPageId.WELCOME: self.install_root_page,
            OnboardingPageId.TARGET_MODE: self.target_mode_page,
            OnboardingPageId.MANAGED_LOCAL: self.managed_local_page,
            OnboardingPageId.ATTACHED_LOCAL: self.attached_local_page,
            OnboardingPageId.REMOTE: self.remote_page,
            OnboardingPageId.FOLDERS: self.folder_setup_page,
            OnboardingPageId.INTEGRATIONS: self.integrations_page,
            OnboardingPageId.PROVISIONING: self.provisioning_page,
            OnboardingPageId.COMPLETION: self.completion_page,
        }
        for page in self._pages.values():
            self.page_stack.addWidget(page)

        self.footer_row = QFrame(self.content_panel)
        self.footer_row.setObjectName("OnboardingFooterRow")
        footer_layout = QHBoxLayout(self.footer_row)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)

        self.back_button = PushButton("Back", self.footer_row)
        self.back_button.setObjectName("OnboardingBackButton")
        self.primary_button = PrimaryPushButton("Continue", self.footer_row)
        self.primary_button.setObjectName("OnboardingPrimaryButton")
        self.back_button.setMinimumWidth(76)
        self.primary_button.setMinimumWidth(164)
        footer_layout.addWidget(self.back_button)
        footer_layout.addWidget(self.primary_button)
        content_layout.addWidget(self.footer_row)

        surface_layout.addWidget(self.identity_rail, 0)
        surface_layout.addWidget(self.content_panel, 1)
        surface_layout.setStretch(0, 0)
        surface_layout.setStretch(1, 1)

        root_layout.addWidget(self.content_surface)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self.root_container)

    def _install_drag_regions(self) -> None:
        """Allow only bare Mica-backed onboarding surfaces to start dragging."""

        for drag_widget in self._drag_region_widgets():
            drag_widget.installEventFilter(self)
            self._drag_widgets.add(drag_widget)

    def _drag_region_widgets(self) -> tuple[QWidget, ...]:
        """Return the specific blank onboarding surfaces that should drag the window."""

        return (
            self.identity_rail,
            self.content_panel,
            self.page_stage,
            self.footer_row,
        )

    def eventFilter(self, watched: object, event: object) -> bool:
        """Start system move when the user presses passive onboarding chrome."""

        if (
            isinstance(watched, QWidget)
            and watched in getattr(self, "_drag_widgets", set())
            and isinstance(event, QMouseEvent)
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and self._drag_hit_is_bare_surface(watched, event)
        ):
            window_handle = self.windowHandle()
            if window_handle is not None:
                try:
                    window_handle.startSystemMove()
                    return True
                except (AttributeError, RuntimeError) as error:
                    log_warning(
                        _LOGGER,
                        "Failed to start onboarding window drag move",
                        error=repr(error),
                    )
        return bool(super().eventFilter(watched, event))

    def _drag_hit_is_bare_surface(self, watched: QWidget, event: QMouseEvent) -> bool:
        """Return True when the press lands on an actual blank drag surface."""

        hit_point = watched.mapTo(self, event.position().toPoint())
        hit_widget = self.childAt(hit_point)
        return hit_widget is watched

    def _apply_styles(self) -> None:
        """Apply onboarding-specific styling tuned for a quieter, balanced layout."""

        accent = themeColor()
        accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
        warning = QColor("#F5A524")
        warning_rgb = f"{warning.red()}, {warning.green()}, {warning.blue()}"
        wash_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
        text_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
        self.setStyleSheet(
            """
            QWidget#OnboardingRoot,
            QWidget#OnboardingSurface,
            QFrame#OnboardingContentPanel {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingIdentityRail {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingIconBadge,
            QFrame#OnboardingHeroBadge,
            QFrame#OnboardingTargetCardBadge,
            QFrame#OnboardingCompletionBadge {
                background-color: rgba(__ACCENT_RGB__, 0.12);
                border: 1px solid rgba(__ACCENT_RGB__, 0.24);
                border-radius: 14px;
            }
            QFrame#OnboardingIssuePanel {
                background-color: rgba(__WARNING_RGB__, 0.10);
                border: 1px solid rgba(__WARNING_RGB__, 0.28);
                border-radius: 16px;
            }
            QFrame#OnboardingStepItem {
                background-color: transparent;
                border: none;
                border-radius: 14px;
            }
            QFrame#OnboardingStepItem[stepState="active"] {
                background-color: rgba(__WASH_RGB__, 0.045);
                border: 1px solid rgba(__WASH_RGB__, 0.075);
            }
            QFrame#OnboardingStepItem[stepState="complete"] {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingPageFrame,
            QWidget#OnboardingContentColumn {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingSectionPanel {
                background-color: rgba(__WASH_RGB__, 0.04);
                border: 1px solid rgba(__WASH_RGB__, 0.075);
                border-radius: 22px;
            }
            QFrame#OnboardingInfoPanel,
            QFrame#OnboardingModeSummaryPanel,
            QFrame#ManagedRuntimeSummaryPanel,
            QFrame#OnboardingStatusPanel {
                background-color: rgba(__WASH_RGB__, 0.035);
                border: 1px solid rgba(__WASH_RGB__, 0.065);
                border-radius: 18px;
            }
            QFrame#OnboardingLogSurface,
            QFrame#OnboardingCommandSurface {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QFrame#OnboardingCompletionSurface {
                background-color: rgba(__WASH_RGB__, 0.025);
                border: none;
                border-radius: 18px;
            }
            QFrame#OnboardingTargetCard {
                background-color: rgba(__WASH_RGB__, 0.025);
                border: 1px solid rgba(__WASH_RGB__, 0.055);
                border-radius: 18px;
            }
            QFrame#OnboardingTargetCard[selected="true"] {
                background-color: rgba(__ACCENT_RGB__, 0.09);
                border: 1px solid rgba(__ACCENT_RGB__, 0.26);
            }
            BodyLabel#OnboardingRailTitle {
                font-size: 24px;
                font-weight: 600;
            }
            CaptionLabel#OnboardingRailSummary,
            CaptionLabel#OnboardingProgressHelper,
            CaptionLabel#OnboardingIssueBody,
            CaptionLabel#OnboardingIssueDetail,
            CaptionLabel#OnboardingPageDescription,
            CaptionLabel#OnboardingFieldHelper,
            CaptionLabel#OnboardingInfoDescription,
            CaptionLabel#OnboardingInfoDetail,
            CaptionLabel#OnboardingModeSummaryText,
            CaptionLabel#OnboardingModeTechnicalNote,
            CaptionLabel#OnboardingTargetCardSummary,
            CaptionLabel#OnboardingTargetCardBestIf,
            CaptionLabel#OnboardingStatusDetail,
            CaptionLabel#OnboardingCompletionSummary,
            CaptionLabel#OnboardingSectionSupport {
                color: rgba(__TEXT_RGB__, 0.74);
            }
            CaptionLabel#OnboardingHeroEyebrow,
            CaptionLabel#OnboardingFieldLabel {
                color: rgba(__ACCENT_RGB__, 0.9);
                font-weight: 600;
                text-transform: uppercase;
            }
            CaptionLabel#OnboardingProgressCount {
                color: rgba(__ACCENT_RGB__, 0.9);
                font-weight: 600;
                text-transform: uppercase;
            }
            BodyLabel#OnboardingPageTitle,
            BodyLabel#OnboardingProgressTitle,
            BodyLabel#OnboardingIssueTitle,
            BodyLabel#OnboardingInfoTitle,
            BodyLabel#OnboardingTargetCardTitle {
                font-size: 22px;
                font-weight: 600;
            }
            BodyLabel#OnboardingTargetCardTitle {
                font-size: 18px;
            }
            BodyLabel#OnboardingIssueTitle {
                font-size: 18px;
            }
            BodyLabel#OnboardingStepNumber {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                border-radius: 12px;
                qproperty-alignment: 'AlignCenter';
                background-color: rgba(__WASH_RGB__, 0.06);
                color: rgba(__TEXT_RGB__, 0.68);
                font-size: 12px;
                font-weight: 700;
            }
            BodyLabel#OnboardingStepNumber[stepState="active"] {
                background-color: rgba(__ACCENT_RGB__, 0.32);
                color: rgba(__TEXT_RGB__, 1.0);
            }
            BodyLabel#OnboardingStepNumber[stepState="complete"] {
                background-color: rgba(__ACCENT_RGB__, 0.18);
                color: rgba(__TEXT_RGB__, 0.92);
            }
            CaptionLabel#OnboardingStepTitle {
                color: rgba(__TEXT_RGB__, 0.62);
            }
            CaptionLabel#OnboardingStepTitle[stepState="active"] {
                color: rgba(__TEXT_RGB__, 0.98);
                font-weight: 600;
            }
            CaptionLabel#OnboardingStepTitle[stepState="complete"] {
                color: rgba(__TEXT_RGB__, 0.78);
            }
            BodyLabel#OnboardingProgressStatus {
                font-size: 24px;
                font-weight: 600;
            }
            BodyLabel#OnboardingOutputTitle {
                color: rgba(__TEXT_RGB__, 0.9);
                font-size: 16px;
                font-weight: 600;
            }
            QFrame#OnboardingFooterRow {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingHeroPanel {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingFieldBlock {
                background-color: transparent;
                border: none;
            }
            BodyLabel#OnboardingCommandLabel {
                font-family: Consolas, 'Courier New', monospace;
                font-size: 13px;
            }
            """.replace("__ACCENT_RGB__", accent_rgb)
            .replace("__WARNING_RGB__", warning_rgb)
            .replace("__WASH_RGB__", wash_rgb)
            .replace("__TEXT_RGB__", text_rgb)
        )

    def _connect_signals(self) -> None:
        """Connect page actions, navigation buttons, and controller signals."""

        self.install_root_page.browse_requested.connect(self._browse_install_root)
        self.managed_local_page.browse_requested.connect(self._browse_managed_workspace)
        self.attached_local_page.browse_requested.connect(
            self._browse_attached_workspace
        )
        self.attached_local_page.python_browse_requested.connect(
            self._browse_attached_python
        )
        self.folder_setup_page.managed_model_browse_requested.connect(
            self._browse_managed_model_root
        )
        self.folder_setup_page.output_browse_requested.connect(self._browse_output_root)
        self.folder_setup_page.managed_model_default_requested.connect(
            self._use_default_managed_model_root
        )
        self.folder_setup_page.output_default_requested.connect(
            self._use_default_output_root
        )
        self.back_button.clicked.connect(self._go_back)
        self.primary_button.clicked.connect(self._advance)
        self._controller.draft_changed.connect(self._apply_draft)
        self._controller.provisioning_started.connect(self._handle_provisioning_started)
        self._controller.provisioning_finished.connect(
            self._handle_provisioning_finished
        )
        self._controller.progress_status_changed.connect(
            self.provisioning_page.status_label.setText
        )
        self._controller.progress_log_emitted.connect(
            self._provisioning_output_stream.append_line
        )
        self._controller.failure_reported.connect(self._handle_failure)
        self._controller.completion_ready.connect(self._handle_completion)

    def _advance(self) -> None:
        """Advance the onboarding flow for the current page."""

        if self._current_page is OnboardingPageId.WELCOME:
            install_root = Path(
                self.install_root_page.install_root_edit.text()
            ).resolve()
            self._controller.set_installation_root(install_root)
        elif self._current_page is OnboardingPageId.TARGET_MODE:
            self._controller.update_target_mode(self.target_mode_page.selected_mode())
        elif self._current_page is OnboardingPageId.MANAGED_LOCAL:
            managed_host = self.managed_local_page.host_edit.text()
            managed_port = self.managed_local_page.port_spinbox.value()
            managed_workspace = Path(
                self.managed_local_page.workspace_edit.text()
            ).resolve()
            runtime_summary = self.managed_local_page.runtime_summary_panel
            force_cpu_mode = runtime_summary.force_cpu_checkbox.isChecked()
            prefer_edge_torch = runtime_summary.edge_torch_checkbox.isChecked()
            prefer_edge_comfy_channel = (
                runtime_summary.edge_channel_checkbox.isChecked()
            )
            self._controller.update_endpoint(
                managed_host,
                managed_port,
            )
            self._controller.update_managed_workspace(managed_workspace)
            self._controller.update_managed_runtime_preferences(
                force_cpu_mode=force_cpu_mode,
                prefer_edge_torch=prefer_edge_torch,
                prefer_edge_comfy_channel=prefer_edge_comfy_channel,
            )
        elif self._current_page is OnboardingPageId.ATTACHED_LOCAL:
            attached_host = self.attached_local_page.host_edit.text()
            attached_port = self.attached_local_page.port_spinbox.value()
            workspace_text = self.attached_local_page.workspace_edit.text().strip()
            python_text = self.attached_local_page.python_edit.text().strip()
            self._controller.update_endpoint(
                attached_host,
                attached_port,
            )
            self._controller.update_attached_workspace(
                Path(workspace_text).resolve() if workspace_text else None
            )
            self._controller.update_attached_python(
                Path(python_text).resolve() if python_text else None
            )
        elif self._current_page is OnboardingPageId.REMOTE:
            remote_host = self.remote_page.host_edit.text()
            remote_port = self.remote_page.port_spinbox.value()
            self._controller.update_endpoint(
                remote_host,
                remote_port,
            )
        elif self._current_page is OnboardingPageId.FOLDERS:
            self._controller.update_folder_preferences(
                managed_model_root=self._selected_managed_model_root(),
                managed_model_root_uses_default=(
                    self._selected_managed_model_root()
                    == self._default_managed_model_root()
                ),
                output_root=self._selected_output_root(),
                output_root_uses_default=(
                    self._selected_output_root() == self._default_output_root()
                ),
            )
        elif self._current_page is OnboardingPageId.INTEGRATIONS:
            self._controller.update_integration_preferences(
                danbooru_tag_help_enabled=self.integrations_page.danbooru_tag_help_checkbox.isChecked(),
                danbooru_safe_previews_enabled=True,
                danbooru_image_rating_policy=self.integrations_page.danbooru_image_policy_value(),
                civitai_model_help_enabled=self.integrations_page.civitai_model_help_checkbox.isChecked(),
                civitai_downloads_enabled=self.integrations_page.civitai_downloads_checkbox.isChecked(),
                civitai_safe_thumbnails_enabled=True,
                civitai_thumbnail_safety_policy=self.integrations_page.civitai_thumbnail_policy_value(),
                civitai_api_key=self.integrations_page.civitai_api_key_edit.text(),
            )
            self.integrations_page.civitai_api_key_edit.clear()
        elif self._current_page is OnboardingPageId.PROVISIONING:
            if not self._provisioning_started:
                self._show_page(OnboardingPageId.PROVISIONING)
            if self._last_completion is not None:
                self._show_page(OnboardingPageId.COMPLETION)
            return
        elif self._current_page is OnboardingPageId.COMPLETION:
            if self._last_completion is None:
                return
            if self._last_completion.restart_required:
                self.close()
                return
            self._emit_close_requested_on_close = False
            self.launch_requested.emit(self._last_completion)
            self.close()
            return

        self._show_page(self._controller.next_page(self._current_page))

    def _go_back(self) -> None:
        """Return to the previous onboarding page when available."""

        previous_page = self._controller.previous_page(self._current_page)
        if self._install_root_locked and previous_page is OnboardingPageId.WELCOME:
            return
        self._show_page(previous_page)

    def _show_page(self, page_id: OnboardingPageId) -> None:
        """Display one page and update navigation state for it."""

        if self._install_root_locked and page_id is OnboardingPageId.WELCOME:
            page_id = OnboardingPageId.TARGET_MODE
        self._current_page = page_id
        self.page_stack.setCurrentWidget(self._pages[page_id])
        self.page_stack.setFixedHeight(self._pages[page_id].sizeHint().height())
        self._update_progress(page_id)

        self.back_button.setEnabled(
            page_id is not OnboardingPageId.WELCOME
            and not (
                self._install_root_locked and page_id is OnboardingPageId.TARGET_MODE
            )
        )
        self.primary_button.setEnabled(True)

        if page_id is OnboardingPageId.PROVISIONING:
            self.back_button.setEnabled(False)
            self.primary_button.setEnabled(False)
            self.primary_button.setText("Working...")
            self.primary_button.adjustSize()
            if not self._provisioning_started:
                self._provisioning_started = True
                self.provisioning_page.clear_details()
                self.provisioning_page.reset_progress()
                self._controller.start_provisioning()
            return

        if page_id is OnboardingPageId.COMPLETION and self._last_completion is not None:
            self.primary_button.setText(
                "Close" if self._last_completion.restart_required else "Open Substitute"
            )
            self.primary_button.adjustSize()
            return

        self.primary_button.setText(self._primary_button_label(page_id))
        self.primary_button.adjustSize()

    def _update_progress(self, page_id: OnboardingPageId) -> None:
        """Refresh the compact progress copy shown in the left rail."""

        progress = _PROGRESS_BY_PAGE[page_id]
        self.progress_count_label.setText(
            f"Step {progress.step_number} of {progress.step_count}"
        )
        self.progress_title_label.setText(progress.title)
        self.progress_helper_label.setText(progress.helper)
        for index, step_item in enumerate(self.step_items, start=1):
            step_item.set_state(
                active=index == progress.step_number,
                complete=index < progress.step_number,
            )

    def _initial_page(self) -> OnboardingPageId:
        """Return the first visible onboarding page for this install mode."""

        return initial_onboarding_page(install_root_locked=self._install_root_locked)

    def _apply_draft(self, _draft: object) -> None:
        """Mirror controller draft state into the page widgets."""

        draft = self._controller.draft
        self.install_root_page.install_root_edit.setText(str(draft.installation_root))
        self.target_mode_page.set_selected_mode(draft.target_mode)
        self.managed_local_page.host_edit.setText(draft.endpoint_host)
        self.managed_local_page.port_spinbox.setValue(draft.endpoint_port)
        self.managed_local_page.workspace_edit.setText(
            str(draft.managed_workspace_path)
        )
        self.managed_local_page.runtime_summary_panel.update_summary(
            detected_platform=draft.detected_platform,
            detected_accelerator=draft.detected_accelerator,
            selected_install_target=draft.selected_install_target,
            selected_python_version=draft.selected_python_version,
            selected_comfy_channel=draft.selected_comfy_channel,
            selected_backend_policy=draft.selected_backend_policy,
            selected_torch_channel=draft.selected_torch_channel,
            selected_torch_reason=draft.selected_torch_reason,
            selected_stability=draft.selected_stability,
        )
        self.managed_local_page.runtime_summary_panel.force_cpu_checkbox.setChecked(
            draft.force_cpu_mode
        )
        self.managed_local_page.runtime_summary_panel.edge_torch_checkbox.setChecked(
            draft.prefer_edge_torch
        )
        self.managed_local_page.runtime_summary_panel.edge_channel_checkbox.setChecked(
            draft.prefer_edge_comfy_channel
        )
        self.attached_local_page.host_edit.setText(draft.endpoint_host)
        self.attached_local_page.port_spinbox.setValue(draft.endpoint_port)
        self.attached_local_page.workspace_edit.setText(
            str(draft.attached_workspace_path or "")
        )
        self.attached_local_page.python_edit.setText(
            str(draft.attached_python_executable or "")
        )
        self.remote_page.host_edit.setText(draft.endpoint_host)
        self.remote_page.port_spinbox.setValue(draft.endpoint_port)
        self.folder_setup_page.set_managed_model_visible(
            draft.target_mode is OnboardingTargetMode.MANAGED_LOCAL
        )
        self.folder_setup_page.managed_model_root_edit.setText(
            str(draft.managed_model_root or self._default_managed_model_root())
        )
        self.folder_setup_page.output_root_edit.setText(
            str(draft.output_root or self._default_output_root())
        )
        self.integrations_page.danbooru_tag_help_checkbox.setChecked(
            draft.danbooru_tag_help_enabled
        )
        self.integrations_page.set_danbooru_image_policy(
            draft.danbooru_image_rating_policy
        )
        self.integrations_page.civitai_model_help_checkbox.setChecked(
            draft.civitai_model_help_enabled
        )
        self.integrations_page.civitai_downloads_checkbox.setChecked(
            draft.civitai_downloads_enabled
        )
        self.integrations_page.set_civitai_thumbnail_policy(
            draft.civitai_thumbnail_safety_policy
        )
        self.integrations_page.set_api_key_configured(draft.civitai_api_key_configured)

    def _render_issues(self) -> None:
        """Render readiness issues inside the quiet repair panel when present."""

        if self._controller.flow_mode is OnboardingFlowMode.FIRST_RUN:
            self.issue_banner.hide()
            return

        issues = self._controller.present_readiness_issues()
        if not issues:
            self.issue_banner.hide()
            return
        if len(issues) == 1:
            issue = issues[0]
            self.issue_banner.set_issue_content(
                title=issue.headline,
                body=issue.user_message,
                detail=issue.technical_detail,
            )
        else:
            body = f"{len(issues)} saved setup items need repair before Substitute can open."
            detail = "\n".join(
                f"- {issue.technical_detail}"
                for issue in issues
                if issue.technical_detail
            )
            self.issue_banner.set_issue_content(
                title="Setup needs attention",
                body=body,
                detail=detail,
            )
        self.issue_banner.show()

    def _handle_provisioning_started(self) -> None:
        """Switch the provisioning page into its active state."""

        self.provisioning_page.begin_progress()
        self.provisioning_page.status_label.setText("Starting setup.")
        self.provisioning_page.detail_label.setText(
            "You can follow the live output below while setup runs."
        )
        self.provisioning_page.clear_details()

    def _handle_provisioning_finished(self) -> None:
        """Re-enable progression once provisioning has finished."""

        self.primary_button.setEnabled(self._last_completion is not None)
        if self._last_completion is not None:
            self.provisioning_page.mark_complete()
            self.primary_button.setText("Review setup")
            self.primary_button.adjustSize()
            return
        self.back_button.setEnabled(True)
        self.primary_button.setEnabled(True)
        self.primary_button.setText("Try again")
        self.primary_button.adjustSize()

    def _handle_failure(self, failure: object) -> None:
        """Render a provisioning failure inside the provisioning page."""

        self.provisioning_page.mark_failed()
        typed_failure = (
            failure
            if isinstance(failure, OnboardingProvisioningFailure)
            else OnboardingProvisioningFailure(
                headline="Setup needs attention.",
                user_message=(
                    "Review the details below, fix the reported issue, and try again."
                ),
                technical_detail=str(failure),
                remediation_steps=(),
            )
        )
        self.provisioning_page.status_label.setText(typed_failure.headline)
        self.provisioning_page.set_failure_guidance(
            user_message=typed_failure.user_message,
            steps=typed_failure.remediation_steps,
        )
        self.provisioning_page.append_log(typed_failure.technical_detail)
        self._provisioning_started = False

    def _handle_completion(self, completion: object) -> None:
        """Store and display a successful onboarding result."""

        typed_completion = (
            completion
            if isinstance(completion, OnboardingCompletion)
            else self._controller.completion
        )
        if typed_completion is None:
            return
        self._last_completion = typed_completion
        if typed_completion.restart_required:
            summary = "Your updated setup has been saved. Close Substitute now, then open it again to use the new configuration."
        else:
            summary = "Your setup is saved and ready to use."
        self.completion_page.summary_label.setText(summary)
        self.completion_page.command_label.setText(
            " ".join(typed_completion.launch_command)
        )
        self.primary_button.setEnabled(True)
        self.primary_button.adjustSize()

    def _browse_install_root(self) -> None:
        """Prompt for the visible installation root directory."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Installation Root",
            self.install_root_page.install_root_edit.text(),
        )
        if selected:
            self.install_root_page.install_root_edit.setText(selected)

    def _browse_managed_workspace(self) -> None:
        """Prompt for the managed-local ComfyUI workspace directory."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Managed ComfyUI Folder",
            self.managed_local_page.workspace_edit.text(),
        )
        if selected:
            self.managed_local_page.workspace_edit.setText(selected)

    def _browse_attached_workspace(self) -> None:
        """Prompt for the existing local ComfyUI folder."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Existing ComfyUI Folder",
            self.attached_local_page.workspace_edit.text(),
        )
        if selected:
            self.attached_local_page.workspace_edit.setText(selected)

    def _browse_attached_python(self) -> None:
        """Prompt for the Python executable used by the attached ComfyUI setup."""

        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose ComfyUI Python Executable",
            self.attached_local_page.python_edit.text(),
            "Python executable (python.exe python);;All files (*)",
        )
        if selected:
            self.attached_local_page.python_edit.setText(selected)

    def _browse_managed_model_root(self) -> None:
        """Prompt for the managed ComfyUI models folder."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Models Folder",
            self.folder_setup_page.managed_model_root_edit.text(),
        )
        if selected:
            self.folder_setup_page.managed_model_root_edit.setText(selected)

    def _browse_output_root(self) -> None:
        """Prompt for the Substitute output folder."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Output Folder",
            self.folder_setup_page.output_root_edit.text(),
        )
        if selected:
            self.folder_setup_page.output_root_edit.setText(selected)

    def _use_default_managed_model_root(self) -> None:
        """Reset the models field to the managed ComfyUI default."""

        self.folder_setup_page.managed_model_root_edit.setText(
            str(self._default_managed_model_root())
        )

    def _use_default_output_root(self) -> None:
        """Reset the output field to Substitute's default output folder."""

        self.folder_setup_page.output_root_edit.setText(
            str(self._default_output_root())
        )

    def _selected_managed_model_root(self) -> Path:
        """Return the selected models folder from the folders page."""

        text = self.folder_setup_page.managed_model_root_edit.text().strip()
        return Path(text).resolve() if text else self._default_managed_model_root()

    def _selected_output_root(self) -> Path:
        """Return the selected output folder from the folders page."""

        text = self.folder_setup_page.output_root_edit.text().strip()
        return Path(text).resolve() if text else self._default_output_root()

    def _default_managed_model_root(self) -> Path:
        """Return ComfyUI's default models folder for the selected workspace."""

        return self._controller.draft.managed_workspace_path / "models"

    def _default_output_root(self) -> Path:
        """Return Substitute's default output folder for the selected install root."""

        return self._controller.draft.installation_root / "user" / "outputs"

    def _center_on_screen(self) -> None:
        """Center the onboarding window on the active screen."""

        screen = self.screen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.left() + (geometry.width() - self.width()) // 2,
            geometry.top() + (geometry.height() - self.height()) // 2,
        )

    def _place_initial_window(self) -> None:
        """Place onboarding on the handoff frame or center it by default."""

        if self._initial_geometry is None:
            self._center_on_screen()
            return
        x, y, width, height = self._initial_geometry
        self.setGeometry(QRect(x, y, width, height))

    def closeEvent(self, event: QCloseEvent) -> None:
        """Emit close routing for non-launch exits before closing the window."""

        if self._emit_close_requested_on_close:
            self.close_requested.emit()
        event.accept()
        super().closeEvent(event)

    @staticmethod
    def _window_title(flow_mode: OnboardingFlowMode) -> str:
        """Return the onboarding window title for one entry mode."""

        if flow_mode is OnboardingFlowMode.REPAIR:
            return "Substitute Repair"
        if flow_mode is OnboardingFlowMode.RECONFIGURE:
            return "Substitute Reconfigure"
        return "Substitute Setup"

    @staticmethod
    def _primary_button_label(page_id: OnboardingPageId) -> str:
        """Return the primary action text for the supplied page."""

        if page_id in {OnboardingPageId.WELCOME, OnboardingPageId.TARGET_MODE}:
            return "Continue"
        if page_id in {
            OnboardingPageId.MANAGED_LOCAL,
            OnboardingPageId.ATTACHED_LOCAL,
            OnboardingPageId.REMOTE,
            OnboardingPageId.FOLDERS,
        }:
            return "Save and continue"
        if page_id is OnboardingPageId.INTEGRATIONS:
            return "Finish setup"
        return "Continue"
