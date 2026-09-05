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

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
    set_localized_text,
    set_localized_window_title,
)
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
    InstallerBrandBar,
    InstallerBodyMaterialSurface,
    build_installer_surface_style_sheet,
    configure_installer_title_bar,
    expose_native_material,
)
from substitute.presentation.localization import (
    LocalizedPrimaryPushButton,
    LocalizedPushButton,
)

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from substitute.application.onboarding import OnboardingProvisioningFailure
from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoverySnapshot,
    ComfyPreflightSnapshot,
)
from substitute.domain.onboarding import (
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
)
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
from substitute.presentation.onboarding.external_link_opener import (
    open_civitai_model_page,
)
from substitute.presentation.onboarding.comfy_environment_pages import (
    AttachedPythonChoicePage,
    AttachedPythonManualPage,
    AttachedPythonProcessPage,
    ComfyPreflightPage,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.model_onboarding_coordinator import (
    ModelOnboardingCoordinator,
)
from substitute.presentation.onboarding.model_onboarding_presenter import (
    ModelOnboardingPresenter,
)
from substitute.presentation.onboarding.onboarding_failure_presenter import (
    OnboardingFailurePresenter,
)
from substitute.presentation.onboarding.onboarding_existing_model_page import (
    ExistingModelsFolderQuestionPage,
)
from substitute.presentation.onboarding.onboarding_model_download_review_page import (
    ModelDownloadReviewPage,
)
from substitute.presentation.onboarding.onboarding_recommendation_pages import (
    ModelRecommendationPage,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
    initial_onboarding_page,
)
from substitute.presentation.onboarding.onboarding_shell_presentation import (
    PROGRESS_BY_PAGE,
    OnboardingIssuePanel,
)
from substitute.presentation.onboarding.onboarding_navigation_presentation import (
    onboarding_primary_button_label,
    onboarding_window_title,
)
from substitute.presentation.onboarding.onboarding_page_stage import (
    OnboardingPageStage,
)
from substitute.presentation.onboarding.onboarding_style_sheet import (
    build_onboarding_style_sheet,
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
from substitute.presentation.onboarding.path_selector import (
    DirectoryChooser,
    OnboardingPathSelector,
)
from substitute.presentation.onboarding.setup_progress_presenter import (
    SetupProgressPresenter,
)
from substitute.presentation.resources.app_icon import application_icon
from substitute.presentation.errors.error_presenter import (
    ErrorPresenter,
    ErrorReportPresenterProtocol,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from substitute.presentation.shell.window_attention import (
    request_window_attention_if_inactive,
)
from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.shared.logging.logger import get_logger, log_warning


_LOGGER = get_logger("presentation.onboarding.onboarding_window")


class OnboardingWindow(SubstituteWindowFrame):
    """Render a polished onboarding surface inside the shared Substitute shell."""

    launch_requested = Signal(object)
    close_requested = Signal()

    def __init__(
        self,
        *,
        controller: OnboardingController,
        environment_coordinator: ComfyEnvironmentCoordinator | None = None,
        model_coordinator: ModelOnboardingCoordinator | None = None,
        install_root_locked: bool = False,
        initial_geometry: tuple[int, int, int, int] | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        attention_requester: Callable[[QWidget], bool] | None = None,
        directory_chooser: DirectoryChooser | None = None,
        diagnostic_log_sink: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the onboarding shell and connect it to the controller."""

        super().__init__(
            parent,
            create_menu_container=False,
            backdrop_mode=ShellBackdropMode.MICA_ALT,
        )
        self._controller = controller
        self._environment_coordinator = environment_coordinator
        self._model_coordinator = model_coordinator
        self._attention_requester = (
            attention_requester or request_window_attention_if_inactive
        )
        self._diagnostic_log_sink = diagnostic_log_sink or (lambda _line: None)
        self._install_root_locked = install_root_locked
        self._initial_geometry = initial_geometry
        self._current_page = self._initial_page()
        self._provisioning_started = False
        self._last_completion: OnboardingCompletion | None = None
        self._attention_outcomes: set[str] = set()
        self._emit_close_requested_on_close = True
        self._drag_widgets: set[QWidget] = set()
        self._provisioning_output_stream = TerminalOutputStream(max_lines=2000)
        self._preflight_snapshot: ComfyPreflightSnapshot | None = None
        self._preflight_destination: OnboardingPageId | None = None
        self._recovery_snapshot: AttachedPythonRecoverySnapshot | None = None

        self.setObjectName("OnboardingWindow")
        window_title = onboarding_window_title(controller.flow_mode)
        set_localized_window_title(
            self,
            window_title.source_text,
            *window_title.arguments,
        )
        self.setWindowIcon(application_icon())
        self.setFixedSize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()
        configure_installer_title_bar(self.titleBar)

        self._build_ui()
        report_presenter = error_presenter or ErrorPresenter(
            parent=self,
            open_console=lambda: self.provisioning_page.set_log_expanded(True),
        )
        self._failure_presenter = OnboardingFailurePresenter(
            report_presenter=report_presenter,
            installation_root=self._controller.draft.installation_root,
        )
        self._path_selector = OnboardingPathSelector(
            parent=self,
            draft_provider=lambda: self._controller.draft,
            install_root_edit=self.install_root_page.install_root_edit,
            managed_workspace_edit=self.managed_local_page.workspace_edit,
            attached_workspace_edit=self.attached_local_page.workspace_edit,
            model_root_edit=self.folder_setup_page.managed_model_root_edit,
            output_root_edit=self.folder_setup_page.output_root_edit,
            validate_attached_python=self._validate_attached_python,
            directory_chooser=directory_chooser,
        )
        self._model_presenter = ModelOnboardingPresenter(
            controller=controller,
            session=controller.model_session,
            coordinator=model_coordinator,
            existing_folder_page=self.existing_models_question_page,
            folder_page=self.folder_setup_page,
            recommendation_page=self.model_recommendation_page,
            review_page=self.model_download_review_page,
            primary_button=self.primary_button,
            navigate=self._show_page,
            refresh_height=self.page_stage.schedule_current_page_height_refresh,
            open_model_page=open_civitai_model_page,
        )
        self.titleBar.raise_()
        self._install_drag_regions()
        self._apply_styles()
        connect_theme_refresh(self, self._apply_styles)
        self._connect_signals()
        self._apply_draft(controller.draft)
        self._render_issues()
        self._show_page(self._current_page)
        if self._install_root_locked:
            self._begin_preflight_gate(OnboardingPageId.TARGET_MODE)
        self._place_initial_window()

    def _build_ui(self) -> None:
        """Build the shared brand shell and dominant content area."""

        self.root_container = QWidget(self)
        self.root_container.setObjectName("OnboardingRoot")
        expose_native_material(self.root_container)

        root_layout = QVBoxLayout(self.root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.content_surface = QWidget(self.root_container)
        self.content_surface.setObjectName("OnboardingSurface")
        expose_native_material(self.content_surface)
        surface_layout = QVBoxLayout(self.content_surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        self.identity_rail = QFrame(self.content_surface)
        self.identity_rail.setObjectName("OnboardingIdentityRail")
        self.identity_rail.setFixedHeight(126)
        expose_native_material(self.identity_rail)
        rail_layout = QVBoxLayout(self.identity_rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(0)

        self.brand_bar = InstallerBrandBar(self.identity_rail)
        rail_layout.addWidget(self.brand_bar)

        self.content_panel = InstallerBodyMaterialSurface(
            object_name="OnboardingContentPanel",
            parent=self.content_surface,
        )
        content_layout = QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(38, 22, 38, 20)
        content_layout.setSpacing(14)
        self.issue_banner = OnboardingIssuePanel(self.content_panel)
        content_layout.addWidget(self.issue_banner)

        self.page_stage = OnboardingPageStage(self.content_panel)
        self.page_scroll_content = self.page_stage.scroll_content
        self.page_stack = self.page_stage.page_stack
        content_layout.addWidget(self.page_stage, 1)

        self.install_root_page = InstallRootPage(self.content_panel)
        self.comfy_preflight_page = ComfyPreflightPage(self.content_panel)
        self.target_mode_page = TargetModePage(self.content_panel)
        self.managed_local_page = ManagedLocalPage(self.content_panel)
        self.attached_local_page = AttachedLocalPage(self.content_panel)
        self.attached_python_choice_page = AttachedPythonChoicePage(self.content_panel)
        self.attached_python_process_page = AttachedPythonProcessPage(
            self.content_panel
        )
        self.attached_python_manual_page = AttachedPythonManualPage(self.content_panel)
        self.remote_page = RemotePage(self.content_panel)
        self.existing_models_question_page = ExistingModelsFolderQuestionPage(
            self.content_panel
        )
        self.folder_setup_page = FolderSetupPage(self.content_panel)
        self.model_recommendation_page = ModelRecommendationPage(self.content_panel)
        self.model_download_review_page = ModelDownloadReviewPage(self.content_panel)
        self.integrations_page = IntegrationsPage(self.content_panel)
        self.provisioning_page = ProvisioningPage(self.content_panel)
        self.provisioning_page.set_output_stream(self._provisioning_output_stream)
        self._setup_progress_presenter = SetupProgressPresenter(self.provisioning_page)
        self.completion_page = CompletionPage(self.content_panel)
        self._pages = {
            OnboardingPageId.WELCOME: self.install_root_page,
            OnboardingPageId.COMFY_PREFLIGHT: self.comfy_preflight_page,
            OnboardingPageId.TARGET_MODE: self.target_mode_page,
            OnboardingPageId.MANAGED_LOCAL: self.managed_local_page,
            OnboardingPageId.ATTACHED_LOCAL: self.attached_local_page,
            OnboardingPageId.ATTACHED_PYTHON_CHOICE: self.attached_python_choice_page,
            OnboardingPageId.ATTACHED_PYTHON_PROCESS: self.attached_python_process_page,
            OnboardingPageId.ATTACHED_PYTHON_MANUAL: self.attached_python_manual_page,
            OnboardingPageId.REMOTE: self.remote_page,
            OnboardingPageId.EXISTING_MODELS: self.existing_models_question_page,
            OnboardingPageId.FOLDERS: self.folder_setup_page,
            OnboardingPageId.MODEL_RECOMMENDATIONS: self.model_recommendation_page,
            OnboardingPageId.MODEL_DOWNLOAD_REVIEW: self.model_download_review_page,
            OnboardingPageId.INTEGRATIONS: self.integrations_page,
            OnboardingPageId.PROVISIONING: self.provisioning_page,
            OnboardingPageId.COMPLETION: self.completion_page,
        }
        for page in self._pages.values():
            self.page_stage.add_page(page)
        self.comfy_preflight_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.managed_local_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.attached_local_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.attached_python_process_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.attached_python_manual_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.provisioning_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.completion_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )
        self.integrations_page.content_height_changed.connect(
            self.page_stage.schedule_current_page_height_refresh
        )

        self.footer_row = QFrame(self.content_panel)
        self.footer_row.setObjectName("OnboardingFooterRow")
        footer_layout = QHBoxLayout(self.footer_row)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)

        self.back_button = LocalizedPushButton(app_text("Back"), self.footer_row)
        self.back_button.setObjectName("OnboardingBackButton")
        self.route_switch_button = LocalizedPushButton("", self.footer_row)
        self.route_switch_button.setObjectName("OnboardingRouteSwitchButton")
        self.route_switch_button.hide()
        self.no_models_button = LocalizedPushButton(
            app_text("No, show recommendations"), self.footer_row
        )
        self.no_models_button.setObjectName("OnboardingNoExistingModelsButton")
        self.no_models_button.hide()
        self.yes_models_button = LocalizedPrimaryPushButton(
            app_text("Yes, choose folder"), self.footer_row
        )
        self.yes_models_button.setObjectName("OnboardingYesExistingModelsButton")
        self.yes_models_button.hide()
        self.primary_button = LocalizedPrimaryPushButton(
            app_text("Continue"), self.footer_row
        )
        self.primary_button.setObjectName("OnboardingPrimaryButton")
        self.back_button.setMinimumWidth(76)
        self.primary_button.setMinimumWidth(164)
        footer_layout.addWidget(self.back_button)
        footer_layout.addWidget(self.route_switch_button)
        footer_layout.addWidget(self.no_models_button)
        footer_layout.addWidget(self.yes_models_button)
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

        self.root_container.setStyleSheet(
            build_onboarding_style_sheet() + build_installer_surface_style_sheet()
        )

    def _connect_signals(self) -> None:
        """Connect page actions, navigation buttons, and controller signals."""

        paths = self._path_selector
        self.install_root_page.browse_requested.connect(paths.browse_install_root)
        self.managed_local_page.browse_requested.connect(paths.browse_managed_workspace)
        self.attached_local_page.browse_requested.connect(
            paths.browse_attached_workspace
        )
        self.comfy_preflight_page.close_requested.connect(
            self._close_observed_comfy_processes
        )
        self.attached_python_choice_page.process_detection_requested.connect(
            lambda: self._show_page(OnboardingPageId.ATTACHED_PYTHON_PROCESS)
        )
        self.attached_python_choice_page.manual_selection_requested.connect(
            lambda: self._show_page(OnboardingPageId.ATTACHED_PYTHON_MANUAL)
        )
        self.attached_python_manual_page.browse_requested.connect(
            paths.browse_attached_python
        )
        self.attached_python_process_page.close_requested.connect(
            self._close_observed_comfy_processes
        )
        self.attached_python_manual_page.close_requested.connect(
            self._close_observed_comfy_processes
        )
        self.folder_setup_page.managed_model_browse_requested.connect(
            self._browse_model_root
        )
        self.folder_setup_page.output_browse_requested.connect(paths.browse_output_root)
        self.folder_setup_page.managed_model_default_requested.connect(
            paths.use_default_model_root
        )
        self.folder_setup_page.output_default_requested.connect(
            paths.use_default_output_root
        )
        self.back_button.clicked.connect(self._go_back)
        self.route_switch_button.clicked.connect(self._switch_attached_python_route)
        self.no_models_button.clicked.connect(
            lambda: self._model_presenter.choose_existing_folder(False)
        )
        self.yes_models_button.clicked.connect(
            lambda: self._model_presenter.choose_existing_folder(True)
        )
        self.primary_button.clicked.connect(self._advance)
        self._controller.draft_changed.connect(self._apply_draft)
        self._controller.provisioning_started.connect(self._handle_provisioning_started)
        self._controller.provisioning_finished.connect(
            self._handle_provisioning_finished
        )
        self._controller.progress_status_changed.connect(self._handle_progress_status)
        self._controller.progress_log_emitted.connect(self._handle_progress_log)
        setup_progress_signal = getattr(
            self._controller, "setup_progress_changed", None
        )
        if setup_progress_signal is not None:
            setup_progress_signal.connect(self._handle_setup_progress)
        self._controller.failure_reported.connect(self._handle_failure)
        self._controller.completion_ready.connect(self._handle_completion)
        coordinator = self._environment_coordinator
        if coordinator is not None:
            coordinator.preflight_changed.connect(self._handle_preflight_snapshot)
            coordinator.discovery_finished.connect(
                self._handle_attached_python_discovery
            )
            coordinator.recovery_changed.connect(self._handle_recovery_snapshot)
            coordinator.browse_finished.connect(self._handle_browsed_python_probe)
            coordinator.termination_finished.connect(self._handle_process_termination)
            coordinator.task_failed.connect(self._handle_environment_task_failure)

    def _advance(self) -> None:
        """Advance the onboarding flow for the current page."""

        if self._current_page in {
            OnboardingPageId.EXISTING_MODELS,
            OnboardingPageId.MODEL_RECOMMENDATIONS,
            OnboardingPageId.MODEL_DOWNLOAD_REVIEW,
        }:
            self._model_presenter.advance(self._current_page)
            return

        if self._current_page is OnboardingPageId.WELCOME:
            install_root = Path(
                self.install_root_page.install_root_edit.text()
            ).resolve()
            self._controller.set_installation_root(install_root)
            self._begin_preflight_gate(OnboardingPageId.TARGET_MODE)
            return
        elif self._current_page is OnboardingPageId.COMFY_PREFLIGHT:
            if self._preflight_snapshot is None:
                return
            if not self._preflight_snapshot.can_continue:
                return
            destination = self._preflight_destination or OnboardingPageId.TARGET_MODE
            self._preflight_destination = None
            self._show_page(destination)
            return
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
            self._controller.start_background_preparation()
        elif self._current_page is OnboardingPageId.ATTACHED_LOCAL:
            attached_host = self.attached_local_page.host_edit.text()
            attached_port = self.attached_local_page.port_spinbox.value()
            workspace_text = self.attached_local_page.workspace_edit.text().strip()
            self._controller.update_endpoint(
                attached_host,
                attached_port,
            )
            self._controller.update_attached_workspace(
                Path(workspace_text).resolve() if workspace_text else None
            )
            workspace = self._controller.draft.attached_workspace_path
            if workspace is None:
                self._show_page(OnboardingPageId.ATTACHED_PYTHON_CHOICE)
                return
            coordinator = self._environment_coordinator
            if coordinator is None:
                self._show_page(OnboardingPageId.ATTACHED_PYTHON_CHOICE)
                return
            self.primary_button.setEnabled(False)
            set_localized_text(self.primary_button, "Finding Python…")
            coordinator.discover_attached_python(workspace)
            return
        elif self._current_page is OnboardingPageId.ATTACHED_PYTHON_CHOICE:
            return
        elif self._current_page in {
            OnboardingPageId.ATTACHED_PYTHON_PROCESS,
            OnboardingPageId.ATTACHED_PYTHON_MANUAL,
        }:
            snapshot = self._recovery_snapshot
            if snapshot is None or not snapshot.can_continue:
                return
            self._controller.update_attached_python_binding(snapshot.binding)
            self._controller.start_background_preparation()
            destination = self._controller.next_page(self._current_page)
            if destination is self._current_page:
                destination = OnboardingPageId.FOLDERS
            self._show_page(destination)
            return
        elif self._current_page is OnboardingPageId.REMOTE:
            remote_host = self.remote_page.host_edit.text()
            remote_port = self.remote_page.port_spinbox.value()
            self._controller.update_endpoint(
                remote_host,
                remote_port,
            )
        elif self._current_page is OnboardingPageId.FOLDERS:
            self._controller.update_folder_preferences(
                managed_model_root=self._path_selector.selected_model_root(),
                managed_model_root_uses_default=(
                    self._path_selector.selected_model_root()
                    == self._path_selector.default_model_root()
                ),
                output_root=self._path_selector.selected_output_root(),
                output_root_uses_default=(
                    self._path_selector.selected_output_root()
                    == self._path_selector.default_output_root()
                ),
            )
            if self._model_presenter.advance(self._current_page):
                return
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

        if self._model_presenter.go_back(self._current_page):
            return

        previous_page = self._controller.previous_page(self._current_page)
        if self._install_root_locked and previous_page is OnboardingPageId.WELCOME:
            return
        self._show_page(previous_page)

    def _begin_preflight_gate(self, destination: OnboardingPageId) -> None:
        """Check for running ComfyUI without exposing a successful check as a page."""

        self._preflight_destination = destination
        self._preflight_snapshot = None
        coordinator = self._environment_coordinator
        if coordinator is None:
            self._preflight_destination = None
            self._show_page(destination)
            return
        set_localized_text(self.primary_button, "Checking ComfyUI…")
        self.primary_button.setEnabled(False)
        coordinator.start_preflight()

    def _switch_attached_python_route(self) -> None:
        """Switch directly between the two guided Python recovery routes."""

        if self._current_page is OnboardingPageId.ATTACHED_PYTHON_PROCESS:
            self._show_page(OnboardingPageId.ATTACHED_PYTHON_MANUAL)
            return
        if self._current_page is OnboardingPageId.ATTACHED_PYTHON_MANUAL:
            self._show_page(OnboardingPageId.ATTACHED_PYTHON_PROCESS)

    def _show_route_switch(self, label: ApplicationText) -> None:
        """Place a recovery-route alternative in the window footer."""

        apply_application_text(self.route_switch_button, label)
        self.route_switch_button.adjustSize()
        self.route_switch_button.show()

    def _show_page(self, page_id: OnboardingPageId) -> None:
        """Display one page and update navigation state for it."""

        if self._install_root_locked and page_id is OnboardingPageId.WELCOME:
            page_id = OnboardingPageId.TARGET_MODE
        if self._last_completion and page_id is OnboardingPageId.PROVISIONING:
            page_id = OnboardingPageId.COMPLETION
        coordinator = self._environment_coordinator
        if coordinator is not None:
            coordinator.stop_monitoring()
        self._current_page = page_id
        self.page_stage.show_page(self._pages[page_id])
        self._update_progress(page_id)

        self.back_button.setEnabled(
            page_id is not OnboardingPageId.WELCOME
            and not (
                self._install_root_locked
                and page_id
                in {
                    OnboardingPageId.COMFY_PREFLIGHT,
                    OnboardingPageId.TARGET_MODE,
                }
            )
        )
        self.route_switch_button.hide()
        self.no_models_button.hide()
        self.yes_models_button.hide()
        self.primary_button.show()
        self.primary_button.setEnabled(True)

        if page_id is OnboardingPageId.EXISTING_MODELS:
            self.primary_button.hide()
            self.no_models_button.show()
            self.yes_models_button.show()
            self._model_presenter.prepare_page(page_id)
            return

        if page_id is OnboardingPageId.COMFY_PREFLIGHT:
            self._preflight_snapshot = None
            self.comfy_preflight_page.show_checking()
            set_localized_text(self.primary_button, "Checking…")
            self.primary_button.setEnabled(False)
            if coordinator is not None:
                coordinator.start_preflight()
            return

        if page_id is OnboardingPageId.ATTACHED_PYTHON_CHOICE:
            self._recovery_snapshot = None
            self.primary_button.hide()
            return

        if page_id is OnboardingPageId.ATTACHED_PYTHON_PROCESS:
            self._recovery_snapshot = None
            self.attached_python_process_page.reset()
            self._show_route_switch(app_text("Select Python manually instead"))
            self.primary_button.hide()
            self._start_attached_python_recovery()
            return

        if page_id is OnboardingPageId.ATTACHED_PYTHON_MANUAL:
            self._recovery_snapshot = None
            self.attached_python_manual_page.reset()
            self._show_route_switch(app_text("Detect from running ComfyUI instead"))
            self.primary_button.hide()
            return

        if page_id is OnboardingPageId.PROVISIONING:
            self.back_button.setEnabled(False)
            self.primary_button.setEnabled(False)
            set_localized_text(self.primary_button, "Working...")
            self.primary_button.adjustSize()
            if not self._provisioning_started:
                self._provisioning_started = True
                self.provisioning_page.clear_details()
                self.provisioning_page.reset_progress()
                self.page_stage.refresh_current_page_height()
                self._controller.start_provisioning()
            return

        if page_id is OnboardingPageId.COMPLETION and self._last_completion is not None:
            self.back_button.hide()
            set_localized_text(
                self.primary_button,
                (
                    "Close"
                    if self._last_completion.restart_required
                    else "Open Substitute"
                ),
            )
            self.primary_button.adjustSize()
            return

        apply_application_text(
            self.primary_button,
            onboarding_primary_button_label(page_id),
        )
        self.primary_button.adjustSize()
        self._model_presenter.prepare_page(page_id)

    def _update_progress(self, page_id: OnboardingPageId) -> None:
        """Refresh the persistent brand progress for the current page."""

        progress = PROGRESS_BY_PAGE[page_id]
        journey_step = progress.step_number + 1
        journey_step_count = progress.step_count + 1
        self.brand_bar.set_progress(
            current=journey_step,
            total=journey_step_count,
            description=render_application_text(
                app_text(
                    "Step %1 of %2 · %3",
                    journey_step,
                    journey_step_count,
                    render_application_text(progress.title),
                )
            ),
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
        self.remote_page.host_edit.setText(draft.endpoint_host)
        self.remote_page.port_spinbox.setValue(draft.endpoint_port)
        if not self._controller.model_session.enabled:
            self.folder_setup_page.set_managed_model_visible(
                draft.target_mode is not OnboardingTargetMode.REMOTE
            )
        self.folder_setup_page.managed_model_root_edit.setText(
            str(draft.managed_model_root or self._path_selector.default_model_root())
        )
        self.folder_setup_page.output_root_edit.setText(
            str(draft.output_root or self._path_selector.default_output_root())
        )
        for path_edit in (
            self.install_root_page.install_root_edit,
            self.managed_local_page.workspace_edit,
            self.attached_local_page.workspace_edit,
            self.folder_setup_page.managed_model_root_edit,
            self.folder_setup_page.output_root_edit,
        ):
            path_edit.setCursorPosition(0)
            path_edit.deselect()
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
            body = app_text(
                "%1 saved setup items need repair before Substitute can open.",
                len(issues),
            )
            detail = "\n".join(
                f"- {issue.technical_detail}"
                for issue in issues
                if issue.technical_detail
            )
            self.issue_banner.set_issue_content(
                title=app_text("Setup needs attention"),
                body=body,
                detail=detail,
            )
        self.issue_banner.show()

    def _handle_provisioning_started(self) -> None:
        """Switch the provisioning page into its active state."""

        self._attention_outcomes.discard("failure")
        self._setup_progress_presenter.begin()
        set_localized_text(self.provisioning_page.status_label, "Starting setup.")
        self.provisioning_page.clear_details()

    def _handle_setup_progress(self, event: object) -> None:
        """Project one typed setup event into honest task and byte progress."""

        self._setup_progress_presenter.accept(event)

    def _handle_progress_status(self, message: ApplicationText) -> None:
        """Render one semantic provisioning status in the active locale."""

        apply_application_text(self.provisioning_page.status_label, message)

    def _handle_progress_log(self, message: ApplicationText) -> None:
        """Append one provisioning transcript line in the active locale."""

        line = render_application_text(message)
        self._provisioning_output_stream.append_line(line)
        self._diagnostic_log_sink(line)

    def _handle_provisioning_finished(self) -> None:
        """Route successful setup to completion or expose retry after failure."""

        if self._last_completion is not None:
            self.provisioning_page.mark_complete()
            self._show_page(OnboardingPageId.COMPLETION)
            return
        self.back_button.setEnabled(True)
        self.primary_button.setEnabled(True)
        set_localized_text(self.primary_button, "Try again")
        self.primary_button.adjustSize()

    def _handle_failure(self, failure: object) -> None:
        """Render a provisioning failure inside the provisioning page."""

        self.provisioning_page.mark_failed()
        typed_failure = (
            failure
            if isinstance(failure, OnboardingProvisioningFailure)
            else OnboardingProvisioningFailure(
                headline=app_text("Setup needs attention."),
                user_message=app_text(
                    "Review the details below, fix the reported issue, and try again."
                ),
                technical_detail=str(failure),
                remediation_steps=(),
            )
        )
        apply_application_text(
            self.provisioning_page.status_label,
            typed_failure.headline,
        )
        self.provisioning_page.set_failure_guidance(
            user_message=typed_failure.user_message,
            steps=typed_failure.remediation_steps,
        )
        self.provisioning_page.append_log(typed_failure.technical_detail)
        self._provisioning_started = False
        first_visible_failure = self._request_attention_once("failure")
        if first_visible_failure:
            self._failure_presenter.present(
                typed_failure,
                log_tail=(
                    self.provisioning_page.details_surface.log_view.toPlainText()[
                        -8000:
                    ]
                ),
            )

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
        self._request_attention_once("completion")
        if typed_completion.restart_required:
            summary = app_text(
                "Your updated setup has been saved. Close Substitute now, then open it again to use the new configuration."
            )
        else:
            summary = app_text("Your setup is saved and ready to use.")
        apply_application_text(self.completion_page.summary_label, summary)
        self.completion_page.command_label.setText(
            " ".join(typed_completion.launch_command)
        )
        self.primary_button.setEnabled(True)
        self.primary_button.adjustSize()
        if self._current_page is OnboardingPageId.PROVISIONING:
            self.provisioning_page.mark_complete()
            self._show_page(OnboardingPageId.COMPLETION)

    def _request_attention_once(self, outcome: str) -> bool:
        """Request visible-window attention once and report whether it was new."""

        if not self.isVisible() or outcome in self._attention_outcomes:
            return False
        self._attention_outcomes.add(outcome)
        self._attention_requester(self)
        return True

    def _handle_preflight_snapshot(self, result: object) -> None:
        """Apply one live running-Comfy preflight observation."""

        if not isinstance(result, ComfyPreflightSnapshot):
            return
        if self._current_page is OnboardingPageId.COMFY_PREFLIGHT:
            self._preflight_snapshot = result
            self.comfy_preflight_page.apply_snapshot(result)
            set_localized_text(self.primary_button, "Continue")
            self.primary_button.setEnabled(result.can_continue)
            return
        destination = self._preflight_destination
        if destination is None:
            return
        if result.can_continue:
            self._preflight_destination = None
            self._show_page(destination)
            return
        self._show_page(OnboardingPageId.COMFY_PREFLIGHT)
        self._preflight_snapshot = result
        self.comfy_preflight_page.apply_snapshot(result)
        set_localized_text(self.primary_button, "Continue")
        self.primary_button.setEnabled(False)

    def _handle_attached_python_discovery(self, result: object) -> None:
        """Route silent Python discovery to normal flow or conditional recovery."""

        if not isinstance(result, ComfyPythonDiscoveryResult):
            return
        if self._current_page is not OnboardingPageId.ATTACHED_LOCAL:
            return
        if result.binding is not None:
            self._controller.update_attached_python_binding(result.binding)
            self._controller.start_background_preparation()
            destination = self._controller.next_page(OnboardingPageId.ATTACHED_LOCAL)
            if destination is OnboardingPageId.ATTACHED_LOCAL:
                destination = OnboardingPageId.FOLDERS
            self._show_page(destination)
            return
        self._show_page(OnboardingPageId.ATTACHED_PYTHON_CHOICE)

    def _start_attached_python_recovery(self) -> None:
        """Begin live process observation for the selected attached workspace."""

        workspace = self._controller.draft.attached_workspace_path
        coordinator = self._environment_coordinator
        if workspace is None or coordinator is None:
            return
        self._recovery_snapshot = None
        self.primary_button.setEnabled(False)
        coordinator.start_attached_recovery(
            workspace=workspace,
            binding=self._controller.draft.attached_python_binding,
        )

    def _handle_recovery_snapshot(self, result: object) -> None:
        """Apply one responsive launch-and-observe recovery state."""

        if not isinstance(result, AttachedPythonRecoverySnapshot):
            return
        if self._current_page not in {
            OnboardingPageId.ATTACHED_PYTHON_PROCESS,
            OnboardingPageId.ATTACHED_PYTHON_MANUAL,
        }:
            return
        self._recovery_snapshot = result
        if result.binding is not None:
            self._controller.update_attached_python_binding(result.binding)
        if self._current_page is OnboardingPageId.ATTACHED_PYTHON_PROCESS:
            self.attached_python_process_page.apply_snapshot(result)
        else:
            self.attached_python_manual_page.apply_snapshot(result)
        set_localized_text(self.primary_button, "Continue")
        self.primary_button.setVisible(result.can_continue)
        self.primary_button.setEnabled(result.can_continue)
        self.route_switch_button.setVisible(result.binding is None)

    def _handle_browsed_python_probe(self, result: object) -> None:
        """Continue monitoring after validating a recovery-only Browse selection."""

        if not isinstance(result, ComfyPythonProbeResult):
            return
        if self._current_page is not OnboardingPageId.ATTACHED_PYTHON_MANUAL:
            return
        if result.binding is None:
            self.attached_python_manual_page.show_validation_failure(
                result.failure
                or app_text("The selected Python executable could not be validated.")
            )
            self.primary_button.hide()
            self.route_switch_button.show()
            return
        self._controller.update_attached_python_binding(result.binding)
        workspace = self._controller.draft.attached_workspace_path
        coordinator = self._environment_coordinator
        if workspace is None or coordinator is None:
            return
        coordinator.start_attached_recovery(
            workspace=workspace,
            binding=result.binding,
        )

    def _close_observed_comfy_processes(self) -> None:
        """Request conservative shutdown of the latest verified process snapshot."""

        coordinator = self._environment_coordinator
        if coordinator is None:
            return
        self.comfy_preflight_page.close_button.setEnabled(False)
        self.attached_python_process_page.close_button.setEnabled(False)
        self.attached_python_manual_page.close_button.setEnabled(False)
        coordinator.close_observed_processes()

    def _handle_process_termination(self, _result: object) -> None:
        """Restore shutdown controls while live monitoring confirms process exit."""

        self.comfy_preflight_page.close_button.setEnabled(True)
        self.attached_python_process_page.close_button.setEnabled(True)
        self.attached_python_manual_page.close_button.setEnabled(True)

    def _handle_environment_task_failure(self, detail: str) -> None:
        """Render an actionable environment observation failure without advancing."""

        self.primary_button.setEnabled(False)
        if (
            self._preflight_destination is not None
            and self._current_page is not OnboardingPageId.COMFY_PREFLIGHT
        ):
            self._show_page(OnboardingPageId.COMFY_PREFLIGHT)
        if self._current_page is OnboardingPageId.COMFY_PREFLIGHT:
            set_localized_text(
                self.comfy_preflight_page.status_label,
                "ComfyUI could not be checked yet: %1",
                detail,
            )
            return
        if self._current_page is OnboardingPageId.ATTACHED_PYTHON_PROCESS:
            self.attached_python_process_page.show_failure(detail)
            return
        if self._current_page is OnboardingPageId.ATTACHED_PYTHON_MANUAL:
            self.attached_python_manual_page.show_validation_failure(detail)

    def _validate_attached_python(self, executable: Path) -> None:
        """Present and start validation for a browsed attached Python executable."""

        workspace = self._controller.draft.attached_workspace_path
        coordinator = self._environment_coordinator
        if workspace is None or coordinator is None:
            return
        self.primary_button.hide()
        self.attached_python_manual_page.show_validation_started(executable)
        coordinator.validate_browsed_python(
            workspace=workspace,
            executable=executable,
        )

    def _browse_model_root(self) -> None:
        """Choose an existing models folder and publish confirmation state."""

        selected = self._path_selector.browse_model_root()
        self._model_presenter.confirm_existing_folder_path(selected)

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

        if self._environment_coordinator is not None:
            self._environment_coordinator.shutdown()
        if self._model_coordinator is not None:
            self._model_coordinator.shutdown()
        if self._emit_close_requested_on_close:
            self.close_requested.emit()
        event.accept()
        super().closeEvent(event)
