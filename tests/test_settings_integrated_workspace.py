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

"""Widget contract tests for the integrated Settings workspace components."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, cast

import pytest
from PySide6.QtCore import QObject, QPoint
from PySide6.QtTest import QTest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ComboBox,
    PushButton,
    SearchLineEdit,
    TitleLabel,
)
from tests.localization_testing import stub_translation_manager

from substitute.application.about import (
    AboutInfoService,
    AboutInfoSnapshot,
    AboutVersionRow,
    AboutVersionStatus,
)
from substitute.application.appearance import (
    AppearanceRestartCoordinator,
    AppearanceResolver,
    ResolvedAppearance,
)
from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.application.cube_library import CubeLibraryManagementService
from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.ports.civitai_cache_repository import CivitaiCacheSummary
from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
    CredentialStoreStatus,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.application.onboarding import (
    ComfyConnectionSettingsService,
    ComfyConnectionSettingsSnapshot,
)
from substitute.application.prompt_editor import default_prompt_feature_preferences
from substitute.application.prompt_editor import PromptEditorPreferenceService
from substitute.domain.appearance import (
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    SystemAppearanceSnapshot,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.domain.generation import (
    GenerationPreviewMethod,
    GenerationPreviewPreferences,
    JpegOutputSettings,
    JpegSizingMode,
    OutputPersistenceMode,
    OutputPreferences,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.prompt.preferences import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
)
from substitute.presentation.motion import (
    SETTINGS_NAV_INDICATOR_DURATION_MS,
    SETTINGS_PAGE_TRANSITION_DURATION_MS,
)
from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.comfy_environment_page import ComfyEnvironmentPage
from substitute.presentation.settings.cube_library_page import CubeLibrarySettingsPage
from substitute.presentation.settings.generation_page import GenerationSettingsPage
from substitute.presentation.settings.jpeg_companion_settings import (
    JpegCompanionSettingsControl,
)
from substitute.presentation.settings.generation_preview_settings import (
    GenerationPreviewSettingsControl,
)
from substitute.presentation.settings.civitai_page import CivitaiSettingsPage
from substitute.presentation.settings.settings_workspace import (
    ABOUT_SECTION_ID,
    create_settings_workspace,
)
from substitute.presentation.settings.settings_catalog_builders import (
    AppearanceSettingsContext,
    build_appearance_settings_page,
)
from substitute.presentation.settings import settings_catalog_builders
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
)
from substitute.presentation.settings.settings_control_group import SettingsControlGroup
from substitute.presentation.shell.settings_toolbar_search import (
    SETTINGS_SEARCH_DEBOUNCE_MS,
    SettingsToolbarSearchBox,
)
from substitute.presentation.settings.prompt_editor_page import PromptEditorSettingsPage
from substitute.presentation.settings.settings_navigation import (
    SettingsNavigationDescriptor,
    SettingsNavigationPane,
)
from substitute.presentation.settings.settings_card import (
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_segmented_card import (
    SettingsSegmentedCard,
    SettingsSegmentedCardRow,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    SETTINGS_CARD_PADDING,
)
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner
from substitute.presentation.settings.settings_workspace_panel import (
    SETTINGS_CONTENT_MAX_WIDTH,
    SettingsPageDescriptor,
    SettingsWorkspacePanel,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.infrastructure.persistence import (
    FileCivitaiPreferenceRepository,
    FileDanbooruPreferenceRepository,
    SqliteDanbooruCacheStore,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings workspace Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for integrated widget tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def test_settings_navigation_emits_user_page_selection() -> None:
    """Settings navigation should expose ordered non-workflow page selection."""

    _app()
    navigation = SettingsNavigationPane()
    selected: list[str] = []
    navigation.pageSelected.connect(selected.append)
    navigation.set_pages(
        (
            SettingsNavigationDescriptor("appearance", "Appearance", "Theme"),
            SettingsNavigationDescriptor(
                "prompt_editing", "Prompt Editing", "Features"
            ),
        )
    )

    navigation._on_item_activated("prompt_editing")

    assert navigation.page_ids() == ("appearance", "prompt_editing")
    assert navigation.selected_page_id() == "prompt_editing"
    assert selected == ["prompt_editing"]


def test_settings_navigation_slides_indicator_between_pages() -> None:
    """Settings navigation should animate the selected-page accent rail."""

    app = _app()
    navigation = SettingsNavigationPane()
    navigation.set_pages(
        (
            SettingsNavigationDescriptor("appearance", "Appearance", "Theme"),
            SettingsNavigationDescriptor(
                "prompt_editing", "Prompt Editing", "Features"
            ),
        )
    )
    navigation.show()
    app.processEvents()
    navigation.select_page("appearance", animated=False)
    app.processEvents()
    initial_y = navigation.indicatorY

    navigation.select_page("prompt_editing", animated=True)

    assert (
        navigation._indicator_animation.duration() == SETTINGS_NAV_INDICATOR_DURATION_MS
    )
    assert navigation._indicator_animation.endValue() != initial_y


def test_settings_workspace_panel_switches_active_pages() -> None:
    """Settings panel should show one active page instead of a continuous document."""

    app = _app()
    panel = SettingsWorkspacePanel()
    emitted: list[str] = []
    panel.currentPageChanged.connect(emitted.append)
    panel.resize(520, 220)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance",
                "Appearance",
                "Theme",
                None,
                _tall_widget("A"),
            ),
            SettingsPageDescriptor(
                "prompt_editing",
                "Prompt Editing",
                "Features",
                None,
                _tall_widget("B"),
            ),
        )
    )
    panel.show()
    app.processEvents()
    panel.select_page("prompt_editing", animated=False)
    app.processEvents()

    assert panel.page_ids() == ("appearance", "prompt_editing")
    assert panel.active_page_id() == "prompt_editing"
    assert emitted[-1] == "prompt_editing"
    appearance_shell = panel.page_shell("appearance")
    assert appearance_shell is not None
    assert appearance_shell.isEnabled() is False


def test_settings_workspace_panel_clamps_content_column_width() -> None:
    """Settings content should not stretch across the full route width."""

    app = _app()
    panel = SettingsWorkspacePanel()
    panel.resize(1500, 260)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance",
                "Appearance",
                "Theme",
                None,
                _tall_widget("A"),
            ),
        )
    )
    panel.show()
    app.processEvents()
    shell = panel.page_shell("appearance")

    assert shell is not None
    assert shell._content_column.maximumWidth() == SETTINGS_CONTENT_MAX_WIDTH
    assert shell.content_column_width() == SETTINGS_CONTENT_MAX_WIDTH
    assert shell.content_column_x() > 0


def test_settings_workspace_resize_updates_active_page_width() -> None:
    """Visible Settings resizes should propagate to active page row modes."""

    app = _app()
    page = QWidget()
    page_layout = QVBoxLayout(page)
    card = SettingsCard(
        title="Resize",
        description="Tracks shell width",
        trailing_widget=QWidget(),
    )
    page_layout.addWidget(card)
    panel = SettingsWorkspacePanel()
    panel.resize(1500, 300)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance",
                "Appearance",
                "Theme",
                None,
                page,
            ),
        )
    )
    panel.show()
    app.processEvents()
    shell = panel.page_shell("appearance")

    assert shell is not None
    assert shell.content_column_width() == SETTINGS_CONTENT_MAX_WIDTH
    assert card.layout_mode() == "wide"

    panel.resize(260, 300)
    app.processEvents()

    assert shell.content_column_width() < SETTINGS_CONTENT_MAX_WIDTH
    assert card.layout_mode() == "wrapped_no_icon"
    assert card.width() <= shell.content_column_width()
    panel.close()


def test_settings_workspace_resyncs_width_after_hidden_route_resize() -> None:
    """Settings should not reuse a stale wide column after hidden route resizing."""

    app = _app()
    route_stack = QStackedWidget()
    workflow_page = QWidget()
    panel = SettingsWorkspacePanel()
    generation_page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(
            _GenerationPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            _OutputOrganizationPreferenceRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "generation",
                "Generation",
                "Preview",
                None,
                generation_page,
            ),
        )
    )
    route_stack.addWidget(workflow_page)
    route_stack.addWidget(panel)
    route_stack.resize(1300, 720)
    route_stack.setCurrentWidget(panel)
    route_stack.show()
    app.processEvents()
    shell = panel.page_shell("generation")

    assert shell is not None
    assert shell.content_column_width() == SETTINGS_CONTENT_MAX_WIDTH

    route_stack.setCurrentWidget(workflow_page)
    route_stack.resize(760, 720)
    app.processEvents()
    route_stack.setCurrentWidget(panel)
    panel.select_page("generation", animated=False)
    app.processEvents()

    viewport_width = shell._scroll_surface.viewport().width()
    assert shell.content_column_width() <= viewport_width
    assert shell.content_column_width() < SETTINGS_CONTENT_MAX_WIDTH
    for card in generation_page.findChildren(SettingsCard):
        assert card.width() <= shell.content_column_width()
        if card.trailing_widget is not None:
            assert card.trailing_widget.width() <= card.width()

    route_stack.close()
    route_stack.deleteLater()
    app.processEvents()


def test_settings_workspace_panel_configures_page_transition() -> None:
    """Settings page selection should configure the shared page transition tokens."""

    _app()
    panel = SettingsWorkspacePanel()
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance", "Appearance", "Theme", None, QWidget()
            ),
            SettingsPageDescriptor(
                "generation", "Generation", "Preview", None, QWidget()
            ),
        )
    )

    panel.select_page("generation", animated=True)

    assert (
        panel._transition_animation.duration() == SETTINGS_PAGE_TRANSITION_DURATION_MS
    )
    assert panel._transition_animation.endValue() == 0


def test_settings_workspace_panel_respects_reduced_motion_override() -> None:
    """Settings page transition duration should collapse under reduced motion."""

    app = _app()
    app.setProperty("substitute.reduce_motion", True)
    try:
        panel = SettingsWorkspacePanel()
        panel.set_pages(
            (
                SettingsPageDescriptor(
                    "appearance", "Appearance", "Theme", None, QWidget()
                ),
                SettingsPageDescriptor(
                    "generation", "Generation", "Preview", None, QWidget()
                ),
            )
        )

        panel.select_page("generation", animated=True)

        assert panel._transition_animation.duration() == 0
    finally:
        app.setProperty("substitute.reduce_motion", None)


def test_settings_workspace_panel_refreshes_only_active_page() -> None:
    """Integrated Settings projection should refresh only the active page."""

    _app()
    panel = SettingsWorkspacePanel()
    appearance_page = _RefreshableWidget()
    environment_page = _RefreshableWidget()
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance", "Appearance", "Theme", None, appearance_page
            ),
            SettingsPageDescriptor(
                "comfy_environment",
                "Comfy Environment",
                "Packages",
                None,
                environment_page,
            ),
        )
    )
    panel.set_route_active(True)

    panel.refresh()

    assert appearance_page.refresh_count == 1
    assert environment_page.refresh_count == 0

    panel.select_page("comfy_environment", animated=False)

    assert appearance_page.refresh_count == 1
    assert environment_page.refresh_count == 1


def test_settings_workspace_panel_refreshes_visible_selected_page_without_route_flag() -> (
    None
):
    """Visible Settings selection should refresh even without explicit route state."""

    app = _app()
    panel = SettingsWorkspacePanel()
    appearance_page = _RefreshableWidget()
    environment_page = _RefreshableWidget()
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance", "Appearance", "Theme", None, appearance_page
            ),
            SettingsPageDescriptor(
                "comfy_environment",
                "Comfy Environment",
                "Packages",
                None,
                environment_page,
            ),
        )
    )
    panel.show()
    app.processEvents()

    panel.select_page("comfy_environment", animated=False)

    assert appearance_page.refresh_count == 0
    assert environment_page.refresh_count == 1

    panel.close()
    panel.deleteLater()
    app.processEvents()


def test_settings_workspace_panel_constructs_pages_lazily() -> None:
    """Settings pages should be constructed only when first selected."""

    _app()
    constructed: list[str] = []
    panel = SettingsWorkspacePanel()

    def page_factory(page_id: str) -> Callable[[QWidget], QWidget]:
        """Return a factory that records construction for one page."""

        def create(parent: QWidget) -> QWidget:
            """Create one recorded page widget."""

            constructed.append(page_id)
            return QWidget(parent)

        return create

    panel.set_pages(
        (
            SettingsPageDescriptor(
                "about",
                "About",
                "Version",
                None,
                create_widget=page_factory("about"),
            ),
            SettingsPageDescriptor(
                "generation",
                "Generation",
                "Preview",
                None,
                create_widget=page_factory("generation"),
            ),
        )
    )

    assert constructed == ["about"]
    assert panel.constructed_page_ids() == ("about",)
    assert panel.page_shell("generation") is None

    panel.select_page("generation", animated=False)

    assert constructed == ["about", "generation"]
    assert panel.constructed_page_ids() == ("about", "generation")
    assert panel.page_shell("generation") is not None

    panel.select_page("about", animated=False)
    panel.select_page("generation", animated=False)

    assert constructed == ["about", "generation"]


def test_settings_workspace_uses_user_intent_navigation_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integrated Settings should expose user-intent pages in priority order."""

    _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)

    widgets = create_settings_workspace(
        comfy_environment_service=cast(ComfyEnvironmentService, object()),
        cube_library_management_service=cast(CubeLibraryManagementService, object()),
        about_info_service=cast(AboutInfoService, _AboutInfoService()),
        localization_manager=stub_translation_manager(),
        comfy_connection_settings_service=cast(
            ComfyConnectionSettingsService,
            _ConnectionSettingsService(),
        ),
        appearance_runtime=_AppearanceRuntime(),
        appearance_restart_coordinator=cast(
            AppearanceRestartCoordinator,
            _AppearanceRestartCoordinator(),
        ),
        prompt_editor_preference_service=cast(
            PromptEditorPreferenceService,
            _PromptPreferenceService(),
        ),
        danbooru_preference_service=DanbooruPreferenceService(
            FileDanbooruPreferenceRepository(tmp_path / "config")
        ),
        danbooru_cache_repository=SqliteDanbooruCacheStore(tmp_path / "state"),
        civitai_preference_service=CivitaiPreferenceService(
            FileCivitaiPreferenceRepository(tmp_path / "settings")
        ),
        civitai_credential_service=CivitaiCredentialService(_CivitaiCredentialStore()),
        civitai_cache_service=CivitaiCacheService(_CivitaiCacheRepository()),
        generation_preview_preference_service=GenerationPreviewPreferenceService(
            _GenerationPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            _OutputOrganizationPreferenceRepository(),
            default_output_root=Path("E:/projects"),
        ),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )

    assert widgets.navigation_pane.page_ids() == (
        "about",
        "generation",
        "prompt_editing",
        "model_sources",
        "library",
        "comfyui",
        "appearance",
    )
    assert widgets.panel.page_ids() == widgets.navigation_pane.page_ids()
    assert widgets.panel.active_page_id() == ABOUT_SECTION_ID


def test_generation_output_catalog_controls_persist_unified_output_policy(
    tmp_path: Path,
) -> None:
    """Generation controls should mutate the authoritative output aggregate."""

    _app()
    repository = _OutputOrganizationPreferenceRepository()
    service = OutputPreferenceService(repository, default_output_root=tmp_path)
    page = settings_catalog_builders.build_generation_settings_page(
        settings_catalog_builders.GenerationSettingsContext(
            generation_preview_service=cast(
                GenerationPreviewPreferenceService,
                object(),
            ),
            output_preference_service=service,
            civitai_preference_service=cast(CivitaiPreferenceService, object()),
            task_runner_factory=_task_runner_factory,
        )
    )
    parent = QWidget()
    output_section = next(
        section
        for section in page.sections
        if section.section_id == "generation.output"
    )

    assert tuple(control.setting_id for control in output_section.controls) == (
        "generation.output.folder",
        "generation.output.pattern",
        "generation.output.preview",
        "generation.output.persistence",
        "generation.output.jpeg",
    )

    persistence_row = _appearance_control(
        page, "generation.output.persistence"
    ).factory(parent)
    persistence_combo = persistence_row.findChild(ComboBox)
    assert persistence_combo is not None
    persistence_combo.setCurrentIndex(1)

    jpeg_control = _appearance_control(page, "generation.output.jpeg").factory(parent)
    assert isinstance(jpeg_control, JpegCompanionSettingsControl)
    assert jpeg_control.is_expanded() is False
    assert jpeg_control.quality_control.value() == 100

    jpeg_control.set_checked(True)
    jpeg_control.mode_combo.setCurrentIndex(1)
    jpeg_control.target_size_control.spinbox.setValue(1.25)

    assert repository.preferences.persistence_mode is OutputPersistenceMode.FINAL_CUBE
    assert repository.preferences.jpeg.enabled is True
    assert repository.preferences.jpeg.sizing_mode is JpegSizingMode.TARGET_SIZE
    assert repository.preferences.jpeg.target_size_kib == 1280
    assert jpeg_control.value_stack.currentWidget() is jpeg_control.target_size_control


def test_generation_preview_catalog_uses_one_switch_control_and_persists_state() -> (
    None
):
    """Generation preview settings should disclose and persist one cohesive group."""

    _app()
    repository = _GenerationPreviewPreferenceRepository()
    page = settings_catalog_builders.build_generation_settings_page(
        settings_catalog_builders.GenerationSettingsContext(
            generation_preview_service=GenerationPreviewPreferenceService(repository),
            output_preference_service=cast(OutputPreferenceService, object()),
            civitai_preference_service=cast(CivitaiPreferenceService, object()),
            task_runner_factory=_task_runner_factory,
        )
    )
    preview_section = next(
        section
        for section in page.sections
        if section.section_id == "generation.preview"
    )

    assert tuple(control.setting_id for control in preview_section.controls) == (
        "generation.preview.configuration",
    )

    parent = QWidget()
    control = preview_section.controls[0].factory(parent)
    assert isinstance(control, GenerationPreviewSettingsControl)
    assert control.is_checked() is True
    assert control.is_expanded() is True
    assert control.selected_method() is GenerationPreviewMethod.LATENT2RGB

    control.set_method(GenerationPreviewMethod.AUTO)
    control.set_checked(False)

    assert control.has_pending_work() is False
    assert control.is_expanded() is False
    assert repository.preferences.enabled is False
    assert repository.preferences.method is GenerationPreviewMethod.AUTO

    control.set_checked(True)

    assert control.is_expanded() is True
    assert repository.preferences.enabled is True
    assert repository.preferences.method is GenerationPreviewMethod.AUTO


def test_generation_preview_control_prepares_taesd_through_async_save_route() -> None:
    """Selecting TAESD should preserve backend preparation and result feedback."""

    _app()
    repository = _GenerationPreviewPreferenceRepository()
    backend = _GenerationPreviewAssetBackend()
    control = GenerationPreviewSettingsControl(
        service=GenerationPreviewPreferenceService(repository, backend),
        task_runner_factory=_task_runner_factory,
    )

    control.set_method(GenerationPreviewMethod.TAESD)

    assert control.has_pending_work() is False
    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert backend.ensure_calls == 1
    assert control.status_text() == "TAESD preview files are installed."


def test_jpeg_companion_control_restores_enabled_values_and_preserves_both_modes(
    tmp_path: Path,
) -> None:
    """Persisted JPEG settings should restore disclosure and retain inactive values."""

    _app()
    repository = _OutputOrganizationPreferenceRepository()
    repository.preferences = OutputPreferences(
        jpeg=JpegOutputSettings(
            enabled=True,
            sizing_mode=JpegSizingMode.TARGET_SIZE,
            quality=83,
            target_size_kib=1536,
        )
    )
    service = OutputPreferenceService(repository, default_output_root=tmp_path)
    control = JpegCompanionSettingsControl(service)

    assert control.is_checked() is True
    assert control.is_expanded() is True
    assert control.quality_control.value() == 83
    assert control.target_size_control.value() == 1.5
    assert control.value_stack.currentWidget() is control.target_size_control

    control.mode_combo.setCurrentIndex(0)
    control.quality_control.spinbox.setValue(91)
    control.mode_combo.setCurrentIndex(1)

    assert repository.preferences.jpeg.quality == 91
    assert repository.preferences.jpeg.target_size_kib == 1536
    assert control.value_stack.currentWidget() is control.target_size_control
    control.close()


def test_jpeg_companion_controls_wrap_without_hiding_the_active_editor(
    tmp_path: Path,
) -> None:
    """The compound sizing controls should remain usable on narrow Settings pages."""

    app = _app()
    repository = _OutputOrganizationPreferenceRepository()
    repository.preferences = OutputPreferences(
        jpeg=JpegOutputSettings(
            enabled=True,
            sizing_mode=JpegSizingMode.TARGET_SIZE,
        )
    )
    host = QWidget()
    layout = QVBoxLayout(host)
    control = JpegCompanionSettingsControl(
        OutputPreferenceService(repository, default_output_root=tmp_path),
        host,
    )
    layout.addWidget(control)
    control_group = control.findChild(SettingsControlGroup)
    assert control_group is not None

    host.resize(900, 320)
    host.show()
    _process_events(app)

    assert control_group.layout_mode() == "horizontal"
    assert control.target_size_control.isVisible() is True
    assert (
        control.value_stack.mapTo(control_group, QPoint()).x()
        < control.mode_combo.mapTo(control_group, QPoint()).x()
    )
    assert control.target_size_control.spinbox.maximum() == 20.0
    assert control.target_size_control.spinbox.singleStep() == 0.1

    host.resize(480, 420)
    _process_events(app)

    assert control_group.layout_mode() == "vertical"
    assert control.target_size_control.isVisible() is True
    assert (
        control.target_size_control.width()
        >= control.target_size_control.sizeHint().width()
    )
    host.close()


def test_appearance_catalog_routes_restart_required_settings_to_coordinator() -> None:
    """Appearance rows should route restart and live color settings correctly."""

    _app()
    runtime = _AppearanceRuntime()
    coordinator = _AppearanceRestartCoordinator()
    restart_dialog_calls: list[str] = []
    page = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=runtime,
            appearance_restart_coordinator=cast(
                AppearanceRestartCoordinator,
                coordinator,
            ),
            show_restart_requirements=lambda: restart_dialog_calls.append("show"),
        )
    )
    parent = QWidget()
    assert tuple(section.title for section in page.sections) == (
        "Theme",
        "Window",
        "System colors",
    )

    theme_row = _appearance_control(page, "appearance.theme.mode").factory(parent)
    theme_combo = theme_row.findChild(ComboBox)
    assert theme_combo is not None
    theme_combo.setCurrentIndex(0)

    material_row = _appearance_control(page, "appearance.window.material").factory(
        parent
    )
    material_combo = material_row.findChild(ComboBox)
    assert material_combo is not None
    material_combo.setCurrentIndex(1)

    colors_row = _appearance_control(
        page,
        "appearance.system_colors.palette",
    ).factory(parent)
    assert isinstance(colors_row, SettingsSegmentedCard)
    assert {"Warning color", "Error color"}.issubset(set(_label_texts(colors_row)))
    assert [row_title for row_title in _segmented_row_titles(colors_row)] == [
        "Accent color",
        "Warning color",
        "Error color",
    ]
    assert colors_row.findChild(QWidget, "AppearanceWarningColorIcon") is not None
    assert colors_row.findChild(QWidget, "AppearanceErrorColorIcon") is not None
    for row in _segmented_rows(colors_row):
        row_layout = row.layout()
        assert row_layout is not None
        margins = row_layout.contentsMargins()
        assert margins.left() == SETTINGS_CARD_PADDING.left()
        assert margins.top() == SETTINGS_CARD_PADDING.top()
        assert margins.right() == SETTINGS_CARD_PADDING.right()
        assert margins.bottom() == SETTINGS_CARD_PADDING.bottom()
        assert row.visual_slot.minimumWidth() == SETTINGS_CARD_ICON_MAX_SIZE
        assert row.visual_slot.maximumWidth() == SETTINGS_CARD_ICON_MAX_SIZE
    accent_combo = colors_row.findChild(ComboBox, "AppearanceAccentSourceCombo")
    assert accent_combo is not None
    warning_mode = colors_row.findChild(ComboBox, "AppearanceWarningModeCombo")
    error_mode = colors_row.findChild(ComboBox, "AppearanceErrorModeCombo")
    warning_choose = colors_row.findChild(PushButton, "AppearanceWarningChooseButton")
    error_choose = colors_row.findChild(PushButton, "AppearanceErrorChooseButton")
    assert warning_mode is not None
    assert error_mode is not None
    assert warning_choose is not None
    assert error_choose is not None
    assert warning_mode.itemText(0) == "Derived"
    assert error_mode.itemText(0) == "Derived"
    assert warning_mode.currentData() is AppearanceWarningColorMode.DEFAULT
    assert error_mode.currentData() is AppearanceErrorColorMode.DEFAULT
    assert warning_mode.itemData(1) is AppearanceWarningColorMode.YELLOW
    assert error_mode.itemData(1) is AppearanceErrorColorMode.RED
    assert warning_choose.isEnabled() is False
    assert error_choose.isEnabled() is False
    accent_combo.setCurrentIndex(1)

    assert coordinator.saved == [
        ("theme", AppearanceThemeMode.LIGHT),
        ("backdrop", AppearanceBackdropMode.ACRYLIC),
    ]
    assert runtime.load_preferences().accent_source is AppearanceAccentSource.SYSTEM
    assert restart_dialog_calls == []

    parent.deleteLater()


def test_appearance_system_colors_open_color_pickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System color segment should persist accent, warning, and error picker choices."""

    _app()
    runtime = _AppearanceRuntime()
    page = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=runtime,
            appearance_restart_coordinator=cast(
                AppearanceRestartCoordinator,
                _AppearanceRestartCoordinator(),
            ),
            show_restart_requirements=None,
        )
    )
    parent = QWidget()
    selected_colors = iter(("#224466", "#FFAA00", "#CC1122"))
    monkeypatch.setattr(
        settings_catalog_builders,
        "ColorDialog",
        lambda color, title, parent: _FakeColorDialog(
            color=next(selected_colors),
            title=title,
            parent=parent,
        ),
    )
    colors_row = _appearance_control(
        page,
        "appearance.system_colors.palette",
    ).factory(parent)

    accent_button = colors_row.findChild(PushButton, "AppearanceAccentChooseButton")
    warning_mode = colors_row.findChild(ComboBox, "AppearanceWarningModeCombo")
    warning_button = colors_row.findChild(PushButton, "AppearanceWarningChooseButton")
    error_mode = colors_row.findChild(ComboBox, "AppearanceErrorModeCombo")
    error_button = colors_row.findChild(PushButton, "AppearanceErrorChooseButton")
    assert accent_button is not None
    assert warning_mode is not None
    assert warning_button is not None
    assert error_mode is not None
    assert error_button is not None

    assert warning_mode.itemText(0) == "Derived"
    assert error_mode.itemText(0) == "Derived"
    assert warning_mode.currentData() is AppearanceWarningColorMode.DEFAULT
    assert error_mode.currentData() is AppearanceErrorColorMode.DEFAULT
    assert warning_button.isEnabled() is False
    assert error_button.isEnabled() is False

    accent_button.click()
    warning_mode.setCurrentIndex(1)
    error_mode.setCurrentIndex(1)
    assert warning_mode.currentData() is AppearanceWarningColorMode.YELLOW
    assert error_mode.currentData() is AppearanceErrorColorMode.RED
    assert runtime.load_preferences().warning_color_mode is (
        AppearanceWarningColorMode.YELLOW
    )
    assert runtime.load_preferences().error_color_mode is AppearanceErrorColorMode.RED
    assert warning_button.isEnabled() is False
    assert error_button.isEnabled() is False

    warning_mode.setCurrentIndex(2)
    error_mode.setCurrentIndex(2)
    assert warning_mode.currentData() is AppearanceWarningColorMode.CUSTOM
    assert error_mode.currentData() is AppearanceErrorColorMode.CUSTOM
    assert warning_button.isEnabled() is True
    assert error_button.isEnabled() is True
    warning_button.click()
    error_button.click()

    preferences = runtime.load_preferences()
    assert preferences.custom_accent_color == "#224466"
    assert preferences.warning_color_mode is AppearanceWarningColorMode.CUSTOM
    assert preferences.error_color_mode is AppearanceErrorColorMode.CUSTOM
    assert preferences.custom_warning_color == "#FFAA00"
    assert preferences.custom_error_color == "#CC1122"

    warning_mode.setCurrentIndex(0)
    assert warning_mode.currentData() is AppearanceWarningColorMode.DEFAULT
    assert runtime.load_preferences().warning_color_mode is (
        AppearanceWarningColorMode.DEFAULT
    )
    assert warning_button.isEnabled() is False

    parent.deleteLater()


def test_appearance_system_colors_rows_remain_visible_after_resize() -> None:
    """System color rows should remain always-visible static card segments."""

    app = _app()
    runtime = _AppearanceRuntime()
    page = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=runtime,
            appearance_restart_coordinator=cast(
                AppearanceRestartCoordinator,
                _AppearanceRestartCoordinator(),
            ),
            show_restart_requirements=None,
        )
    )
    parent = QWidget()
    layout = QVBoxLayout(parent)
    colors_row = _appearance_control(
        page,
        "appearance.system_colors.palette",
    ).factory(parent)
    assert isinstance(colors_row, SettingsSegmentedCard)
    layout.addWidget(colors_row)
    parent.resize(1000, 600)
    parent.show()
    _process_events(app)
    _assert_system_color_controls_aligned(colors_row)

    wide_height = colors_row.height()
    parent.resize(480, 600)
    _process_events(app)
    _assert_system_color_controls_aligned(colors_row)

    warning_row = _segmented_row_with_title(colors_row, "Warning color")
    error_row = _segmented_row_with_title(colors_row, "Error color")
    assert colors_row.height() > wide_height
    assert _segmented_row_titles(colors_row) == (
        "Accent color",
        "Warning color",
        "Error color",
    )
    assert warning_row.geometry().bottom() <= colors_row.height()
    assert error_row.geometry().bottom() <= colors_row.height()
    assert error_row.isVisibleTo(colors_row)

    parent.deleteLater()


def test_settings_page_shell_does_not_own_search_bar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings detail shells should leave search ownership to shell chrome."""

    _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    shell = widgets.panel.page_shell(ABOUT_SECTION_ID)

    assert shell is not None
    assert not widgets.navigation_pane.findChildren(SearchLineEdit)
    assert not hasattr(shell, "search_edit")
    assert not hasattr(shell, "title_label")
    assert isinstance(shell.breadcrumb_label, TitleLabel)
    assert shell.breadcrumb_label.text() == "Settings > About"
    assert shell._content_layout.indexOf(shell.breadcrumb_label) == 0


def test_settings_toolbar_search_box_emits_debounced_queries() -> None:
    """Toolbar Settings search should preserve debounced query emission."""

    app = _app()
    search_box = SettingsToolbarSearchBox()
    emitted: list[str] = []
    search_box.searchQueryChanged.connect(emitted.append)

    search_box.setText("credential")
    app.processEvents()

    assert emitted == []

    QTest.qWait(SETTINGS_SEARCH_DEBOUNCE_MS + 50)
    app.processEvents()

    assert emitted == ["credential"]

    search_box.set_search_text("panel-owned")
    QTest.qWait(SETTINGS_SEARCH_DEBOUNCE_MS + 50)
    app.processEvents()

    assert emitted == ["credential"]


def test_settings_workspace_search_replaces_page_and_clearing_restores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings search should show a synthetic page without changing active page id."""

    app = _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("credential")
    app.processEvents()

    assert widgets.panel.is_search_active() is True
    assert widgets.panel.active_page_id() == ABOUT_SECTION_ID
    assert "Settings > Search settings" in _label_texts(widgets.panel)
    assert "Model Sources > CivitAI account" in _label_texts(widgets.panel)
    assert "API key" in _label_texts(widgets.panel)

    assert widgets.panel.search_query() == "credential"

    widgets.panel.set_search_query("")
    app.processEvents()

    assert widgets.panel.is_search_active() is False
    assert widgets.panel.active_page_id() == ABOUT_SECTION_ID


def test_settings_search_excludes_about_page_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """About copy and acknowledgements should not be indexed as settings."""

    app = _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("About-only patron")
    app.processEvents()

    search_shell = widgets.panel._search_shell
    assert search_shell is not None
    labels = _label_texts(search_shell)
    assert widgets.panel.is_search_active() is True
    assert "No settings found" in labels
    assert "About-only patron" not in labels
    assert "About-only special thanks" not in labels


def test_settings_workspace_search_orders_results_by_navigation_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings search results should follow page and section ordering."""

    app = _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("thumbnail")
    app.processEvents()

    labels = _label_texts(widgets.panel)
    generation_index = labels.index("Generation > Preview")
    model_sources_index = labels.index("Model Sources > Thumbnails and safety")
    assert generation_index < model_sources_index


def test_settings_workspace_keeps_danbooru_under_prompt_editing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Danbooru controls should be grouped as prompt reference support."""

    app = _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    widgets.panel.select_page("prompt_editing", animated=False)
    prompt_shell = widgets.panel.page_shell("prompt_editing")
    widgets.panel.select_page("model_sources", animated=False)
    model_sources_shell = widgets.panel.page_shell("model_sources")
    assert prompt_shell is not None
    assert model_sources_shell is not None

    prompt_labels = _label_texts(prompt_shell.content_widget())
    model_source_labels = _label_texts(model_sources_shell.content_widget())

    assert "Danbooru reference" in prompt_labels
    assert "Show images in wiki viewer" in prompt_labels
    assert "Danbooru cache maintenance" in prompt_labels
    assert "Danbooru reference" not in model_source_labels
    assert "Show images in wiki viewer" not in model_source_labels
    assert "Danbooru cache maintenance" not in model_source_labels

    widgets.panel.show()
    app.processEvents()
    widgets.panel.set_search_query("danbooru")
    app.processEvents()

    labels = _label_texts(widgets.panel)
    assert "Prompt Editing > Danbooru prompt integration" in labels
    assert "Prompt Editing > Danbooru reference" in labels
    assert not any(label.startswith("Model Sources >") for label in labels)


def test_settings_workspace_search_no_results_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings search should render an explicit no-results row."""

    app = _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("definitelynotasetting")
    app.processEvents()

    assert "No settings found" in _label_texts(widgets.panel)


def test_settings_workspace_search_does_not_refresh_dynamic_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings search should not trigger dynamic page refresh work while typing."""

    app = _app()
    refresh_calls: list[str] = []
    monkeypatch.setattr(
        ComfyEnvironmentPage,
        "refresh",
        lambda _page: refresh_calls.append("environment"),
    )
    monkeypatch.setattr(
        CubeLibrarySettingsPage,
        "refresh",
        lambda _page: refresh_calls.append("library"),
    )
    widgets = _settings_workspace(tmp_path)
    widgets.panel.show()
    app.processEvents()
    refresh_calls.clear()

    widgets.panel.set_search_query("server")
    app.processEvents()

    assert widgets.panel.is_search_active() is True
    assert refresh_calls == []


def test_settings_workspace_search_result_activation_selects_owner_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening a Settings search result should navigate instead of embedding controls."""

    app = _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = _settings_workspace(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("account credential")
    app.processEvents()

    cards = widgets.panel.findChildren(
        InteractiveSettingsCard, "SettingsSearchResultCard"
    )
    assert cards

    cards[0].activated.emit()
    app.processEvents()

    assert widgets.panel.search_query() == ""
    assert widgets.panel.is_search_active() is False
    assert widgets.panel.active_page_id() == "model_sources"
    assert widgets.panel.page_shell("model_sources") is not None


def test_civitai_settings_page_persists_policy_credentials_and_cache(
    tmp_path: Path,
) -> None:
    """CivitAI Settings should own preferences, credentials, and cache actions."""

    _app()
    preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings")
    )
    credential_store = _CivitaiCredentialStore()
    credential_service = CivitaiCredentialService(credential_store)
    cache_repository = _CivitaiCacheRepository()
    scheduled_refreshes: list[str] = []
    page = CivitaiSettingsPage(
        preference_service=preference_service,
        credential_service=credential_service,
        cache_service=CivitaiCacheService(
            cache_repository,
            schedule_metadata_refresh=lambda: scheduled_refreshes.append("refresh"),
        ),
    )

    cast(Any, page)._set_metadata_lookup_enabled(False)
    cast(Any, page)._set_missing_model_lookup_enabled(False)
    cast(Any, page)._set_thumbnail_downloads_enabled(False)
    combo = cast(Any, page)._thumbnail_policy_combo
    combo.setCurrentIndex(2)
    cast(Any, page)._set_thumbnail_safety_policy(2)
    cast(Any, page)._set_downloads_enabled(False)
    cast(Any, page)._api_key_edit.setText("secret-token")
    cast(Any, page)._set_api_key()
    cast(Any, page)._clear_thumbnails()
    cast(Any, page)._clear_metadata()
    cast(Any, page)._refresh_metadata()

    preferences = preference_service.load_preferences()
    assert preferences.metadata_lookup_enabled is False
    assert preferences.missing_model_lookup_enabled is False
    assert preferences.thumbnail_downloads_enabled is False
    assert (
        preferences.thumbnail_safety_policy is CivitaiThumbnailSafetyPolicy.ALLOW_SOFT
    )
    assert preferences.downloads_enabled is False
    assert credential_store.saved_key == "secret-token"
    assert "4 bytes" in page.cache_summary_text()
    assert cache_repository.actions == ["clear-thumbnails", "clear-metadata"]
    assert scheduled_refreshes == ["refresh"]


def test_civitai_settings_page_download_organization_preview_and_autocomplete(
    tmp_path: Path,
) -> None:
    """CivitAI Settings should expose download organization pattern controls."""

    app = _app()
    preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings"),
        preview_comfy_root=tmp_path / "diffusion_models",
    )
    page = CivitaiSettingsPage(
        preference_service=preference_service,
        credential_service=CivitaiCredentialService(_CivitaiCredentialStore()),
        cache_service=CivitaiCacheService(_CivitaiCacheRepository()),
    )
    page.show()
    app.processEvents()

    labels = _label_texts(page)
    assert "Model folder pattern" in labels
    assert "Download path preview" in labels
    assert page.download_path_preview_text() == str(
        tmp_path / "diffusion_models" / "Anima" / "anima_baseV10.safetensors"
    )

    page.download_path_pattern_edit.setFocus()
    page.set_download_path_pattern("{base")
    page.download_path_pattern_edit.setCursorPosition(len("{base"))
    assert page.download_token_autocomplete is not None
    page.download_token_autocomplete.refresh()
    app.processEvents()

    assert page.download_token_autocomplete.is_visible() is True
    assert page.download_token_autocomplete.visible_tokens() == ("{base_model}",)
    assert page.download_token_autocomplete.accept_current() is True
    assert page.download_path_pattern_edit.text() == "{base_model}"

    page.set_download_path_pattern("{creator}\\{file_name}")
    page.download_path_pattern_edit.editingFinished.emit()
    app.processEvents()

    assert (
        preference_service.load_preferences().download_path_pattern
        == "{creator}\\{file_name}"
    )
    page.close()


def test_civitai_settings_page_reports_unavailable_linux_credentials(
    tmp_path: Path,
) -> None:
    """CivitAI Settings should explain Linux secure-storage remediation."""

    _app()
    preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings")
    )
    credential_store = _CivitaiCredentialStore(
        status=CredentialStoreStatus(
            available=False,
            backend_name="Linux Secret Service/KWallet",
            reason="No compatible operating-system credential store is available.",
            remediation=(
                "Install and enable GNOME Keyring, KWallet, or another "
                "Secret Service-compatible keyring through your distribution's "
                "package manager, then sign in or unlock it and restart Substitute."
            ),
        )
    )
    page = CivitaiSettingsPage(
        preference_service=preference_service,
        credential_service=CivitaiCredentialService(credential_store),
        cache_service=CivitaiCacheService(_CivitaiCacheRepository()),
    )

    cast(Any, page)._api_key_edit.setText("secret-token")
    cast(Any, page)._set_api_key()

    assert "Secure credential storage is unavailable" in page.api_key_status_text()
    assert "GNOME Keyring" in page.api_key_status_text()
    assert "package manager" in page.api_key_status_text()
    assert credential_store.saved_key is None


def test_settings_pages_leave_section_titles_to_workspace_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings pages should leave section title text to the workspace panel."""

    _app()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    connection_page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, _ConnectionSettingsService()),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    environment_page = ComfyEnvironmentPage(
        cast(ComfyEnvironmentService, object()),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    prompt_page = PromptEditorSettingsPage(
        preference_service=cast(
            PromptEditorPreferenceService,
            _PromptPreferenceService(),
        ),
    )
    generation_page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(
            _GenerationPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            _OutputOrganizationPreferenceRepository(),
            default_output_root=Path("E:/projects"),
        ),
        task_runner_factory=_task_runner_factory,
    )

    assert "Comfy Connection" not in _label_texts(connection_page)
    assert "Comfy Environment" not in _label_texts(environment_page)
    assert "Generation" not in _label_texts(generation_page)
    assert "Prompt Editing" not in _label_texts(prompt_page)


class _RefreshableWidget(QWidget):
    """Widget double that records page refresh calls."""

    def __init__(self) -> None:
        """Create a refresh-counting widget."""

        super().__init__()
        self.refresh_count = 0

    def refresh(self) -> None:
        """Record refresh calls from the integrated Settings panel."""

        self.refresh_count += 1


class _AppearanceRuntime:
    """Appearance runtime double with stable supported options."""

    def __init__(self) -> None:
        """Create the runtime from default appearance preferences."""

        self._preferences = AppearancePreferences(
            schema_version="1",
            theme_mode=AppearanceThemeMode.DARK,
            accent_source=AppearanceAccentSource.CUSTOM,
            custom_accent_color=DEFAULT_CUSTOM_ACCENT_COLOR,
            backdrop_mode=AppearanceBackdropMode.MICA_ALT,
        )

    def load_preferences(self) -> AppearancePreferences:
        """Return current appearance preferences."""

        return self._preferences

    def resolve_preferences(self) -> ResolvedAppearance:
        """Return a resolved appearance snapshot."""

        return AppearanceResolver().resolve(
            self._preferences,
            system_appearance=SystemAppearanceSnapshot(),
        )

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> ResolvedAppearance:
        """Persist one theme mode for page interaction tests."""

        self._preferences = self._preferences.with_theme_mode(theme_mode)
        return self.resolve_preferences()

    def set_accent_source(
        self,
        accent_source: AppearanceAccentSource,
    ) -> ResolvedAppearance:
        """Persist one accent source for page interaction tests."""

        self._preferences = self._preferences.with_accent_source(accent_source)
        return self.resolve_preferences()

    def set_custom_accent_color(self, color: str) -> ResolvedAppearance:
        """Persist one custom accent color for page interaction tests."""

        self._preferences = self._preferences.with_custom_accent_color(color)
        return self.resolve_preferences()

    def set_custom_warning_color(self, color: str | None) -> ResolvedAppearance:
        """Persist one warning color override for page interaction tests."""

        self._preferences = self._preferences.with_custom_warning_color(color)
        return self.resolve_preferences()

    def set_warning_color_mode(
        self,
        mode: AppearanceWarningColorMode,
    ) -> ResolvedAppearance:
        """Persist one warning color mode for page interaction tests."""

        self._preferences = self._preferences.with_warning_color_mode(mode)
        return self.resolve_preferences()

    def set_custom_error_color(self, color: str | None) -> ResolvedAppearance:
        """Persist one error color override for page interaction tests."""

        self._preferences = self._preferences.with_custom_error_color(color)
        return self.resolve_preferences()

    def set_error_color_mode(
        self,
        mode: AppearanceErrorColorMode,
    ) -> ResolvedAppearance:
        """Persist one error color mode for page interaction tests."""

        self._preferences = self._preferences.with_error_color_mode(mode)
        return self.resolve_preferences()

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> ResolvedAppearance:
        """Persist one backdrop mode for page interaction tests."""

        self._preferences = self._preferences.with_backdrop_mode(backdrop_mode)
        return self.resolve_preferences()


class _AppearanceRestartCoordinator:
    """Record restart-required appearance saves for integrated Settings tests."""

    def __init__(self) -> None:
        """Create an empty save log."""

        self.saved: list[tuple[str, object]] = []

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> object:
        """Record one theme-mode save and return an empty pending snapshot."""

        self.saved.append(("theme", theme_mode))
        return _PendingSnapshot(count=0)

    def set_backdrop_mode(self, backdrop_mode: AppearanceBackdropMode) -> object:
        """Record one backdrop-mode save and return an empty pending snapshot."""

        self.saved.append(("backdrop", backdrop_mode))
        return _PendingSnapshot(count=0)


class _PendingSnapshot:
    """Minimal restart snapshot double for Settings catalog tests."""

    def __init__(self, *, count: int) -> None:
        """Store the pending item count exposed by production snapshots."""

        self.count = count


class _FakeColorSignal:
    """Capture and replay one color dialog callback."""

    def __init__(self) -> None:
        """Create an unconnected signal double."""

        self._callback: Callable[[QColor], None] | None = None

    def connect(self, callback: Callable[[QColor], None]) -> None:
        """Record the connected color callback."""

        self._callback = callback

    def emit(self, color: QColor) -> None:
        """Emit one selected color to the connected callback."""

        if self._callback is not None:
            self._callback(color)


class _FakeColorDialog:
    """Minimal QFluent color dialog double for settings picker tests."""

    def __init__(self, *, color: str, title: str, parent: object) -> None:
        """Store the color emitted when the fake dialog executes."""

        self._color = QColor(color)
        self.title = title
        self.parent = parent
        self.colorChanged = _FakeColorSignal()

    def exec(self) -> int:
        """Emit the configured color selection."""

        self.colorChanged.emit(self._color)
        return 1


class _PromptPreferenceService:
    """Prompt preference service double with registry defaults."""

    def __init__(self) -> None:
        """Initialize default prompt preferences."""

        self._preferences = PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features=default_prompt_feature_preferences(),
        )

    def load_preferences(self) -> PromptEditorPreferences:
        """Return default prompt feature preferences."""

        return self._preferences

    def set_feature_allowed(
        self,
        feature: object,
        allowed: bool,
    ) -> PromptEditorPreferences:
        """Record a feature policy change."""

        _ = (feature, allowed)
        return self._preferences


class _GenerationPreviewPreferenceRepository:
    """Generation preview preference repository double with defaults."""

    def __init__(self) -> None:
        """Initialize with default preferences."""

        self.preferences = default_generation_preview_preferences()

    def load(self) -> GenerationPreviewPreferences:
        """Return current preferences."""

        return self.preferences

    def save(self, preferences: GenerationPreviewPreferences) -> None:
        """Persist preferences in memory."""

        self.preferences = preferences


class _GenerationPreviewAssetBackend:
    """Return ready TAESD assets while recording preparation calls."""

    def __init__(self) -> None:
        """Initialize without preparation calls."""

        self.ensure_calls = 0

    def get_taesd_status(self) -> TaesdPreviewAssetStatus:
        """Return the ready test asset status."""

        return self._ready_status()

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus:
        """Record preparation and return the ready test asset status."""

        self.ensure_calls += 1
        return self._ready_status()

    @staticmethod
    def _ready_status() -> TaesdPreviewAssetStatus:
        """Build one deterministic ready TAESD asset status."""

        return TaesdPreviewAssetStatus(
            schema_version=1,
            ready=True,
            installed_count=4,
            missing_count=0,
            downloads_attempted=True,
            assets=(),
            destination_root="E:\\ComfyUI\\models\\vae_approx",
        )


class _OutputOrganizationPreferenceRepository:
    """Output organization preference repository double with defaults."""

    def __init__(self) -> None:
        """Initialize with default preferences."""

        self.preferences = OutputPreferences()

    def load(self) -> OutputPreferences:
        """Return current preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Persist preferences in memory."""

        self.preferences = preferences


class _ConnectionSettingsService:
    """Connection settings service double with a stable managed-local snapshot."""

    def load_snapshot(self) -> ComfyConnectionSettingsSnapshot:
        """Return a stable Comfy connection snapshot."""

        return ComfyConnectionSettingsSnapshot(
            target=ComfyTargetConfiguration(
                mode=ComfyTargetMode.MANAGED_LOCAL,
                endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
                workspace_path=None,
                install_owned=True,
                launch_owned=True,
            ),
            persisted_exists=True,
            status_message="Substitute is configured to use managed ComfyUI.",
            can_test_endpoint=True,
        )


class _CivitaiCredentialStore:
    """CivitAI credential store double that keeps secrets in memory."""

    def __init__(
        self,
        *,
        status: CredentialStoreStatus | None = None,
    ) -> None:
        """Initialize with no saved API key."""

        self.saved_key: str | None = None
        self._status = status or CredentialStoreStatus(
            available=True,
            backend_name="Test secure store",
        )

    def status(self) -> CredentialStoreStatus:
        """Return configured fake storage availability."""

        return self._status

    def has_api_key(self) -> bool:
        """Return whether a key is saved."""

        return self.saved_key is not None

    def load_api_key(self) -> str | None:
        """Return the saved key."""

        return self.saved_key

    def save_api_key(self, api_key: str) -> None:
        """Save one key in memory."""

        if not self._status.available:
            raise CredentialStorageUnavailableError(
                "Secure credential storage is unavailable."
            )
        self.saved_key = api_key

    def clear_api_key(self) -> None:
        """Clear the saved key."""

        self.saved_key = None


class _CivitaiCacheRepository:
    """CivitAI cache repository double that records mutation actions."""

    def __init__(self) -> None:
        """Initialize an empty action list."""

        self.actions: list[str] = []

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return a deterministic empty cache summary."""

        return CivitaiCacheSummary(
            provider_record_count=1,
            thumbnail_source_count=2,
            thumbnail_variant_count=3,
            thumbnail_bytes=4,
        )

    def clear_civitai_thumbnails(self) -> None:
        """Record thumbnail clearing."""

        self.actions.append("clear-thumbnails")

    def clear_civitai_metadata(self) -> None:
        """Record metadata clearing."""

        self.actions.append("clear-metadata")


class _AboutInfoService:
    """Return deterministic About snapshots for integrated Settings tests."""

    def __init__(self) -> None:
        """Initialize with zero refresh calls."""

        self.snapshot_calls = 0

    def placeholder_snapshot(self) -> AboutInfoSnapshot:
        """Return a deterministic placeholder snapshot."""

        return _about_snapshot("placeholder")

    def snapshot(self) -> AboutInfoSnapshot:
        """Return a deterministic refreshed snapshot."""

        self.snapshot_calls += 1
        return _about_snapshot("refreshed")


def _about_snapshot(version_value: str) -> AboutInfoSnapshot:
    """Return one deterministic About snapshot for Settings tests."""

    return AboutInfoSnapshot(
        versions=(
            AboutVersionRow(
                component_key="SugarSubstitute",
                label="SugarSubstitute",
                value=version_value,
                status=AboutVersionStatus.AVAILABLE,
            ),
        ),
        project_summary="About-only project copy",
        supporters=("About-only patron",),
        special_thanks=("About-only special thanks",),
    )


def _settings_workspace(tmp_path: Path) -> Any:
    """Create an integrated Settings workspace with deterministic test services."""

    return create_settings_workspace(
        comfy_environment_service=cast(ComfyEnvironmentService, object()),
        cube_library_management_service=cast(CubeLibraryManagementService, object()),
        about_info_service=cast(AboutInfoService, _AboutInfoService()),
        localization_manager=stub_translation_manager(),
        comfy_connection_settings_service=cast(
            ComfyConnectionSettingsService,
            _ConnectionSettingsService(),
        ),
        appearance_runtime=_AppearanceRuntime(),
        appearance_restart_coordinator=cast(
            AppearanceRestartCoordinator,
            _AppearanceRestartCoordinator(),
        ),
        prompt_editor_preference_service=cast(
            PromptEditorPreferenceService,
            _PromptPreferenceService(),
        ),
        danbooru_preference_service=DanbooruPreferenceService(
            FileDanbooruPreferenceRepository(tmp_path / "danbooru-settings")
        ),
        danbooru_cache_repository=SqliteDanbooruCacheStore(tmp_path / "danbooru-cache"),
        civitai_preference_service=CivitaiPreferenceService(
            FileCivitaiPreferenceRepository(tmp_path / "civitai-settings")
        ),
        civitai_credential_service=CivitaiCredentialService(_CivitaiCredentialStore()),
        civitai_cache_service=CivitaiCacheService(_CivitaiCacheRepository()),
        generation_preview_preference_service=GenerationPreviewPreferenceService(
            _GenerationPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            _OutputOrganizationPreferenceRepository(),
            default_output_root=Path("E:/projects"),
        ),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )


def _appearance_control(
    page: SettingsPageEntry,
    setting_id: str,
) -> SettingsControlEntry:
    """Return one appearance catalog control by stable setting id."""

    for section in page.sections:
        for control in section.controls:
            if control.setting_id == setting_id:
                return control
    raise AssertionError(f"Missing appearance control: {setting_id}")


def _tall_widget(text: str) -> QWidget:
    """Return a deterministic tall section body for scroll tests."""

    widget = QLabel(text)
    widget.setMinimumHeight(360)
    return widget


def _label_texts(widget: QWidget) -> tuple[str, ...]:
    """Return all non-empty label texts below one widget."""

    return tuple(
        text for label in widget.findChildren(QLabel) if (text := label.text().strip())
    )


def _segmented_row_with_title(
    card: SettingsSegmentedCard,
    title: str,
) -> SettingsSegmentedCardRow:
    """Return the child row containing one visible title label."""

    for row in card.findChildren(SettingsSegmentedCardRow):
        if title in _label_texts(row):
            return row
    raise AssertionError(f"Missing segmented row: {title}")


def _segmented_rows(
    card: SettingsSegmentedCard,
) -> tuple[SettingsSegmentedCardRow, ...]:
    """Return the typed rows owned by one segmented settings card."""

    rows = card.rows()
    assert all(isinstance(row, SettingsSegmentedCardRow) for row in rows)
    return tuple(cast(SettingsSegmentedCardRow, row) for row in rows)


def _segmented_row_titles(card: SettingsSegmentedCard) -> tuple[str, ...]:
    """Return the visible title labels for one segmented settings card."""

    titles = []
    expected = {"Accent color", "Warning color", "Error color"}
    for row in card.findChildren(SettingsSegmentedCardRow):
        for label in row.findChildren(QLabel):
            text = label.text().strip()
            if text in expected:
                titles.append(text)
                break
    return tuple(titles)


def _assert_system_color_controls_aligned(card: SettingsSegmentedCard) -> None:
    """Assert System color trailing controls share one visual column."""

    rows = (
        _segmented_row_with_title(card, "Accent color"),
        _segmented_row_with_title(card, "Warning color"),
        _segmented_row_with_title(card, "Error color"),
    )
    combo_names = (
        "AppearanceAccentSourceCombo",
        "AppearanceWarningModeCombo",
        "AppearanceErrorModeCombo",
    )
    button_names = (
        "AppearanceAccentChooseButton",
        "AppearanceWarningChooseButton",
        "AppearanceErrorChooseButton",
    )
    swatches = tuple(
        _single_child(row, QWidget, "AppearanceColorSwatch") for row in rows
    )
    combos = tuple(
        _single_child(row, ComboBox, combo_name)
        for row, combo_name in zip(rows, combo_names, strict=True)
    )
    buttons = tuple(
        _single_child(row, PushButton, button_name)
        for row, button_name in zip(rows, button_names, strict=True)
    )

    assert (
        _mapped_x_positions(card, swatches)
        == (swatches[0].mapTo(card, QPoint()).x(),) * 3
    )
    assert (
        _mapped_x_positions(card, combos) == (combos[0].mapTo(card, QPoint()).x(),) * 3
    )
    assert (
        _mapped_x_positions(card, buttons)
        == (buttons[0].mapTo(card, QPoint()).x(),) * 3
    )


def _single_child[TWidget: QWidget](
    parent: QObject,
    widget_type: type[TWidget],
    name: str,
) -> TWidget:
    """Return one named child widget."""

    child = parent.findChild(widget_type, name)
    assert child is not None
    return child


def _mapped_x_positions(
    ancestor: QWidget,
    widgets: tuple[QWidget, ...],
) -> tuple[int, ...]:
    """Return child x positions mapped into a shared ancestor."""

    return tuple(widget.mapTo(ancestor, QPoint()).x() for widget in widgets)


def _process_events(app: QApplication) -> None:
    """Process queued Qt layout and zero-delay refresh work."""

    for _ in range(8):
        app.processEvents()


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
