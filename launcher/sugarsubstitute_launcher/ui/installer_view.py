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

"""Compose the language-first launcher portion of the setup journey."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    IconWidget,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.experience_models import (
    ExperiencePage,
    ExperienceSnapshot,
)
from launcher.sugarsubstitute_launcher.ui.experience_pages import RepairScopePage
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    install_location_guidance,
)
from sugarsubstitute_shared.localization import load_language_manifest
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_CONTENT_MAX_WIDTH,
    InstallerBrandBar,
    InstallerBodyMaterialSurface,
    expose_native_material,
)
from sugarsubstitute_shared.presentation.localization.language_selector import (
    ManifestLanguageComboBox,
)
from sugarsubstitute_shared.presentation.terminal import TerminalOutputView

if TYPE_CHECKING:
    from sugarsubstitute_shared.presentation.localization import TranslationManager


class InstallerView(QWidget):
    """Own the launcher's pages while preserving one stable installer shell."""

    primary_requested = Signal()
    back_requested = Signal()

    def __init__(
        self,
        *,
        initial_install_path: str,
        localization_manager: TranslationManager | None,
        show_language_first: bool,
        parent: QWidget,
    ) -> None:
        """Build the shared surface and its language-first entry route."""

        super().__init__(parent)
        self.setObjectName("OnboardingRoot")
        expose_native_material(self)
        self._localization_manager = localization_manager
        self._experience_page = (
            ExperiencePage.LANGUAGE
            if show_language_first
            else ExperiencePage.INSTALL_LOCATION
        )
        self.install_path_edit = LineEdit(self)
        self.install_path_edit.setObjectName("LauncherInstallPathEdit")
        self.install_path_edit.setText(initial_install_path)
        self.progress_log = TerminalOutputView(self, min_height=220, max_height=280)
        self.primary_button = PrimaryPushButton(self)
        self.back_button = PushButton(self)
        self.browse_button = PushButton(self)
        self.install_location_guidance_label = CaptionLabel(self)
        self.status_panel = QFrame(self)
        self._build_shell()
        self._build_pages()
        if show_language_first:
            self.show_language_selection()
        else:
            self.show_install_location()

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
        """Append diagnostics while promoting the latest activity to the page."""

        self.progress_log.append_line(f"{message}\n")
        self.activity_label.setText(message)

    def show_status_output(self) -> None:
        """Show calm progress while keeping console details collapsed."""

        self._experience_page = ExperiencePage.PROGRESS
        self._activate_page(self.status_panel)
        self.back_button.hide()
        self._set_progress(2, 5, launcher_text("Installing SugarSubstitute"))

    def show_failure(self, message: str) -> None:
        """Reveal diagnostics after a failure and retain the retry action."""

        self._experience_page = ExperiencePage.FAILURE
        self.activity_label.setText(message)
        self.details_button.setChecked(True)
        self._set_log_visible(True)

    def show_language_selection(self) -> None:
        """Present the language decision before any installation question."""

        self._experience_page = ExperiencePage.LANGUAGE
        self._activate_page(self.language_page)
        self.back_button.hide()
        self.primary_button.show()
        self._set_progress(1, 5, launcher_text("Language"))
        self.set_primary_action(text=launcher_text("Continue"), enabled=True)

    def show_repair_scope(self) -> None:
        """Reveal recovery without inserting first-run language onboarding."""

        self._experience_page = ExperiencePage.REPAIR_SCOPE
        self._activate_page(self.repair_page)
        self.back_button.hide()
        self.primary_button.hide()
        self._set_progress(1, 4, launcher_text("Choose repair"))

    def show_install_location(self) -> None:
        """Show the first installation decision in the selected language."""

        self._retranslate_install_page()
        self._experience_page = ExperiencePage.INSTALL_LOCATION
        self._activate_page(self.install_location_page)
        self.back_button.setText(launcher_text("Back"))
        self.back_button.setVisible(self._localization_manager is not None)
        self.primary_button.show()
        self._set_progress(2, 5, launcher_text("Choose a folder"))

    def experience_snapshot(self) -> ExperienceSnapshot:
        """Return semantic evidence for qualification and accessibility tests."""

        if self._experience_page is ExperiencePage.LANGUAGE:
            return ExperienceSnapshot(
                page=self._experience_page,
                title=launcher_text("Choose your language"),
                primary_action=self.primary_button.text(),
                secondary_action=None,
                repair_choice=None,
            )
        if self._experience_page is ExperiencePage.REPAIR_SCOPE:
            return ExperienceSnapshot(
                page=self._experience_page,
                title=launcher_text("Put Substitute back in a fresh state"),
                primary_action=self.repair_page.primary_button.text(),
                secondary_action=launcher_text("Cancel"),
                repair_choice=self.repair_page.choice,
            )
        if self._experience_page in {ExperiencePage.PROGRESS, ExperiencePage.FAILURE}:
            return ExperienceSnapshot(
                page=self._experience_page,
                title=launcher_text("Setting up SugarSubstitute"),
                primary_action=self.primary_button.text(),
                secondary_action=None,
                repair_choice=None,
            )
        return ExperienceSnapshot(
            page=self._experience_page,
            title=launcher_text("Choose where Substitute should live"),
            primary_action=self.primary_button.text(),
            secondary_action=(
                self.back_button.text() if self.back_button.isVisible() else None
            ),
            repair_choice=None,
        )

    def _build_shell(self) -> None:
        """Compose the persistent brand bar, washed body, and stable footer."""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.brand_bar = InstallerBrandBar(self)
        root_layout.addWidget(self.brand_bar)

        self.content_panel = InstallerBodyMaterialSurface(
            object_name="InstallerContentWash",
            parent=self,
        )
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(44, 26, 44, 24)
        content_layout.setSpacing(16)

        self.page_stage = QScrollArea(self.content_panel)
        self.page_stage.setObjectName("OnboardingPageStage")
        self.page_stage.setWidgetResizable(True)
        self.page_stage.setFrameShape(QFrame.Shape.NoFrame)
        self.page_stage.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.page_stage.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.page_scroll_content = QWidget(self.page_stage)
        self.page_scroll_content.setObjectName("OnboardingPageScrollContent")
        stage_layout = QVBoxLayout(self.page_scroll_content)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(0)
        stage_layout.addStretch(1)
        self.page_stack = QStackedWidget(self.page_stage)
        self.page_stack.setObjectName("OnboardingPageStack")
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.page_stack.setMaximumWidth(INSTALLER_CONTENT_MAX_WIDTH)
        stage_layout.addWidget(self.page_stack, alignment=Qt.AlignmentFlag.AlignCenter)
        stage_layout.addStretch(1)
        self.page_stage.setWidget(self.page_scroll_content)
        content_layout.addWidget(self.page_stage, 1)

        self.footer_row = QFrame(self.content_panel)
        self.footer_row.setObjectName("OnboardingFooterRow")
        footer_layout = QHBoxLayout(self.footer_row)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)
        self.back_button.clicked.connect(self.back_requested)
        self.primary_button.setObjectName("LauncherPrimaryButton")
        self.primary_button.clicked.connect(self.primary_requested)
        self.back_button.setMinimumWidth(92)
        self.primary_button.setMinimumWidth(168)
        footer_layout.addWidget(self.back_button)
        footer_layout.addWidget(self.primary_button)
        content_layout.addWidget(self.footer_row)
        root_layout.addWidget(self.content_panel, 1)

        self.progress_count_label = self.brand_bar.progress_caption
        self.progress_title_label = self.brand_bar.progress_caption
        self.progress_helper_label = CaptionLabel(self)
        self.progress_helper_label.hide()

    def _activate_page(self, page: QFrame) -> None:
        """Center one page at its declared visual width and reset scrolling."""

        self.page_stack.setCurrentWidget(page)
        content_width = page.property("installerContentWidth")
        if not isinstance(content_width, int):
            content_width = INSTALLER_CONTENT_MAX_WIDTH
        self.page_stack.setFixedWidth(content_width)
        page_layout = page.layout()
        if page_layout is not None:
            page_layout.invalidate()
            page_layout.activate()
        page.updateGeometry()
        self.page_stack.setFixedHeight(page.sizeHint().height())
        self.page_stage.verticalScrollBar().setValue(0)

    def _build_pages(self) -> None:
        """Build the bounded launcher pages owned by this process."""

        self.language_page = self._build_language_page()
        self.install_location_page = self._build_install_location_page()
        self.status_panel = self._build_progress_page()
        self.repair_page = RepairScopePage(self.page_stack)
        for page in (
            self.language_page,
            self.install_location_page,
            self.status_panel,
            self.repair_page,
        ):
            self.page_stack.addWidget(page)
        self.repair_page.setProperty(
            "installerContentWidth", INSTALLER_CONTENT_MAX_WIDTH
        )

    def _build_language_page(self) -> QFrame:
        """Build a quiet language-first page backed by the locale manifest."""

        page, layout = self._new_page("LauncherLanguagePage")
        page.setMinimumWidth(620)
        page.setMaximumWidth(620)
        page.setProperty("installerContentWidth", 620)
        icon_row, text_layout = self._hero_row(page, FIF.LANGUAGE, centered=True)
        self.language_title_label = SubtitleLabel(page)
        self.language_title_label.setObjectName("OnboardingPageTitle")
        self.language_title_label.setMinimumWidth(420)
        self.language_description_label = BodyLabel(page)
        self.language_description_label.setObjectName("OnboardingPageDescription")
        self.language_description_label.setMinimumWidth(420)
        self.language_description_label.setWordWrap(True)
        text_layout.addWidget(self.language_title_label)
        text_layout.addWidget(self.language_description_label)
        layout.addLayout(icon_row)

        if self._localization_manager is not None:
            self.language_combo: ComboBox = ManifestLanguageComboBox(
                self._localization_manager,
                failure_presenter=self._show_language_failure,
                parent=page,
            )
            self._localization_manager.languageChanged.connect(
                lambda _snapshot: self._retranslate_language_page()
            )
        else:
            fallback_combo = ComboBox(page)
            for language in load_language_manifest().release_languages:
                fallback_combo.addItem(
                    language.native_display_name,
                    userData=language.identifier,
                )
            self.language_combo = fallback_combo
        self.language_combo.setObjectName("LauncherLanguageSelector")
        self.language_combo.setFixedWidth(420)
        self.language_combo.setAccessibleName(launcher_text("Application language"))
        layout.addSpacing(10)
        layout.addWidget(
            self.language_combo,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addStretch(1)
        self._retranslate_language_page()
        return page

    def _build_install_location_page(self) -> QFrame:
        """Build the single install-location decision without support prose."""

        page, layout = self._new_page("OnboardingPageFrame")
        icon_row, text_layout = self._hero_row(page, FIF.FOLDER)
        self.install_title_label = SubtitleLabel(page)
        self.install_title_label.setObjectName("OnboardingPageTitle")
        self.install_description_label = BodyLabel(page)
        self.install_description_label.setObjectName("OnboardingPageDescription")
        self.install_description_label.setWordWrap(True)
        text_layout.addWidget(self.install_title_label)
        text_layout.addWidget(self.install_description_label)
        layout.addLayout(icon_row)
        layout.addSpacing(10)

        self.install_field_label = CaptionLabel(page)
        self.install_field_label.setObjectName("OnboardingFieldLabel")
        layout.addWidget(self.install_field_label)
        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        self.install_path_edit.setParent(page)
        self.install_path_edit.setMinimumHeight(38)
        self.browse_button.setParent(page)
        self.browse_button.clicked.connect(self._choose_install_directory)
        path_row.addWidget(self.install_path_edit, 1)
        path_row.addWidget(self.browse_button)
        layout.addLayout(path_row)
        self.install_location_guidance_label.setParent(page)
        self.install_location_guidance_label.setWordWrap(True)
        self.install_location_guidance_label.setObjectName("OnboardingFieldHelper")
        layout.addWidget(self.install_location_guidance_label)
        layout.addStretch(1)
        self._retranslate_install_page()
        return page

    def _build_progress_page(self) -> QFrame:
        """Build a focused progress page with optional technical output."""

        page, layout = self._new_page("LauncherProgressPage")
        icon_row, text_layout = self._hero_row(page, FIF.SYNC)
        title = SubtitleLabel(launcher_text("Setting up SugarSubstitute"), page)
        title.setObjectName("OnboardingPageTitle")
        self.activity_label = BodyLabel(launcher_text("Getting things ready…"), page)
        self.activity_label.setObjectName("LauncherCurrentActivity")
        self.activity_label.setWordWrap(True)
        text_layout.addWidget(title)
        text_layout.addWidget(self.activity_label)
        layout.addLayout(icon_row)
        layout.addSpacing(12)

        progress = QProgressBar(page)
        progress.setObjectName("LauncherInstallProgress")
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedHeight(5)
        layout.addWidget(progress)
        self.details_button = PushButton(launcher_text("Show details"), page)
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._set_log_visible)
        layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.progress_log.setParent(page)
        self.progress_log.hide()
        layout.addWidget(self.progress_log)
        layout.addStretch(1)
        return page

    def _new_page(self, object_name: str) -> tuple[QFrame, QVBoxLayout]:
        """Create one centered page with the shared readable width."""

        page = QFrame(self.page_stack)
        page.setObjectName(object_name)
        page.setMinimumWidth(760)
        page.setMaximumWidth(INSTALLER_CONTENT_MAX_WIDTH)
        page.setProperty("installerContentWidth", INSTALLER_CONTENT_MAX_WIDTH)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        return page, layout

    @staticmethod
    def _hero_row(
        page: QWidget,
        icon: FIF,
        *,
        centered: bool = False,
    ) -> tuple[QHBoxLayout, QVBoxLayout]:
        """Create a compact icon-and-heading row for one launcher page."""

        row = QHBoxLayout()
        row.setSpacing(16)
        if centered:
            row.addStretch(1)
        badge = QFrame(page)
        badge.setObjectName("OnboardingHeroBadge")
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(11, 11, 11, 11)
        icon_widget = IconWidget(icon, badge)
        icon_widget.setFixedSize(24, 24)
        badge_layout.addWidget(icon_widget)
        row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)
        row.addLayout(text_layout, 0 if centered else 1)
        if centered:
            row.addStretch(1)
        return row, text_layout

    def _set_progress(self, current: int, total: int, title: str) -> None:
        """Update the persistent compact journey indicator."""

        description = launcher_text("Step %1 of %2 · %3", current, total, title)
        self.brand_bar.set_progress(
            current=current,
            total=total,
            description=description,
        )

    def _set_log_visible(self, visible: bool) -> None:
        """Toggle technical output without changing the primary flow."""

        self.progress_log.setVisible(visible)
        self.details_button.setText(
            launcher_text("Hide details") if visible else launcher_text("Show details")
        )

    def _retranslate_language_page(self) -> None:
        """Immediately preview the selected locale on the first page."""

        self.language_title_label.setText(launcher_text("Choose your language"))
        self.language_description_label.setText(
            launcher_text("SugarSubstitute will use this language during setup.")
        )
        if self._experience_page is ExperiencePage.LANGUAGE:
            self.set_primary_action(text=launcher_text("Continue"), enabled=True)
            self._set_progress(1, 5, launcher_text("Language"))

    def _retranslate_install_page(self) -> None:
        """Render install-location copy after the language choice is committed."""

        self.install_title_label.setText(
            launcher_text("Choose where Substitute should live")
        )
        self.install_description_label.setText(
            launcher_text("Pick a folder with room for the app, ComfyUI, and models.")
        )
        self.install_field_label.setText(launcher_text("Install folder"))
        self.browse_button.setText(launcher_text("Browse…"))
        self.install_location_guidance_label.setText(install_location_guidance())

    def _choose_install_directory(self) -> None:
        """Prompt the user for a writable install directory."""

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            launcher_text("Choose SugarSubstitute install directory"),
            self.install_path,
        )
        if selected_dir:
            self.install_path_edit.setText(selected_dir)

    def _show_language_failure(self, title: str, message: str) -> None:
        """Present a rare locale-switch failure without losing the current choice."""

        QMessageBox.critical(self, title, message)


__all__ = ["InstallerView"]
