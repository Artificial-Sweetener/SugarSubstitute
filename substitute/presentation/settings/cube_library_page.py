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

"""Render active-target Cube Library settings and pack management."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.localization import LocalizedSwitchButton

from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
    set_localized_placeholder,
    set_localized_text,
    set_localized_tooltip,
)
from substitute.presentation.localization import (
    LocalizedPushButton,
    LocalizedStrongBodyLabel,
)

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon,
    IconWidget,
    IndicatorPosition,
    LineEdit,
    TransparentToolButton,
)

from substitute.application.cube_library import (
    CubeDependencyRepairProposal,
    CubeLibraryManagementService,
    CubeLibrarySnapshot,
    CubePackPreflight,
    CubePackRecord,
)
from substitute.application.cube_library.settings_projection import (
    CubePackDetailView,
    CubePackRowView,
    project_library_status,
    project_pack,
    project_readiness,
)
from substitute.application.errors import SubstituteOperationContext
from substitute.presentation.errors import (
    ErrorPresenter,
    ErrorReportPresenterProtocol,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    SettingsCard,
)
from substitute.presentation.settings.settings_expander import (
    SettingsExpander,
    SettingsExpanderRow,
)
from substitute.presentation.settings.settings_infobar import (
    SettingsInfoBar,
    SettingsInfoBarSeverity,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_style import SETTINGS_CARD_GROUP_SPACING
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.settings.cube_library_page")
_MAIN_BRANCH = "main"
_NO_PENDING_SNAPSHOT = object()


@dataclass(frozen=True)
class GitHubCubePackCandidate:
    """Describe a Cube Pack GitHub URL parsed for target operations."""

    owner: str
    repo: str

    @property
    def repo_ref(self) -> str:
        """Return the GitHub owner/repository reference."""

        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class CubeLibraryOperationResult:
    """Describe a completed Cube Library operation for UI rendering."""

    operation: str
    success: bool
    severity: SettingsInfoBarSeverity
    title: ApplicationText
    message: ApplicationText
    payload: object | None = None
    owner: str = ""
    repo: str = ""
    branch: str = ""
    error: BaseException | None = None


class ComfyRestartService(Protocol):
    """Describe the restart operation Cube Library can request after repair."""

    def restart_comfy(self) -> object | None:
        """Request a Comfy restart through the active target."""


class CubeLibrarySettingsPage(QWidget):
    """Display Cube Library status and manage target Cube Packs."""

    snapshot_loaded = Signal(object)
    operation_finished = Signal(object)

    def __init__(
        self,
        service: CubeLibraryManagementService,
        *,
        restart_service: ComfyRestartService | None = None,
        restart_required_changed: Callable[[bool], None] | None = None,
        post_restart_refresh: Callable[[], None] | None = None,
        catalog_invalidated: Callable[[], None] | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        parent: QWidget | None = None,
        task_runner_factory: SettingsAsyncTaskRunnerFactory,
    ) -> None:
        """Build the Cube Library Settings page."""

        super().__init__(parent)
        self._service = service
        self._restart_service = restart_service
        self._restart_required_changed = restart_required_changed
        self._post_restart_refresh = post_restart_refresh
        self._catalog_invalidated = catalog_invalidated
        self._error_presenter = error_presenter
        self._packs: tuple[CubePackRecord, ...] = ()
        self._dependency_repair_proposal: CubeDependencyRepairProposal | None = None
        self._cube_paths_by_pack: dict[str, tuple[str, ...]] = {}
        self._pack_expanders: dict[str, SettingsExpander] = {}
        self._settings_page_active = False
        self._refresh_generation = 0
        self._refresh_in_flight = False
        self._pending_snapshot_payload: object = _NO_PENDING_SNAPSHOT
        self._restart_required_after_repair = False
        self._task_runner = task_runner_factory(
            self,
            owner_id="cube_library_settings",
        )
        self._build_layout()
        self.snapshot_loaded.connect(self._apply_snapshot)
        self.operation_finished.connect(self._apply_operation_result)

    def set_settings_page_active(self, active: bool) -> None:
        """Apply Settings route/page visibility and render any pending snapshot."""

        self._settings_page_active = active
        if not active or self._pending_snapshot_payload is _NO_PENDING_SNAPSHOT:
            return
        payload = self._pending_snapshot_payload
        self._pending_snapshot_payload = _NO_PENDING_SNAPSHOT
        self._apply_snapshot(payload)

    def refresh(self) -> None:
        """Refresh target Cube Library state without blocking the UI thread."""

        if self._refresh_in_flight:
            return
        self._refresh_generation += 1
        generation = self._refresh_generation
        self._refresh_in_flight = True
        self.refresh_button.setEnabled(False)
        self._run_background(
            task_id="cube_library_refresh",
            operation=lambda: self._load_snapshot(generation),
        )

    def rendered_pack_refs(self) -> tuple[str, ...]:
        """Return pack refs currently displayed for tests."""

        return tuple(pack.repo_ref for pack in self._packs)

    def _build_layout(self) -> None:
        """Create Cube Library settings sections."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        self.status_row = self._build_status_row()
        self.notification_bar = SettingsInfoBar(self)
        self.add_pack_expander = self._build_add_pack_expander()
        self.pack_section = self._build_pack_list_section()
        self.readiness_section = self._build_readiness_section()
        layout.addWidget(self.status_row)
        layout.addWidget(self.notification_bar)
        layout.addWidget(self.add_pack_expander)
        layout.addWidget(self.pack_section)
        layout.addWidget(self.readiness_section)
        layout.addStretch(1)

    def _build_status_row(self) -> SettingsCard:
        """Create target status row."""

        self.refresh_button = TransparentToolButton(FluentIcon.SYNC, self)
        set_localized_tooltip(self.refresh_button, "Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.sync_all_button = LocalizedPushButton(app_text("Sync all"), self)
        self.sync_all_button.clicked.connect(self._request_sync_all)
        return SettingsCard(
            visual_widget=_icon_widget(self, AppIcon.LIBRARY_20_REGULAR),
            title=app_text("Cube Library"),
            description=app_text("Loading active target Cube Library state."),
            trailing_widget=_control_row(
                self,
                self.refresh_button,
                self.sync_all_button,
            ),
            reserve_visual_space=True,
            parent=self,
        )

    def _build_add_pack_expander(self) -> SettingsExpander:
        """Create the URL-only add-pack row."""

        self.github_url_edit = LineEdit(self)
        set_localized_placeholder(
            self.github_url_edit, "https://github.com/owner/repository"
        )
        self.github_url_edit.setMinimumWidth(260)
        self.add_button = LocalizedPushButton(app_text("Add"), self)
        self.add_button.clicked.connect(self._request_add_pack)
        self.github_url_edit.textChanged.connect(self._sync_add_pack_actions)
        controls = _control_row(self, self.github_url_edit, self.add_button)
        expander = SettingsExpander(
            title=app_text("Add Cube Pack"),
            description=app_text(
                "Paste a GitHub URL. Substitute validates and syncs the pack."
            ),
            visual_widget=_icon_widget(self, AppIcon.LINK_ADD_20_REGULAR),
            trailing_widget=controls,
            content_available=False,
            expanded=False,
            parent=self,
        )
        self.validation_result_row = SettingsExpanderRow(
            title=app_text("Validation result"),
            description=app_text("No repository has been validated."),
            parent=expander.content_widget(),
        )
        self.validation_result_row.hide()
        expander.add_widget(self.validation_result_row)
        self._sync_add_pack_actions()
        return expander

    def _build_pack_list_section(self) -> QWidget:
        """Create the tracked pack list section."""

        section = QWidget(self)
        section.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        section.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        self.pack_section_title = LocalizedStrongBodyLabel(
            app_text("Tracked Cube Packs"), section
        )
        self.pack_list = QWidget(section)
        self.pack_list.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.pack_list.setStyleSheet("background-color: transparent; border: none;")
        self.pack_list_layout = QVBoxLayout(self.pack_list)
        self.pack_list_layout.setContentsMargins(0, 0, 0, 0)
        self.pack_list_layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        layout.addWidget(self.pack_section_title)
        layout.addWidget(self.pack_list)
        return section

    def _build_readiness_section(self) -> QWidget:
        """Create the readiness section container."""

        section = QWidget(self)
        section.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        section.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        self.readiness_container = QWidget(section)
        self.readiness_container.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.readiness_container.setStyleSheet(
            "background-color: transparent; border: none;"
        )
        self.readiness_layout = QVBoxLayout(self.readiness_container)
        self.readiness_layout.setContentsMargins(0, 0, 0, 0)
        self.readiness_layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        layout.addWidget(self.readiness_container)
        return section

    def _load_snapshot(self, generation: int) -> None:
        """Load snapshot through the settings task route."""

        try:
            snapshot = self._service.load_snapshot()
            self.snapshot_loaded.emit((generation, snapshot))
        except Exception as error:
            log_exception(_LOGGER, "Failed to load Cube Library snapshot", error=error)
            self.snapshot_loaded.emit((generation, None))

    def _run_background(
        self,
        *,
        task_id: str,
        operation: Callable[[], object],
    ) -> None:
        """Run one Cube Library operation through the settings execution lane."""

        self._task_runner.run(
            task_id=task_id,
            generation=self._refresh_generation,
            operation=operation,
            context={"page": "cube_library"},
        )

    def _apply_snapshot(self, snapshot: object) -> None:
        """Render one Cube Library snapshot."""

        generation = self._refresh_generation
        has_generation = False
        if (
            isinstance(snapshot, tuple)
            and len(snapshot) == 2
            and isinstance(snapshot[0], int)
        ):
            has_generation = True
            generation = snapshot[0]
            snapshot = snapshot[1]
        if has_generation and generation != self._refresh_generation:
            return
        self._refresh_in_flight = False
        if has_generation and not self._settings_page_active and not self.isVisible():
            self.refresh_button.setEnabled(True)
            self._pending_snapshot_payload = (generation, snapshot)
            return
        self.refresh_button.setEnabled(True)
        if not isinstance(snapshot, CubeLibrarySnapshot):
            self._packs = ()
            self._cube_paths_by_pack = {}
            self._render_status(None)
            self._render_pack_rows(())
            self._render_readiness(None)
            self._show_notification(
                severity="error",
                title=app_text("Cube Library unavailable"),
                message=app_text(
                    "Failed to load Cube Library state from the active target."
                ),
            )
            return
        if self._restart_required_after_repair:
            self._restart_required_after_repair = False
            self._notify_restart_required_changed(False)
        self._render_status(snapshot)
        if not snapshot.available:
            self._packs = ()
            self._cube_paths_by_pack = {}
            self._render_pack_rows(())
            self._render_readiness(None)
            return
        self._cube_paths_by_pack = dict(snapshot.cube_paths_by_pack)
        self._render_pack_rows(snapshot.packs)
        self._render_readiness(snapshot.readiness)

    def _render_status(self, snapshot: CubeLibrarySnapshot | None) -> None:
        """Render the target status card."""

        view = project_library_status(snapshot)
        apply_application_text(self.status_row.description_label, view.description)
        self.sync_all_button.setEnabled(view.can_sync_all)

    def _render_pack_rows(self, packs: tuple[CubePackRecord, ...]) -> None:
        """Render tracked packs as expander rows."""

        self._packs = packs
        self._pack_expanders = {}
        _clear_layout(self.pack_list_layout)
        if not packs:
            empty_action = LocalizedPushButton(
                app_text("Add Cube Pack"), self.pack_list
            )
            empty_action.clicked.connect(self._focus_add_pack)
            self.pack_list_layout.addWidget(
                SettingsCard(
                    visual_widget=_icon_widget(
                        self.pack_list,
                        AppIcon.CUBE_MULTIPLE_20_REGULAR,
                    ),
                    title=app_text("No Cube Packs tracked"),
                    description=(
                        app_text(
                            "Add a GitHub Cube Pack to make its cubes available in the picker."
                        )
                    ),
                    trailing_widget=empty_action,
                    reserve_visual_space=True,
                    parent=self.pack_list,
                )
            )
            return
        for pack in packs:
            expander = self._render_pack_expander(pack)
            self._pack_expanders[pack.repo_ref] = expander
            self.pack_list_layout.addWidget(expander)

    def _render_pack_expander(self, pack: CubePackRecord) -> SettingsExpander:
        """Create one tracked pack expander."""

        view = project_pack(
            pack,
            cube_paths=self._cube_paths_by_pack.get(pack.repo_ref, ()),
        )
        trailing = self._pack_header_controls(pack)
        expander = SettingsExpander(
            title=view.title,
            description=view.subtitle,
            visual_widget=_icon_widget(
                self.pack_list, AppIcon.CUBE_MULTIPLE_20_REGULAR
            ),
            trailing_widget=trailing,
            expanded=False,
            parent=self.pack_list,
        )
        self._render_pack_details(expander, view, pack)
        return expander

    def _render_pack_details(
        self,
        expander: SettingsExpander,
        view: CubePackRowView,
        pack: CubePackRecord,
    ) -> None:
        """Render expanded detail and actions for one pack."""

        for detail in view.details:
            expander.add_widget(_detail_card(detail, parent=expander.content_widget()))
        remove_description = (
            app_text("Remove this Cube Pack from the active target.")
            if view.can_remove
            else view.remove_disabled_reason
        )
        sync_button = LocalizedPushButton(app_text("Sync"), expander.content_widget())
        sync_button.clicked.connect(
            lambda _checked=False, item=pack: self._request_sync_pack(item)
        )
        remove_button = LocalizedPushButton(
            app_text("Remove"), expander.content_widget()
        )
        remove_button.setEnabled(view.can_remove)
        remove_button.clicked.connect(
            lambda _checked=False, item=pack: self._request_remove_pack(item)
        )
        expander.add_widget(
            SettingsExpanderRow(
                title=app_text("Actions"),
                description=remove_description,
                trailing_widget=_control_row(
                    expander.content_widget(),
                    sync_button,
                    remove_button,
                ),
                parent=expander.content_widget(),
            )
        )

    def _pack_header_controls(self, pack: CubePackRecord) -> QWidget:
        """Create quiet direct controls for one collapsed pack row."""

        enabled_switch = LocalizedSwitchButton(
            "Off",
            self.pack_list,
            indicatorPos=IndicatorPosition.RIGHT,
        )
        enabled_switch.setChecked(pack.enabled)
        enabled_switch.checkedChanged.connect(
            lambda checked, item=pack: self._request_toggle_enabled(item, checked)
        )
        return _control_row(self.pack_list, enabled_switch)

    def _render_readiness(self, readiness: object) -> None:
        """Render target custom-node readiness."""

        _clear_layout(self.readiness_layout)
        self._dependency_repair_proposal = self._service.dependency_repair_proposal(
            readiness
        )
        readiness_view = project_readiness(readiness)
        if not readiness_view.details or readiness_view.ready:
            self.readiness_layout.addWidget(
                SettingsCard(
                    visual_widget=_icon_widget(
                        self.readiness_container,
                        AppIcon.SHIELD_CHECKMARK_20_REGULAR,
                    ),
                    title=readiness_view.title,
                    description=readiness_view.summary,
                    reserve_visual_space=True,
                    parent=self.readiness_container,
                )
            )
            return
        expander = SettingsExpander(
            title=readiness_view.title,
            description=readiness_view.summary,
            visual_widget=_icon_widget(
                self.readiness_container,
                AppIcon.SHIELD_CHECKMARK_20_REGULAR,
            ),
            expanded=False,
            parent=self.readiness_container,
        )
        for detail in readiness_view.details:
            expander.add_widget(_detail_card(detail, parent=expander.content_widget()))
        if self._dependency_repair_proposal is not None:
            repair_button = LocalizedPushButton(
                app_text("Install required nodes"), expander.content_widget()
            )
            repair_button.clicked.connect(self._request_repair_dependencies)
            expander.add_widget(
                SettingsExpanderRow(
                    title=app_text("Repair"),
                    description=app_text(
                        "Install missing custom nodes required by enabled cubes."
                    ),
                    trailing_widget=repair_button,
                    parent=expander.content_widget(),
                )
            )
        self.readiness_layout.addWidget(expander)

    def _request_repair_dependencies(self) -> None:
        """Prompt when needed, then repair missing Cube Library dependencies."""

        proposal = self._dependency_repair_proposal
        if proposal is None:
            return
        if proposal.requires_confirmation:
            node_list = "\n".join(
                f"- {label}" for label in proposal.confirmation_node_labels
            )
            answer = QMessageBox.question(
                self,
                render_application_text(app_text("Install required custom nodes")),
                render_application_text(
                    app_text(
                        "Cubes you are subscribed to require additional custom "
                        "nodes.\n\n%1\n\nInstall these nodes now?",
                        node_list,
                    )
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._show_notification(
                    severity="warning",
                    title=app_text("Dependency repair skipped"),
                    message=app_text("Missing cube dependencies still need attention."),
                )
                return
        self._run_background(
            task_id="cube_library_repair_dependencies",
            operation=lambda: self._repair_dependencies(proposal),
        )

    def _repair_dependencies(self, proposal: CubeDependencyRepairProposal) -> None:
        """Run dependency repair through the settings task route."""

        try:
            result = self._service.repair_dependency_proposal(proposal)
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="repair_dependencies",
                    success=result is not None and not result.failed_nodes,
                    severity="success"
                    if result is not None and not result.failed_nodes
                    else "error",
                    title=app_text("Required nodes installed")
                    if result is not None and not result.failed_nodes
                    else app_text("Dependency repair failed"),
                    message=app_text(
                        "Restart ComfyUI before using repaired cube dependencies."
                    )
                    if result is not None and result.restart_required
                    else app_text("Cube Library dependencies are up to date."),
                    payload=result,
                )
            )
        except Exception as error:
            log_exception(
                _LOGGER, "Failed to repair Cube Library dependencies", error=error
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="repair_dependencies",
                    success=False,
                    severity="error",
                    title=app_text("Dependency repair failed"),
                    message=app_text("Could not install required Cube Library nodes."),
                    error=error,
                )
            )

    def _request_restart_comfy(self) -> None:
        """Request Comfy restart after dependency repair."""

        restart_service = self._restart_service
        if restart_service is None:
            self._show_notification(
                severity="warning",
                title=app_text("Restart ComfyUI manually"),
                message=app_text(
                    "Restart ComfyUI before using repaired cube dependencies."
                ),
            )
            return
        self._run_background(
            task_id="cube_library_restart_comfy",
            operation=lambda: self._restart_comfy(restart_service),
        )

    def _restart_comfy(self, restart_service: ComfyRestartService) -> None:
        """Run restart request through the settings task route."""

        try:
            job = restart_service.restart_comfy()
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="restart_comfy",
                    success=job is not None,
                    severity="success" if job is not None else "error",
                    title=app_text("Comfy restart requested")
                    if job is not None
                    else app_text("Comfy restart failed"),
                    message=app_text("Refreshing Cube Library after restart request.")
                    if job is not None
                    else app_text("Comfy restart could not be started."),
                    payload=job,
                )
            )
        except Exception as error:
            log_exception(_LOGGER, "Failed to request Comfy restart", error=error)
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="restart_comfy",
                    success=False,
                    severity="error",
                    title=app_text("Comfy restart failed"),
                    message=app_text("Comfy restart could not be started."),
                    error=error,
                )
            )

    def _validate_pack(
        self,
        candidate: GitHubCubePackCandidate,
    ) -> CubePackPreflight | None:
        """Validate one GitHub Cube Pack candidate on the target."""

        return self._service.preflight_pack(
            owner=candidate.owner,
            repo=candidate.repo,
            branch=_MAIN_BRANCH,
        )

    def _request_add_pack(self) -> None:
        """Validate and add the current Cube Pack GitHub URL."""

        candidate = parse_github_cube_pack_url(self.github_url_edit.text())
        if candidate is None:
            self._show_notification(
                severity="warning",
                title=app_text("GitHub URL needed"),
                message=app_text("Paste a GitHub repository URL for a Cube Pack."),
            )
            set_localized_text(
                self.validation_result_row.description_label,
                "Paste a URL like https://github.com/owner/repository.",
            )
            self.validation_result_row.show()
            self.add_pack_expander.set_content_available(True)
            self.add_pack_expander.set_expanded(True)
            self.github_url_edit.setFocus()
            return
        self.add_button.setEnabled(False)
        self._run_background(
            task_id="cube_library_add_pack",
            operation=lambda: self._validate_and_add_pack(candidate),
        )

    def _validate_and_add_pack(self, candidate: GitHubCubePackCandidate) -> None:
        """Validate, add, and sync one Cube Pack through the settings task route."""

        try:
            preflight = self._validate_pack(candidate)
            if not isinstance(preflight, CubePackPreflight):
                self.operation_finished.emit(
                    CubeLibraryOperationResult(
                        operation="add",
                        success=False,
                        severity="error",
                        title=app_text("Cube Pack validation failed"),
                        message=app_text(
                            "Could not validate %1 on the active target.",
                            candidate.repo_ref,
                        ),
                        owner=candidate.owner,
                        repo=candidate.repo,
                        branch=_MAIN_BRANCH,
                    )
                )
                return
            if not preflight.contains_cubes:
                self.operation_finished.emit(
                    CubeLibraryOperationResult(
                        operation="validation",
                        success=False,
                        severity="warning",
                        title=app_text("No cubes found"),
                        message=app_text(
                            "Validation found no cubes in %1.",
                            candidate.repo_ref,
                        ),
                        payload=preflight,
                        owner=candidate.owner,
                        repo=candidate.repo,
                        branch=_MAIN_BRANCH,
                    )
                )
                return
            result = self._service.add_pack(
                owner=candidate.owner,
                repo=candidate.repo,
                branch=_MAIN_BRANCH,
                sync_immediately=True,
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="add",
                    success=isinstance(result, CubePackRecord),
                    severity="success"
                    if isinstance(result, CubePackRecord)
                    else "error",
                    title=app_text("Cube Pack added")
                    if isinstance(result, CubePackRecord)
                    else app_text("Cube Pack add failed"),
                    message=app_text("Validated and synced %1.", candidate.repo_ref)
                    if isinstance(result, CubePackRecord)
                    else app_text(
                        "Could not add %1.",
                        candidate.repo_ref,
                    ),
                    payload=preflight,
                    owner=candidate.owner,
                    repo=candidate.repo,
                    branch=_MAIN_BRANCH,
                )
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to validate and add Cube Pack",
                owner=candidate.owner,
                repo=candidate.repo,
                branch=_MAIN_BRANCH,
                error=error,
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="add",
                    success=False,
                    severity="error",
                    title=app_text("Cube Pack add failed"),
                    message=app_text(
                        "Could not add %1.",
                        candidate.repo_ref,
                    ),
                    owner=candidate.owner,
                    repo=candidate.repo,
                    branch=_MAIN_BRANCH,
                    error=error,
                )
            )

    def _request_sync_all(self) -> None:
        """Sync all enabled Cube Packs."""

        self.sync_all_button.setEnabled(False)
        self._run_background(
            task_id="cube_library_sync_all",
            operation=self._sync_all,
        )

    def _sync_all(self) -> None:
        """Sync all packs through the settings task route."""

        try:
            result = self._service.sync_all_packs()
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="sync_all",
                    success=True,
                    severity="success",
                    title=app_text("Cube Packs synced"),
                    message=app_text(
                        "Synced %1 Cube Packs.",
                        len(result),
                    ),
                    payload=result,
                )
            )
        except Exception as error:
            log_exception(_LOGGER, "Failed to sync Cube Packs", error=error)
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="sync_all",
                    success=False,
                    severity="error",
                    title=app_text("Cube Pack sync failed"),
                    message=app_text("Could not sync Cube Packs."),
                    error=error,
                )
            )

    def _request_toggle_enabled(self, pack: CubePackRecord, enabled: bool) -> None:
        """Update enabled state for one pack."""

        if pack.enabled == enabled:
            return
        self._run_background(
            task_id="cube_library_toggle_pack",
            operation=lambda: self._toggle_enabled(pack, enabled),
        )

    def _toggle_enabled(self, pack: CubePackRecord, enabled: bool) -> None:
        """Toggle pack enabled state through the settings task route."""

        try:
            result = self._service.set_pack_enabled(
                owner=pack.owner,
                repo=pack.repo,
                enabled=enabled,
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="toggle",
                    success=isinstance(result, CubePackRecord),
                    severity="success"
                    if isinstance(result, CubePackRecord)
                    else "error",
                    title=app_text("Cube Pack updated")
                    if isinstance(result, CubePackRecord)
                    else app_text("Cube Pack update failed"),
                    message=app_text(
                        "%1 %2.",
                        pack.repo_ref,
                        app_text("enabled") if enabled else app_text("disabled"),
                    )
                    if isinstance(result, CubePackRecord)
                    else app_text(
                        "Could not update %1.",
                        pack.repo_ref,
                    ),
                    payload=result,
                    owner=pack.owner,
                    repo=pack.repo,
                    branch=pack.branch,
                )
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to update Cube Pack",
                owner=pack.owner,
                repo=pack.repo,
                error=error,
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="toggle",
                    success=False,
                    severity="error",
                    title=app_text("Cube Pack update failed"),
                    message=app_text(
                        "Could not update %1.",
                        pack.repo_ref,
                    ),
                    owner=pack.owner,
                    repo=pack.repo,
                    branch=pack.branch,
                    error=error,
                )
            )

    def _request_sync_pack(self, pack: CubePackRecord) -> None:
        """Sync one tracked pack."""

        self._run_background(
            task_id="cube_library_sync_pack",
            operation=lambda: self._sync_pack(pack),
        )

    def _sync_pack(self, pack: CubePackRecord) -> None:
        """Sync selected pack through the settings task route."""

        try:
            result = self._service.sync_pack(owner=pack.owner, repo=pack.repo)
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="sync",
                    success=isinstance(result, CubePackRecord),
                    severity="success"
                    if isinstance(result, CubePackRecord)
                    else "error",
                    title=app_text("Cube Pack synced")
                    if isinstance(result, CubePackRecord)
                    else app_text("Cube Pack sync failed"),
                    message=app_text("Synced %1.", pack.repo_ref)
                    if isinstance(result, CubePackRecord)
                    else app_text(
                        "Could not sync %1.",
                        pack.repo_ref,
                    ),
                    payload=result,
                    owner=pack.owner,
                    repo=pack.repo,
                    branch=pack.branch,
                )
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to sync Cube Pack",
                owner=pack.owner,
                repo=pack.repo,
                error=error,
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="sync",
                    success=False,
                    severity="error",
                    title=app_text("Cube Pack sync failed"),
                    message=app_text(
                        "Could not sync %1.",
                        pack.repo_ref,
                    ),
                    owner=pack.owner,
                    repo=pack.repo,
                    branch=pack.branch,
                    error=error,
                )
            )

    def _request_remove_pack(self, pack: CubePackRecord) -> None:
        """Confirm and remove one tracked pack."""

        if pack.default_base_repo:
            self._show_notification(
                severity="warning",
                title=app_text("Cube Pack cannot be removed"),
                message=app_text(
                    "Base Cube Packs are required by Substitute and cannot be removed."
                ),
            )
            return
        answer = QMessageBox.question(
            self,
            render_application_text(app_text("Remove Cube Pack")),
            render_application_text(
                app_text("Remove %1 from the active target?", pack.repo_ref)
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_background(
            task_id="cube_library_remove_pack",
            operation=lambda: self._remove_pack(pack),
        )

    def _remove_pack(self, pack: CubePackRecord) -> None:
        """Remove selected pack through the settings task route."""

        try:
            result = self._service.remove_pack(owner=pack.owner, repo=pack.repo)
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="remove",
                    success=result,
                    severity="success" if result else "error",
                    title=(
                        app_text("Cube Pack removed")
                        if result
                        else app_text("Cube Pack remove failed")
                    ),
                    message=app_text("Removed %1.", pack.repo_ref)
                    if result
                    else app_text(
                        "Could not remove %1.",
                        pack.repo_ref,
                    ),
                    owner=pack.owner,
                    repo=pack.repo,
                    branch=pack.branch,
                )
            )
        except Exception as error:
            log_exception(
                _LOGGER,
                "Failed to remove Cube Pack",
                owner=pack.owner,
                repo=pack.repo,
                error=error,
            )
            self.operation_finished.emit(
                CubeLibraryOperationResult(
                    operation="remove",
                    success=False,
                    severity="error",
                    title=app_text("Cube Pack remove failed"),
                    message=app_text(
                        "Could not remove %1.",
                        pack.repo_ref,
                    ),
                    owner=pack.owner,
                    repo=pack.repo,
                    branch=pack.branch,
                    error=error,
                )
            )

    def _apply_operation_result(self, result: object) -> None:
        """Render operation result and refresh target state."""

        self._sync_add_pack_actions()
        if not isinstance(result, CubeLibraryOperationResult):
            return
        if result.error is not None:
            self._resolved_error_presenter().show_exception_report(
                title=result.title,
                message=result.message,
                stage="settings",
                error=result.error,
                context=SubstituteOperationContext(
                    operation=f"cube_library.{result.operation}",
                    package_name=(
                        f"{result.owner}/{result.repo}"
                        if result.owner and result.repo
                        else None
                    ),
                    values={
                        "owner": result.owner,
                        "repo": result.repo,
                        "branch": result.branch,
                    },
                ),
            )
        self._show_notification(
            severity=result.severity,
            title=result.title,
            message=result.message,
        )
        if result.operation == "repair_dependencies":
            self._restart_required_after_repair = bool(
                getattr(result.payload, "restart_required", False)
            )
            if self._restart_required_after_repair and result.success:
                self._notify_restart_required_changed(True)
                self._render_restart_required_action()
                return
        if result.operation == "restart_comfy" and result.success:
            if self._post_restart_refresh is not None:
                self._post_restart_refresh()
            if self._catalog_invalidated is not None:
                self._catalog_invalidated()
            self.refresh()
            return
        if result.operation in {"validation", "add"}:
            self._render_validation_result(result.payload)
            if result.operation == "validation":
                return
        if result.success:
            if self._catalog_invalidated is not None:
                self._catalog_invalidated()
            self.refresh()

    def _render_restart_required_action(self) -> None:
        """Show the Comfy restart action after dependency mutation."""

        _clear_layout(self.readiness_layout)
        restart_button = LocalizedPushButton(
            app_text("Restart Comfy"), self.readiness_container
        )
        restart_button.clicked.connect(self._request_restart_comfy)
        self.readiness_layout.addWidget(
            SettingsCard(
                visual_widget=_icon_widget(
                    self.readiness_container,
                    AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
                ),
                title=app_text("Comfy restart required"),
                description=(
                    app_text(
                        "Cube dependency repair changed the target environment. Restart "
                        "ComfyUI before generating with the repaired cubes."
                    )
                ),
                trailing_widget=restart_button,
                reserve_visual_space=True,
                parent=self.readiness_container,
            )
        )

    def _notify_restart_required_changed(self, required: bool) -> None:
        """Notify the shell that dependency repair changed generation readiness."""

        if self._restart_required_changed is not None:
            self._restart_required_changed(required)

    def _render_validation_result(self, payload: object) -> None:
        """Render validation details inside the add-pack expander."""

        if not isinstance(payload, CubePackPreflight):
            set_localized_text(
                self.validation_result_row.description_label,
                "Validation did not return results.",
            )
            self.validation_result_row.show()
            self.add_pack_expander.set_content_available(True)
            self.add_pack_expander.set_expanded(True)
            return
        paths = ", ".join(payload.cube_paths) if payload.cube_paths else "None"
        truncated = " Result was truncated." if payload.truncated else ""
        set_localized_text(
            self.validation_result_row.description_label,
            "%1/%2: %3 %4 found. Cubes: %5.%6",
            payload.owner,
            payload.repo,
            payload.cube_count,
            _cube_noun(payload.cube_count),
            paths,
            truncated,
        )
        self.validation_result_row.show()
        self.add_pack_expander.set_content_available(True)
        self.add_pack_expander.set_expanded(True)

    def _show_notification(
        self,
        *,
        severity: SettingsInfoBarSeverity,
        title: str,
        message: str,
    ) -> None:
        """Show inline operation feedback."""

        self.notification_bar.show_message(
            severity=severity,
            title=title,
            message=message,
        )

    def _focus_add_pack(self) -> None:
        """Expand and focus the add-pack editor."""

        self.github_url_edit.setFocus()

    def _sync_add_pack_actions(self) -> None:
        """Refresh add-pack action enablement."""

        enabled = bool(parse_github_cube_pack_url(self.github_url_edit.text()))
        self.add_button.setEnabled(enabled)

    def _resolved_error_presenter(self) -> ErrorReportPresenterProtocol:
        """Return the injected presenter or lazily create one parented to the page."""

        if self._error_presenter is None:
            self._error_presenter = ErrorPresenter(parent=self)
        return self._error_presenter

    def _add_pack_candidate(self) -> GitHubCubePackCandidate | None:
        """Return the parsed add-pack candidate."""

        return parse_github_cube_pack_url(self.github_url_edit.text())


def _detail_card(detail: CubePackDetailView, *, parent: QWidget) -> SettingsExpanderRow:
    """Return one expanded detail row."""

    return SettingsExpanderRow(
        title=detail.label,
        description=detail.value,
        parent=parent,
    )


def _control_row(parent: QWidget, *widgets: QWidget) -> QWidget:
    """Create a compact right-aligned control row."""

    controls = QWidget(parent)
    controls.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(controls)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    return controls


def _icon_widget(parent: QWidget, icon: AppIcon) -> IconWidget:
    """Create one fixed-size Settings row icon."""

    widget = IconWidget(icon, parent)
    widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
    return widget


def _clear_layout(layout: QVBoxLayout) -> None:
    """Remove and delete all widgets from a vertical layout."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _cube_noun(count: int) -> str:
    """Return the cube noun for one count."""

    return "cube" if count == 1 else "cubes"


def parse_github_cube_pack_url(value: str) -> GitHubCubePackCandidate | None:
    """Parse a GitHub repository URL or owner/repo shorthand for pack adding."""

    text = value.strip()
    if not text:
        return None
    if "://" not in text and not text.lower().startswith("github.com/"):
        return _candidate_from_parts(text.split("/"))

    candidate_text = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate_text)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    return _candidate_from_parts(parsed.path.strip("/").split("/"))


def _candidate_from_parts(parts: list[str]) -> GitHubCubePackCandidate | None:
    """Return a candidate from path parts when owner and repository are present."""

    if len(parts) < 2:
        return None
    owner = parts[0].strip()
    repo = parts[1].strip().removesuffix(".git")
    if not owner or not repo:
        return None
    return GitHubCubePackCandidate(owner=owner, repo=repo)


__all__ = [
    "CubeLibrarySettingsPage",
    "GitHubCubePackCandidate",
    "parse_github_cube_pack_url",
]
