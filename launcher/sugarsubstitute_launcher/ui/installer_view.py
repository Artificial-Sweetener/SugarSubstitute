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

"""Compose and own the standalone installer widgets and view state."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt, Signal
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
    LineEdit,
    PrimaryPushButton,
    PushButton,
)

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.resources import launcher_icon
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    install_location_guidance,
)
from sugarsubstitute_shared.presentation.terminal import TerminalOutputView


_STEP_TITLES = (
    "Choose a folder",
    "Pick a setup",
    "Confirm the details",
    "Finish setup",
)


class LauncherStepItem(QFrame):
    """Render one compact installer/onboarding progress step."""

    def __init__(
        self,
        *,
        index: int,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build the numbered progress row used by the installer rail."""

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
        """Apply active, complete, or inactive presentation state."""

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


class InstallerView(QWidget):
    """Own installer widgets and expose intent through a narrow view boundary."""

    primary_requested = Signal()

    def __init__(self, *, initial_install_path: str, parent: QWidget) -> None:
        """Build the installer surface with its initial install path."""

        super().__init__(parent)
        self.setObjectName("OnboardingRoot")
        self.install_path_edit = LineEdit(self)
        self.install_path_edit.setText(initial_install_path)
        self.progress_log = TerminalOutputView(
            self,
            min_height=260,
            max_height=340,
        )
        self.primary_button = PrimaryPushButton(self)
        self.browse_button: PushButton
        self.status_panel: QFrame
        self.install_location_guidance_label: CaptionLabel
        self.progress_count_label: CaptionLabel
        self.progress_title_label: BodyLabel
        self.progress_helper_label: CaptionLabel
        self.step_items: list[LauncherStepItem]
        self._build()

    @property
    def install_path(self) -> str:
        """Return the install path currently entered by the user."""

        return cast(str, self.install_path_edit.text())

    def set_path_controls_enabled(self, enabled: bool) -> None:
        """Enable or lock the install path controls as one editable group."""

        self.install_path_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)

    def set_primary_action(self, *, text: str, enabled: bool) -> None:
        """Project the current installer action onto the primary button."""

        self.primary_button.setText(text)
        self.primary_button.setEnabled(enabled)

    def append_log(self, message: str) -> None:
        """Append one user-visible progress line."""

        self.progress_log.append_line(f"{message}\n")

    def show_status_output(self) -> None:
        """Reveal installer output after setup work starts."""

        self.status_panel.show()

    def _choose_install_directory(self) -> None:
        """Prompt the user for a writable install directory."""

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            launcher_text("Choose SugarSubstitute install directory"),
            self.install_path,
        )
        if selected_dir:
            self.install_path_edit.setText(selected_dir)

    def _build(self) -> None:
        """Compose the installer widgets and connect view-owned actions."""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        surface = QWidget(self)
        surface.setObjectName("OnboardingSurface")
        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        identity_rail = QFrame(surface)
        identity_rail.setObjectName("OnboardingIdentityRail")
        identity_rail.setFixedWidth(280)
        rail_layout = QVBoxLayout(identity_rail)
        rail_layout.setContentsMargins(24, 24, 18, 18)
        rail_layout.setSpacing(14)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(12)

        icon_badge = QFrame(identity_rail)
        icon_badge.setObjectName("OnboardingIconBadge")
        icon_badge_layout = QVBoxLayout(icon_badge)
        icon_badge_layout.setContentsMargins(10, 10, 10, 10)
        icon_badge_layout.setSpacing(0)
        icon_label = QLabel(icon_badge)
        icon_label.setPixmap(launcher_icon().pixmap(26, 26))
        icon_label.setFixedSize(26, 26)
        icon_badge_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(icon_badge, alignment=Qt.AlignmentFlag.AlignTop)

        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(4)
        title = BodyLabel(launcher_text("Setup"), identity_rail)
        title.setObjectName("OnboardingRailTitle")
        title.setWordWrap(True)
        brand_text.addWidget(title)
        subtitle = CaptionLabel(
            launcher_text("Choose a folder and connect Substitute to ComfyUI."),
            identity_rail,
        )
        subtitle.setObjectName("OnboardingRailSummary")
        subtitle.setWordWrap(True)
        brand_text.addWidget(subtitle)
        brand_row.addLayout(brand_text, 1)
        rail_layout.addLayout(brand_row)

        self.progress_count_label = CaptionLabel(
            launcher_text("Step 1 of 4"), identity_rail
        )
        self.progress_count_label.setObjectName("OnboardingProgressCount")
        rail_layout.addWidget(self.progress_count_label)
        self.progress_title_label = BodyLabel(
            launcher_text("Choose a folder"), identity_rail
        )
        self.progress_title_label.setObjectName("OnboardingProgressTitle")
        self.progress_title_label.setWordWrap(True)
        rail_layout.addWidget(self.progress_title_label)
        self.progress_helper_label = CaptionLabel(
            launcher_text("You can change the ComfyUI connection later."),
            identity_rail,
        )
        self.progress_helper_label.setObjectName("OnboardingProgressHelper")
        self.progress_helper_label.setWordWrap(True)
        rail_layout.addWidget(self.progress_helper_label)

        self.step_items = []
        for index, step_title in enumerate(_STEP_TITLES, start=1):
            step_item = LauncherStepItem(
                index=index,
                title=launcher_text(step_title),
                parent=identity_rail,
            )
            step_item.set_state(active=index == 1, complete=False)
            rail_layout.addWidget(step_item)
            self.step_items.append(step_item)
        rail_layout.addStretch(1)

        content_panel = QFrame(surface)
        content_panel.setObjectName("OnboardingContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(24, 24, 24, 18)
        content_layout.setSpacing(14)

        page_stage = QWidget(content_panel)
        page_stage.setObjectName("OnboardingPageStage")
        page_stage_layout = QVBoxLayout(page_stage)
        page_stage_layout.setContentsMargins(0, 0, 0, 0)
        page_stage_layout.setSpacing(0)
        page_stage_layout.addStretch(1)

        page_stack = QStackedWidget(content_panel)
        page_stack.setObjectName("OnboardingPageStack")
        page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        install_root_page = QFrame(content_panel)
        install_root_page.setObjectName("OnboardingPageFrame")
        page_outer_layout = QHBoxLayout(install_root_page)
        page_outer_layout.setContentsMargins(0, 0, 0, 0)
        page_outer_layout.setSpacing(0)
        page_outer_layout.addStretch(1)

        content_column = QWidget(install_root_page)
        content_column.setObjectName("OnboardingContentColumn")
        content_column.setMinimumWidth(820)
        content_column.setMaximumWidth(980)
        column_layout = QVBoxLayout(content_column)
        column_layout.setContentsMargins(4, 6, 4, 8)
        column_layout.setSpacing(18)

        hero_panel = QFrame(content_column)
        hero_panel.setObjectName("OnboardingHeroPanel")
        hero_layout = QHBoxLayout(hero_panel)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(14)
        hero_badge = QFrame(hero_panel)
        hero_badge.setObjectName("OnboardingHeroBadge")
        hero_badge_layout = QVBoxLayout(hero_badge)
        hero_badge_layout.setContentsMargins(10, 10, 10, 10)
        hero_badge_layout.setSpacing(0)
        folder_icon = IconWidget(FIF.FOLDER, hero_badge)
        folder_icon.setFixedSize(22, 22)
        hero_badge_layout.addWidget(folder_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(hero_badge, alignment=Qt.AlignmentFlag.AlignTop)

        hero_text = QVBoxLayout()
        hero_text.setContentsMargins(0, 0, 0, 0)
        hero_text.setSpacing(5)
        eyebrow = CaptionLabel(launcher_text("Start here"), hero_panel)
        eyebrow.setObjectName("OnboardingHeroEyebrow")
        hero_text.addWidget(eyebrow)
        page_title = BodyLabel(
            launcher_text("Choose where Substitute should keep its setup"),
            hero_panel,
        )
        page_title.setObjectName("OnboardingPageTitle")
        page_title.setWordWrap(True)
        hero_text.addWidget(page_title)
        page_description = CaptionLabel(
            launcher_text(
                "Pick the main folder for Substitute's files. If you let Substitute install ComfyUI for you, it will place that there too by default."
            ),
            hero_panel,
        )
        page_description.setObjectName("OnboardingPageDescription")
        page_description.setWordWrap(True)
        hero_text.addWidget(page_description)
        hero_layout.addLayout(hero_text, 1)
        column_layout.addWidget(hero_panel)

        location_panel = QFrame(content_column)
        location_panel.setObjectName("OnboardingSectionPanel")
        panel_layout = QVBoxLayout(location_panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)
        path_block = QFrame(location_panel)
        path_block.setObjectName("OnboardingFieldBlock")
        path_block_layout = QVBoxLayout(path_block)
        path_block_layout.setContentsMargins(0, 0, 0, 0)
        path_block_layout.setSpacing(7)
        path_label = CaptionLabel(launcher_text("Folder"), path_block)
        path_label.setObjectName("OnboardingFieldLabel")
        path_block_layout.addWidget(path_label)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(10)
        self.install_path_edit.setMinimumHeight(36)
        self.browse_button = PushButton(launcher_text("Browse..."), path_block)
        self.browse_button.clicked.connect(self._choose_install_directory)
        path_row.addWidget(self.install_path_edit, 1)
        path_row.addWidget(self.browse_button)
        path_block_layout.addLayout(path_row)
        helper_label = CaptionLabel(
            launcher_text(
                "Substitute will place the desktop launcher, source app payload, local runtime, settings, and user data under this folder."
            ),
            path_block,
        )
        helper_label.setObjectName("OnboardingFieldHelper")
        helper_label.setWordWrap(True)
        path_block_layout.addWidget(helper_label)
        self.install_location_guidance_label = CaptionLabel(
            install_location_guidance(),
            path_block,
        )
        self.install_location_guidance_label.setObjectName("OnboardingFieldHelper")
        self.install_location_guidance_label.setWordWrap(True)
        path_block_layout.addWidget(self.install_location_guidance_label)
        panel_layout.addWidget(path_block)
        column_layout.addWidget(location_panel)

        self.status_panel = QFrame(content_column)
        self.status_panel.setObjectName("OnboardingStatusPanel")
        status_layout = QVBoxLayout(self.status_panel)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)
        status_title = BodyLabel(launcher_text("Live Output"), self.status_panel)
        status_title.setObjectName("OnboardingOutputTitle")
        status_layout.addWidget(status_title)
        status_layout.addWidget(self.progress_log)
        column_layout.addWidget(self.status_panel)
        self.status_panel.hide()
        column_layout.addStretch(1)
        page_outer_layout.addWidget(content_column, 1)
        page_outer_layout.addStretch(1)
        page_stack.addWidget(install_root_page)
        page_stack.setCurrentWidget(install_root_page)

        page_stage_layout.addWidget(
            page_stack,
            0,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        page_stage_layout.addStretch(1)
        content_layout.addWidget(page_stage, 1)

        footer_row = QFrame(content_panel)
        footer_row.setObjectName("OnboardingFooterRow")
        footer_layout = QHBoxLayout(footer_row)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)
        self.primary_button.setObjectName("LauncherPrimaryButton")
        self.primary_button.clicked.connect(self.primary_requested)
        self.primary_button.setMinimumWidth(164)
        footer_layout.addWidget(
            self.primary_button,
            0,
            Qt.AlignmentFlag.AlignRight,
        )
        content_layout.addWidget(footer_row)

        surface_layout.addWidget(identity_rail, 0)
        surface_layout.addWidget(content_panel, 1)
        surface_layout.setStretch(0, 0)
        surface_layout.setStretch(1, 1)
        root_layout.addWidget(surface)
