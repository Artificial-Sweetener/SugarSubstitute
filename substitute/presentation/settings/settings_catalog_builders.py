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

"""Build user-facing Settings catalog entries from application services."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from sugarsubstitute_shared.presentation.localization import (
    set_localized_placeholder,
    set_localized_text,
)
from substitute.presentation.localization import LocalizedBodyLabel, LocalizedPushButton

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
)

from substitute.application.appearance import (
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearanceRestartCoordinator,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    RgbColor,
    resolve_semantic_palette,
)
from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.danbooru import DanbooruImageRatingPolicy
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.application.onboarding import ComfyConnectionSettingsService
from substitute.application.ports.civitai_credential_store import (
    CredentialStorageUnavailableError,
)
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.presentation.dialogs import LocalizedColorDialog
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorPreferenceService,
    PromptFeatureDefinition,
    PromptWheelAdjustmentMode,
    prompt_feature_definition,
    prompt_feature_definitions,
)
from substitute.application.prompt_wildcards import (
    PromptWildcardFileManagementService,
    PromptWildcardPreferenceService,
)
from substitute.presentation.semantic_colors import legible_text_color_for_background
from substitute.presentation.settings.civitai_credential_status import (
    api_key_status_text,
)
from substitute.presentation.settings.appearance_runtime_protocol import (
    AppearanceRuntimeProtocol,
)
from substitute.presentation.settings.generation_output_settings_catalog import (
    build_generation_output_settings_section,
)
from substitute.presentation.settings.generation_preview_settings_catalog import (
    build_generation_preview_settings_section,
)
from substitute.presentation.settings.path_pattern_token_autocomplete import (
    PathPatternTokenAutocomplete,
    PathPatternTokenSuggestion,
)
from substitute.presentation.settings.prompt_editor_icons import (
    PROMPT_DANBOORU_BACKGROUND_REFRESH_SETTINGS_ICON,
    PROMPT_DANBOORU_CACHE_MAINTENANCE_SETTINGS_ICON,
    PROMPT_DANBOORU_CACHE_USAGE_SETTINGS_ICON,
    PROMPT_DANBOORU_IMAGES_SETTINGS_ICON,
    PROMPT_DANBOORU_RATINGS_SETTINGS_ICON,
    PROMPT_WHEEL_ADJUSTMENT_SETTINGS_ICON,
    PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON,
    PROMPT_WILDCARD_RESOLUTION_SETTINGS_ICON,
    prompt_feature_settings_icon,
)
from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_cache_size import format_cache_size
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
    SettingsSectionEntry,
)
from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_row_factories import (
    build_combo_settings_row as _combo_row,
    build_named_settings_icon_widget as _named_icon_widget,
    build_settings_icon_widget as _icon_widget,
    build_switch_settings_row as _switch_row,
)
from substitute.presentation.settings.settings_segmented_card import (
    SettingsSegmentedCard,
    SettingsSegmentedCardRow,
)
from substitute.presentation.resources.app_icon import AppIcon

_HIDDEN_PROMPT_FEATURES = {
    PromptEditorFeature.DANBOORU_URL_IMPORT,
    PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
}
_DANBOORU_PROMPT_FEATURES = (
    PromptEditorFeature.DANBOORU_URL_IMPORT,
    PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
)
_COMMON_PATH_KEYWORDS = ("folder", "directory", "path", "save", "location")
_IMAGE_KEYWORDS = ("image", "thumbnail", "preview", "picture")
_MODEL_KEYWORDS = ("model", "missing", "download", "resolve")
_CACHE_KEYWORDS = ("cache", "clear", "refresh", "metadata")
_THEME_KEYWORDS = ("theme", "dark", "light", "color", "accent")
_COMFY_KEYWORDS = ("server", "host", "port", "connection", "comfy")
_API_KEYWORDS = ("api", "token", "key", "credential")
_COLOR_SWATCH_SIZE = 28
_COLOR_HEX_LABEL_WIDTH = 72
_COLOR_COMBO_WIDTH = 180
_COLOR_BUTTON_WIDTH = 90


@dataclass(frozen=True, slots=True)
class GenerationSettingsContext:
    """Hold services needed by the Generation Settings catalog."""

    generation_preview_service: GenerationPreviewPreferenceService
    output_preference_service: OutputPreferenceService
    civitai_preference_service: CivitaiPreferenceService
    task_runner_factory: SettingsAsyncTaskRunnerFactory


@dataclass(frozen=True, slots=True)
class PromptEditingSettingsContext:
    """Hold services needed by the Prompt Editing Settings catalog."""

    preference_service: PromptEditorPreferenceService
    danbooru_preference_service: DanbooruPreferenceService
    danbooru_cache_repository: DanbooruCacheRepository
    wildcard_preference_service: PromptWildcardPreferenceService | None
    wildcard_file_management_service: PromptWildcardFileManagementService | None
    open_wildcard_management_modal: Callable[[QWidget | None], None] | None
    preferences_changed: Callable[[], None] | None
    open_autocomplete_list_management_modal: Callable[[QWidget | None], None] | None = (
        None
    )


@dataclass(frozen=True, slots=True)
class ModelSourcesSettingsContext:
    """Hold services needed by the Model Sources Settings catalog."""

    civitai_preference_service: CivitaiPreferenceService
    civitai_credential_service: CivitaiCredentialService
    civitai_cache_service: CivitaiCacheService


@dataclass(frozen=True, slots=True)
class AppearanceSettingsContext:
    """Hold services needed by the Appearance Settings catalog."""

    appearance_runtime: AppearanceRuntimeProtocol
    appearance_restart_coordinator: AppearanceRestartCoordinator
    show_restart_requirements: Callable[[], None] | None


@dataclass(frozen=True, slots=True)
class ComfyUiSettingsContext:
    """Hold services needed by the ComfyUI Settings catalog."""

    connection_service: ComfyConnectionSettingsService
    open_reconfigure_window: Callable[[], object]
    task_runner_factory: SettingsAsyncTaskRunnerFactory


def build_generation_settings_page(
    context: GenerationSettingsContext,
) -> SettingsPageEntry:
    """Build the Generation catalog page."""

    return SettingsPageEntry(
        page_id="generation",
        title=app_text("Generation"),
        subtitle=app_text("Generation behavior and generated files."),
        icon=AppIcon.IMAGE_SPARKLE_20_REGULAR,
        order=10,
        sections=(
            build_generation_preview_settings_section(
                context.generation_preview_service,
                context.task_runner_factory,
            ),
            build_generation_output_settings_section(context.output_preference_service),
            SettingsSectionEntry(
                "generation.missing_models",
                "Missing model handling",
                "",
                30,
                (
                    SettingsControlEntry(
                        "generation.missing_models.lookup",
                        "Look up missing recipe models",
                        "Use CivitAI only after local recipe model matching fails.",
                        _MODEL_KEYWORDS + _API_KEYWORDS,
                        10,
                        lambda parent: _civitai_missing_model_lookup_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                    SettingsControlEntry(
                        "generation.missing_models.downloads",
                        "Offer verified model downloads",
                        "Allow missing-model resolution to offer CivitAI downloads.",
                        _MODEL_KEYWORDS,
                        20,
                        lambda parent: _civitai_downloads_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "generation.model_downloads",
                "Model downloads",
                "",
                40,
                (
                    SettingsControlEntry(
                        "generation.model_downloads.pattern",
                        "Model folder pattern",
                        "Organize downloaded models inside the matching Comfy model folder.",
                        _MODEL_KEYWORDS + _COMMON_PATH_KEYWORDS,
                        10,
                        lambda parent: _civitai_download_path_pattern_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                    SettingsControlEntry(
                        "generation.model_downloads.preview",
                        "Download path preview",
                        "Shows an example model download path using the current pattern.",
                        _MODEL_KEYWORDS + _COMMON_PATH_KEYWORDS,
                        20,
                        lambda parent: _civitai_download_path_preview_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                ),
            ),
        ),
    )


def build_prompt_editing_settings_page(
    context: PromptEditingSettingsContext,
) -> SettingsPageEntry:
    """Build the Prompt Editing catalog page."""

    feature_entries = tuple(
        _prompt_feature_entry(context, definition, order)
        for order, definition in enumerate(prompt_feature_definitions(), start=10)
        if definition.feature not in _HIDDEN_PROMPT_FEATURES
    )
    return SettingsPageEntry(
        page_id="prompt_editing",
        title=app_text("Prompt Editing"),
        subtitle=app_text("Prompt editor behavior and authoring support."),
        icon=AppIcon.TEXT_EFFECTS_SPARKLE_20_REGULAR,
        order=20,
        sections=(
            SettingsSectionEntry(
                "prompt_editing.interaction",
                "Interaction",
                "",
                10,
                (
                    SettingsControlEntry(
                        "prompt_editing.interaction.wheel_hover",
                        "Wheel adjust after hover",
                        "When off, click or focus a control before the mouse wheel can change it.",
                        ("wheel", "hover", "mouse", "scroll", "focus"),
                        10,
                        lambda parent: _wheel_hover_adjustment_row(context, parent),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "prompt_editing.features",
                "Editor features",
                "",
                20,
                feature_entries,
            ),
            SettingsSectionEntry(
                "prompt_editing.autocomplete",
                "Autocomplete",
                "",
                25,
                (
                    SettingsControlEntry(
                        "prompt_editing.autocomplete.manage_lists",
                        "Manage autocomplete lists",
                        "Add custom tags and hide unwanted tag suggestions.",
                        ("autocomplete", "custom", "censor", "tags", "suggestions"),
                        10,
                        lambda parent: _autocomplete_list_management_row(
                            context, parent
                        ),
                        is_visible=lambda: (
                            context.open_autocomplete_list_management_modal is not None
                        ),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "prompt_editing.wildcards",
                "Wildcards",
                "",
                30,
                (
                    SettingsControlEntry(
                        "prompt_editing.wildcards.resolve",
                        "Resolve wildcards on generation",
                        "Expand wildcard prompt text before sending queued workflows to Comfy.",
                        ("wildcard", "prompt", "generation", "resolve"),
                        10,
                        lambda parent: _wildcard_resolution_row(context, parent),
                        is_visible=lambda: (
                            context.wildcard_preference_service is not None
                        ),
                    ),
                    SettingsControlEntry(
                        "prompt_editing.wildcards.manage",
                        "Manage wildcards",
                        "Edit user wildcard files and refresh prompt metadata.",
                        ("wildcard", "folder", "refresh", "prompt"),
                        20,
                        lambda parent: _wildcard_management_row(context, parent),
                        is_visible=lambda: (
                            context.wildcard_file_management_service is not None
                            or context.open_wildcard_management_modal is not None
                        ),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "prompt_editing.danbooru",
                "Danbooru prompt integration",
                "",
                40,
                tuple(
                    _danbooru_prompt_feature_entry(context, feature, order)
                    for order, feature in enumerate(_DANBOORU_PROMPT_FEATURES, start=10)
                ),
            ),
            SettingsSectionEntry(
                "prompt_editing.danbooru_reference",
                "Danbooru reference",
                "",
                50,
                (
                    SettingsControlEntry(
                        "prompt_editing.danbooru_reference.images",
                        "Show images in wiki viewer",
                        "Render cached Danbooru preview images inside the native wiki viewer.",
                        _IMAGE_KEYWORDS + ("danbooru", "wiki", "tag", "reference"),
                        10,
                        lambda parent: _danbooru_show_images_row(context, parent),
                    ),
                    SettingsControlEntry(
                        "prompt_editing.danbooru_reference.ratings",
                        "Allowed image ratings",
                        "Control which Danbooru ratings may render as image previews.",
                        _IMAGE_KEYWORDS
                        + ("rating", "safe", "danbooru", "wiki", "reference"),
                        20,
                        lambda parent: _danbooru_rating_policy_row(context, parent),
                    ),
                    SettingsControlEntry(
                        "prompt_editing.danbooru_reference.background_refresh",
                        "Refresh cached content in background",
                        "Refresh stale cached wiki pages and preview images lazily while browsing.",
                        _CACHE_KEYWORDS
                        + ("danbooru", "background", "wiki", "reference"),
                        30,
                        lambda parent: _danbooru_background_refresh_row(
                            context,
                            parent,
                        ),
                    ),
                    SettingsControlEntry(
                        "prompt_editing.danbooru_reference.cache_usage",
                        "Danbooru cache usage",
                        "Summarizes locally cached Danbooru metadata and preview assets.",
                        _CACHE_KEYWORDS + ("danbooru", "wiki", "reference"),
                        40,
                        lambda parent: _danbooru_cache_summary_row(context, parent),
                    ),
                    SettingsControlEntry(
                        "prompt_editing.danbooru_reference.cache_maintenance",
                        "Danbooru cache maintenance",
                        "Clear cached Danbooru entries if you want a fresh local state.",
                        _CACHE_KEYWORDS + ("danbooru", "wiki", "reference"),
                        50,
                        lambda parent: _danbooru_cache_actions_row(context, parent),
                    ),
                ),
            ),
        ),
    )


def build_model_sources_settings_page(
    context: ModelSourcesSettingsContext,
) -> SettingsPageEntry:
    """Build the Model Sources catalog page."""

    return SettingsPageEntry(
        page_id="model_sources",
        title=app_text("Model Sources"),
        subtitle=app_text("External providers, credentials, safety, and caches."),
        icon=AppIcon.GLOBE_DESKTOP_20_REGULAR,
        order=30,
        sections=(
            SettingsSectionEntry(
                "model_sources.civitai_account",
                "CivitAI account",
                "",
                10,
                (
                    SettingsControlEntry(
                        "model_sources.civitai_account.status",
                        "API key status",
                        "Used for authenticated CivitAI lookups and downloads.",
                        _API_KEYWORDS,
                        10,
                        lambda parent: _civitai_api_key_status_row(context, parent),
                    ),
                    SettingsControlEntry(
                        "model_sources.civitai_account.key",
                        "API key",
                        "The key is stored in your operating system's secure credential store.",
                        _API_KEYWORDS,
                        20,
                        lambda parent: _civitai_api_key_actions_row(context, parent),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "model_sources.civitai_lookup",
                "CivitAI lookup",
                "",
                20,
                (
                    SettingsControlEntry(
                        "model_sources.civitai_lookup.local_metadata",
                        "Look up local model metadata",
                        "Query CivitAI for hashes already known in the local model cache.",
                        _MODEL_KEYWORDS + _CACHE_KEYWORDS,
                        10,
                        lambda parent: _civitai_metadata_lookup_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "model_sources.safety",
                "Thumbnails and safety",
                "",
                30,
                (
                    SettingsControlEntry(
                        "model_sources.safety.civitai_thumbnails",
                        "Download CivitAI thumbnails",
                        "Download provider images for model picker thumbnails.",
                        _IMAGE_KEYWORDS + _MODEL_KEYWORDS,
                        10,
                        lambda parent: _civitai_thumbnail_downloads_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                    SettingsControlEntry(
                        "model_sources.safety.civitai_thumbnail_policy",
                        "Thumbnail safety",
                        "Control which CivitAI images may be used as thumbnails.",
                        _IMAGE_KEYWORDS + ("safe", "rating", "safety"),
                        20,
                        lambda parent: _civitai_thumbnail_policy_row(
                            context.civitai_preference_service,
                            parent,
                        ),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "model_sources.provider_cache",
                "Provider cache",
                "",
                40,
                (
                    SettingsControlEntry(
                        "model_sources.provider_cache.civitai_usage",
                        "CivitAI cache usage",
                        "Summarizes cached CivitAI provider metadata and thumbnails.",
                        _CACHE_KEYWORDS + ("civitai",),
                        10,
                        lambda parent: _civitai_cache_summary_row(context, parent),
                    ),
                    SettingsControlEntry(
                        "model_sources.provider_cache.civitai_maintenance",
                        "CivitAI cache maintenance",
                        "Clear or refresh CivitAI-facing cached model metadata.",
                        _CACHE_KEYWORDS + ("civitai",),
                        20,
                        lambda parent: _civitai_cache_actions_row(context, parent),
                    ),
                ),
            ),
        ),
    )


def build_appearance_settings_page(
    context: AppearanceSettingsContext,
) -> SettingsPageEntry:
    """Build the Appearance catalog page."""

    return SettingsPageEntry(
        page_id="appearance",
        title=app_text("Appearance"),
        subtitle=app_text("Visual customization."),
        icon=FIF.BRUSH,
        order=60,
        sections=(
            SettingsSectionEntry(
                "appearance.theme",
                "Theme",
                "",
                10,
                (
                    SettingsControlEntry(
                        "appearance.theme.mode",
                        "Choose your mode",
                        "Change the colors that appear in Substitute.",
                        _THEME_KEYWORDS,
                        10,
                        lambda parent: _appearance_theme_row(context, parent),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "appearance.window",
                "Window",
                "",
                20,
                (
                    SettingsControlEntry(
                        "appearance.window.material",
                        "Window material",
                        "Change the main window backdrop material.",
                        _THEME_KEYWORDS + ("window", "material", "mica", "acrylic"),
                        10,
                        lambda parent: _appearance_material_row(context, parent),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "appearance.system_colors",
                "System colors",
                "",
                30,
                (
                    SettingsControlEntry(
                        "appearance.system_colors.palette",
                        "Accent color",
                        "Choose colors used for highlights, warnings, and errors.",
                        _THEME_KEYWORDS + ("warning", "error", "system colors"),
                        10,
                        lambda parent: _appearance_system_colors_row(context, parent),
                    ),
                ),
            ),
        ),
    )


def build_comfyui_search_catalog_page(
    context: ComfyUiSettingsContext,
) -> SettingsPageEntry:
    """Build searchable ComfyUI connection metadata for static search."""

    return SettingsPageEntry(
        page_id="comfyui",
        title=app_text("ComfyUI"),
        subtitle=app_text("ComfyUI connection, installation, and Python environment."),
        icon=AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
        order=50,
        sections=(
            SettingsSectionEntry(
                "comfyui.connection",
                "Connection",
                "",
                10,
                (
                    SettingsControlEntry(
                        "comfyui.connection.editor",
                        "Connection settings",
                        "Choose the ComfyUI source, configure its folder or endpoint, and test the connection.",
                        _COMFY_KEYWORDS + _COMMON_PATH_KEYWORDS + ("setup", "wizard"),
                        10,
                        lambda parent: ComfyConnectionSettingsPage(
                            service=context.connection_service,
                            open_reconfigure_window=context.open_reconfigure_window,
                            task_runner_factory=context.task_runner_factory,
                            parent=parent,
                        ),
                    ),
                ),
            ),
            SettingsSectionEntry(
                "comfyui.environment",
                "Python environment",
                "",
                20,
                (
                    SettingsControlEntry(
                        "comfyui.environment.inventory",
                        "Installed Python packages",
                        "Use the ComfyUI page package filter to inspect installed packages and maintenance actions.",
                        _COMFY_KEYWORDS
                        + _CACHE_KEYWORDS
                        + ("python", "package", "inventory"),
                        10,
                        lambda parent: SettingsCard(
                            visual_widget=_icon_widget(FIF.DEVELOPER_TOOLS, parent),
                            title=app_text("Installed Python packages"),
                            description=(
                                app_text(
                                    "Use the ComfyUI page package filter to inspect "
                                    "installed packages and maintenance actions."
                                )
                            ),
                            reserve_visual_space=True,
                            parent=parent,
                        ),
                    ),
                ),
            ),
        ),
    )


def _prompt_feature_entry(
    context: PromptEditingSettingsContext,
    definition: PromptFeatureDefinition,
    order: int,
) -> SettingsControlEntry:
    """Return one prompt editor feature catalog row."""

    return SettingsControlEntry(
        setting_id=f"prompt_editing.features.{definition.feature.value}",
        title=definition.label,
        description=definition.description,
        keywords=("prompt", "editor", "feature", definition.feature.value),
        order=order,
        factory=lambda parent: _prompt_feature_row(context, definition, parent),
    )


def _danbooru_prompt_feature_entry(
    context: PromptEditingSettingsContext,
    feature: PromptEditorFeature,
    order: int,
) -> SettingsControlEntry:
    """Return one Danbooru prompt integration catalog row."""

    definition = prompt_feature_definition(feature)
    return SettingsControlEntry(
        setting_id=f"prompt_editing.danbooru.{feature.value}",
        title=definition.label,
        description=definition.description,
        keywords=("prompt", "danbooru", "wiki", "url", feature.value),
        order=order,
        factory=lambda parent: _prompt_feature_row(context, definition, parent),
    )


def _civitai_missing_model_lookup_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the missing-model lookup toggle row."""

    return _switch_row(
        parent=parent,
        icon=AppIcon.BOX_SEARCH_20_REGULAR,
        title=app_text("Look up missing recipe models"),
        description=app_text(
            "Use CivitAI only after local recipe model matching fails."
        ),
        checked=service.load_preferences().missing_model_lookup_enabled,
        on_changed=service.set_missing_model_lookup_enabled,
    )


def _civitai_downloads_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the verified model downloads toggle row."""

    return _switch_row(
        parent=parent,
        icon=AppIcon.ARROW_DOWNLOAD_20_REGULAR,
        title=app_text("Offer verified model downloads"),
        description=app_text(
            "Allow missing-model resolution to offer CivitAI downloads."
        ),
        checked=service.load_preferences().downloads_enabled,
        on_changed=service.set_downloads_enabled,
    )


def _civitai_download_path_pattern_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the model download path pattern row."""

    edit = LineEdit(parent)
    edit.setObjectName("CivitaiDownloadPathPatternEdit")
    configure_settings_field_width(edit, preferred_width=360)
    edit.setText(service.load_preferences().download_path_pattern)
    PathPatternTokenAutocomplete(
        edit,
        tuple(
            PathPatternTokenSuggestion(
                token=token.placeholder, description=token.description
            )
            for token in service.supported_download_path_token_descriptions()
        ),
    )
    edit.editingFinished.connect(lambda: service.set_download_path_pattern(edit.text()))
    return SettingsCard(
        visual_widget=_icon_widget(AppIcon.FOLDER_OPEN_20_REGULAR, parent),
        title=app_text("Model folder pattern"),
        description=app_text(
            "Organize downloaded models inside the matching Comfy model folder."
        ),
        trailing_widget=SettingsControlGroup(edit, parent=parent),
        reserve_visual_space=True,
        wrap_threshold=640,
        parent=parent,
    )


def _civitai_download_path_preview_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the model download path preview row."""

    edit = LineEdit(parent)
    edit.setObjectName("CivitaiDownloadPathPreviewEdit")
    edit.setReadOnly(True)
    configure_settings_field_width(edit, preferred_width=420)
    try:
        edit.setText(
            service.render_download_path_preview(
                service.load_preferences()
            ).display_path
        )
    except Exception as error:
        edit.setText(str(error))
    return SettingsCard(
        visual_widget=_icon_widget(AppIcon.DOCUMENT_TEXT_20_REGULAR, parent),
        title=app_text("Download path preview"),
        description=app_text("Shows an example path using the current pattern."),
        trailing_widget=SettingsControlGroup(edit, parent=parent),
        reserve_visual_space=True,
        wrap_threshold=680,
        parent=parent,
    )


def _wheel_hover_adjustment_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the wheel hover adjustment row."""

    preferences = context.preference_service.load_preferences()
    return _switch_row(
        parent=parent,
        icon=PROMPT_WHEEL_ADJUSTMENT_SETTINGS_ICON,
        title=app_text("Wheel adjust after hover"),
        description=app_text(
            "When off, click or focus a control before the mouse wheel can change it."
        ),
        checked=preferences.wheel_adjustment_mode
        is PromptWheelAdjustmentMode.HOVER_DWELL,
        on_changed=lambda enabled: _set_wheel_adjustment(context, enabled),
    )


def _prompt_feature_row(
    context: PromptEditingSettingsContext,
    definition: PromptFeatureDefinition,
    parent: QWidget,
) -> SettingsCard:
    """Create one prompt editor feature toggle row."""

    preferences = context.preference_service.load_preferences()
    return _switch_row(
        parent=parent,
        icon=prompt_feature_settings_icon(definition.feature),
        title=definition.label,
        description=definition.description,
        checked=preferences.user_allows(definition.feature),
        on_changed=lambda enabled: _set_prompt_feature(
            context,
            definition.feature,
            enabled,
        ),
    )


def _wildcard_resolution_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the wildcard resolution toggle row."""

    service = context.wildcard_preference_service
    assert service is not None
    return _switch_row(
        parent=parent,
        icon=PROMPT_WILDCARD_RESOLUTION_SETTINGS_ICON,
        title=app_text("Resolve wildcards on generation"),
        description=app_text(
            "Expand wildcard prompt text before sending queued workflows to Comfy."
        ),
        checked=service.load_preferences().resolve_on_generation,
        on_changed=service.set_resolve_on_generation,
    )


def _autocomplete_list_management_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the custom and censored autocomplete list action row."""

    manage_button = LocalizedPushButton(app_text("Manage"), parent)
    opener = context.open_autocomplete_list_management_modal
    if opener is not None:
        manage_button.clicked.connect(lambda: opener(parent))
    else:
        manage_button.setEnabled(False)
    return SettingsCard(
        visual_widget=_icon_widget(PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON, parent),
        title=app_text("Manage autocomplete lists"),
        description=app_text("Add custom tags and hide unwanted tag suggestions."),
        trailing_widget=SettingsControlGroup(manage_button, parent=parent),
        reserve_visual_space=True,
        parent=parent,
    )


def _wildcard_management_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the wildcard management action row."""

    manage_button = LocalizedPushButton(app_text("Manage"), parent)
    open_button = LocalizedPushButton(app_text("Open folder"), parent)
    refresh_button = LocalizedPushButton(app_text("Refresh"), parent)
    if context.open_wildcard_management_modal is not None:
        manage_button.clicked.connect(
            lambda: context.open_wildcard_management_modal(parent)
        )
    else:
        manage_button.setEnabled(False)
    if context.wildcard_file_management_service is not None:
        open_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(context.wildcard_file_management_service.root_path())
                )
            )
        )
        refresh_button.clicked.connect(
            context.wildcard_file_management_service.refresh_cache
        )
    else:
        open_button.setEnabled(False)
        refresh_button.setEnabled(False)
    return SettingsCard(
        visual_widget=_icon_widget(PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON, parent),
        title=app_text("Manage wildcards"),
        description=app_text("Edit user wildcard files and refresh prompt metadata."),
        trailing_widget=SettingsControlGroup(
            manage_button,
            open_button,
            refresh_button,
            parent=parent,
        ),
        reserve_visual_space=True,
        parent=parent,
    )


def _set_prompt_feature(
    context: PromptEditingSettingsContext,
    feature: PromptEditorFeature,
    enabled: bool,
) -> None:
    """Persist one prompt feature and notify callers."""

    context.preference_service.set_feature_allowed(feature, enabled)
    if context.preferences_changed is not None:
        context.preferences_changed()


def _set_wheel_adjustment(
    context: PromptEditingSettingsContext,
    enabled: bool,
) -> None:
    """Persist wheel adjustment policy and notify callers."""

    context.preference_service.set_wheel_adjustment_mode(
        PromptWheelAdjustmentMode.HOVER_DWELL
        if enabled
        else PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    if context.preferences_changed is not None:
        context.preferences_changed()


def _civitai_metadata_lookup_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI local metadata lookup row."""

    return _switch_row(
        parent=parent,
        icon=AppIcon.DATABASE_SEARCH_20_REGULAR,
        title=app_text("Look up local model metadata"),
        description=app_text(
            "Query CivitAI for hashes already known in the local model cache."
        ),
        checked=service.load_preferences().metadata_lookup_enabled,
        on_changed=service.set_metadata_lookup_enabled,
    )


def _civitai_thumbnail_downloads_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI thumbnail download toggle row."""

    return _switch_row(
        parent=parent,
        icon=AppIcon.IMAGE_MULTIPLE_20_REGULAR,
        title=app_text("Download CivitAI thumbnails"),
        description=app_text("Download provider images for model picker thumbnails."),
        checked=service.load_preferences().thumbnail_downloads_enabled,
        on_changed=service.set_thumbnail_downloads_enabled,
    )


def _civitai_thumbnail_policy_row(
    service: CivitaiPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI thumbnail safety row."""

    preferences = service.load_preferences()
    return _combo_row(
        parent=parent,
        icon=AppIcon.SHIELD_CHECKMARK_20_REGULAR,
        title=app_text("Thumbnail safety"),
        description=app_text("Control which CivitAI images may be used as thumbnails."),
        options=(
            ("Disabled", "disabled"),
            ("SFW only", "sfw_only"),
            ("Allow soft", "allow_soft"),
            ("Allow all", "allow_all"),
        ),
        selected=preferences.thumbnail_safety_policy.value,
        on_changed=lambda value: service.set_thumbnail_safety_policy_value(str(value)),
        enabled=preferences.thumbnail_downloads_enabled,
    )


def _civitai_api_key_status_row(
    context: ModelSourcesSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI API key status row."""

    status = context.civitai_credential_service.storage_status()
    has_key = (
        context.civitai_credential_service.has_api_key() if status.available else False
    )
    return SettingsCard(
        visual_widget=_icon_widget(
            AppIcon.PLUG_CONNECTED_CHECKMARK_20_REGULAR,
            parent,
        ),
        title=app_text("API key status"),
        description=app_text("Used for authenticated CivitAI lookups and downloads."),
        trailing_widget=SettingsControlGroup(
            LocalizedBodyLabel(
                api_key_status_text(status=status, has_key=has_key), parent
            ),
            parent=parent,
        ),
        reserve_visual_space=True,
        wrap_threshold=680,
        parent=parent,
    )


def _civitai_api_key_actions_row(
    context: ModelSourcesSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI API key action row."""

    edit = LineEdit(parent)
    set_localized_placeholder(edit, "Paste CivitAI API key")
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    configure_settings_field_width(edit, preferred_width=320)
    set_button = LocalizedPushButton(app_text("Set/update"), parent)
    test_button = LocalizedPushButton(app_text("Test"), parent)
    clear_button = LocalizedPushButton(app_text("Clear"), parent)
    status_label = BodyLabel("", parent)
    storage_status = context.civitai_credential_service.storage_status()
    set_button.setEnabled(storage_status.available)
    clear_button.setEnabled(storage_status.available)

    def set_api_key() -> None:
        key = edit.text().strip()
        if not key:
            set_localized_text(status_label, "Enter an API key first")
            return
        try:
            context.civitai_credential_service.save_api_key(key)
        except CredentialStorageUnavailableError as error:
            status_label.setText(str(error))
            return
        set_localized_text(status_label, "Configured")
        edit.clear()

    set_button.clicked.connect(set_api_key)
    test_button.clicked.connect(
        lambda: status_label.setText(
            context.civitai_credential_service.test_api_key(
                edit.text().strip() or None
            ).message
        )
    )

    def clear_api_key() -> None:
        """Clear the stored API key and update inline status."""

        context.civitai_credential_service.clear_api_key()
        set_localized_text(status_label, "No API key configured")

    clear_button.clicked.connect(clear_api_key)
    return SettingsCard(
        visual_widget=_icon_widget(AppIcon.KEY_20_REGULAR, parent),
        title=app_text("API key"),
        description=app_text(
            "The key is stored in your operating system's secure credential store."
        ),
        trailing_widget=SettingsControlGroup(
            edit,
            set_button,
            test_button,
            clear_button,
            status_label,
            spacing=6,
            parent=parent,
        ),
        reserve_visual_space=True,
        wrap_threshold=780,
        parent=parent,
    )


def _civitai_cache_summary_row(
    context: ModelSourcesSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI cache summary row."""

    summary = context.civitai_cache_service.cache_summary()
    label = BodyLabel("", parent)
    set_localized_text(
        label,
        "%1 provider records, %2 thumbnail sources, %3 variants, %4",
        summary.provider_record_count,
        summary.thumbnail_source_count,
        summary.thumbnail_variant_count,
        format_cache_size(summary.thumbnail_bytes),
    )
    return SettingsCard(
        visual_widget=_icon_widget(AppIcon.DATABASE_SEARCH_20_REGULAR, parent),
        title=app_text("CivitAI cache usage"),
        description=app_text(
            "Summarizes cached CivitAI provider metadata and thumbnails."
        ),
        trailing_widget=SettingsControlGroup(label, parent=parent),
        reserve_visual_space=True,
        wrap_threshold=680,
        parent=parent,
    )


def _civitai_cache_actions_row(
    context: ModelSourcesSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the CivitAI cache action row."""

    clear_thumbnails_button = LocalizedPushButton(app_text("Clear thumbnails"), parent)
    clear_metadata_button = LocalizedPushButton(app_text("Clear metadata"), parent)
    refresh_button = LocalizedPushButton(app_text("Refresh"), parent)
    clear_thumbnails_button.clicked.connect(
        context.civitai_cache_service.clear_civitai_thumbnails
    )
    clear_metadata_button.clicked.connect(
        context.civitai_cache_service.clear_civitai_metadata
    )
    refresh_button.clicked.connect(
        context.civitai_cache_service.refresh_civitai_metadata
    )
    return SettingsCard(
        visual_widget=_icon_widget(AppIcon.BROOM_20_REGULAR, parent),
        title=app_text("CivitAI cache maintenance"),
        description=app_text("Clear or refresh CivitAI-facing cached model metadata."),
        trailing_widget=SettingsControlGroup(
            clear_thumbnails_button,
            clear_metadata_button,
            refresh_button,
            spacing=6,
            parent=parent,
        ),
        reserve_visual_space=True,
        wrap_threshold=720,
        parent=parent,
    )


def _danbooru_show_images_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the Danbooru wiki image toggle row."""

    return _switch_row(
        parent=parent,
        icon=PROMPT_DANBOORU_IMAGES_SETTINGS_ICON,
        title=app_text("Show images in wiki viewer"),
        description=app_text(
            "Render cached Danbooru preview images inside the native wiki viewer."
        ),
        checked=context.danbooru_preference_service.load_preferences().show_wiki_images,
        on_changed=context.danbooru_preference_service.set_show_wiki_images,
    )


def _danbooru_rating_policy_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the Danbooru rating policy row."""

    preferences = context.danbooru_preference_service.load_preferences()
    return _combo_row(
        parent=parent,
        icon=PROMPT_DANBOORU_RATINGS_SETTINGS_ICON,
        title=app_text("Allowed image ratings"),
        description=app_text(
            "Control which Danbooru ratings may render as image previews."
        ),
        options=(
            ("Safe only", DanbooruImageRatingPolicy.SAFE_ONLY.value),
            (
                "Safe + Questionable",
                DanbooruImageRatingPolicy.SAFE_AND_QUESTIONABLE.value,
            ),
            ("All ratings", DanbooruImageRatingPolicy.ALL_RATINGS.value),
        ),
        selected=preferences.allowed_image_ratings.value,
        on_changed=lambda value: (
            context.danbooru_preference_service.set_allowed_image_ratings(
                DanbooruImageRatingPolicy(str(value))
            )
        ),
        enabled=preferences.show_wiki_images,
    )


def _danbooru_background_refresh_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the Danbooru background refresh row."""

    return _switch_row(
        parent=parent,
        icon=PROMPT_DANBOORU_BACKGROUND_REFRESH_SETTINGS_ICON,
        title=app_text("Refresh cached content in background"),
        description=app_text(
            "Refresh stale cached wiki pages and preview images lazily while browsing."
        ),
        checked=context.danbooru_preference_service.load_preferences().background_refresh_enabled,
        on_changed=context.danbooru_preference_service.set_background_refresh_enabled,
    )


def _danbooru_cache_summary_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the Danbooru cache summary row."""

    summary = context.danbooru_cache_repository.cache_summary()
    summary_label = BodyLabel("", parent)
    set_localized_text(
        summary_label,
        "%1 metadata entries, %2 image previews, %3",
        summary.metadata_entry_count,
        summary.image_entry_count,
        format_cache_size(summary.image_bytes),
    )
    return SettingsCard(
        visual_widget=_icon_widget(PROMPT_DANBOORU_CACHE_USAGE_SETTINGS_ICON, parent),
        title=app_text("Danbooru cache usage"),
        description=app_text(
            "Summarizes locally cached Danbooru metadata and preview assets."
        ),
        trailing_widget=SettingsControlGroup(
            summary_label,
            parent=parent,
        ),
        reserve_visual_space=True,
        wrap_threshold=680,
        parent=parent,
    )


def _danbooru_cache_actions_row(
    context: PromptEditingSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the Danbooru cache action row."""

    clear_text_button = LocalizedPushButton(app_text("Clear text cache"), parent)
    clear_image_button = LocalizedPushButton(app_text("Clear image cache"), parent)
    clear_all_button = LocalizedPushButton(app_text("Clear all"), parent)
    clear_text_button.clicked.connect(
        context.danbooru_cache_repository.clear_text_cache
    )
    clear_image_button.clicked.connect(
        context.danbooru_cache_repository.clear_image_cache
    )
    clear_all_button.clicked.connect(context.danbooru_cache_repository.clear_all_cache)
    return SettingsCard(
        visual_widget=_icon_widget(
            PROMPT_DANBOORU_CACHE_MAINTENANCE_SETTINGS_ICON,
            parent,
        ),
        title=app_text("Danbooru cache maintenance"),
        description=app_text(
            "Clear cached Danbooru entries if you want a fresh local state."
        ),
        trailing_widget=SettingsControlGroup(
            clear_text_button,
            clear_image_button,
            clear_all_button,
            spacing=6,
            parent=parent,
        ),
        reserve_visual_space=True,
        wrap_threshold=720,
        parent=parent,
    )


def _appearance_theme_row(
    context: AppearanceSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the appearance theme row."""

    resolved = context.appearance_runtime.resolve_preferences()
    return _combo_row(
        parent=parent,
        icon=FIF.BRUSH,
        title=app_text("Choose your mode"),
        description=app_text("Change the colors that appear in Substitute."),
        options=(
            ("Light", AppearanceThemeMode.LIGHT),
            ("Dark", AppearanceThemeMode.DARK),
            ("Auto", AppearanceThemeMode.AUTO),
        ),
        selected=resolved.requested.theme_mode,
        on_changed=lambda value: _save_theme_mode(context, value),
    )


def _save_theme_mode(context: AppearanceSettingsContext, value: object) -> object:
    """Persist one theme mode through the restart-required appearance owner."""

    snapshot = context.appearance_restart_coordinator.set_theme_mode(
        value if isinstance(value, AppearanceThemeMode) else AppearanceThemeMode.AUTO
    )
    _show_restart_requirements_if_pending(context, snapshot.count)
    return snapshot


def _appearance_system_colors_row(
    context: AppearanceSettingsContext,
    parent: QWidget,
) -> SettingsSegmentedCard:
    """Create the segmented system color settings card."""

    control = _SystemColorSettingsControl(context=context, parent=parent)
    return control.card()


class _ColorSwatch(QWidget):
    """Render one compact Fluent color preview square."""

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        """Create a fixed-size color preview."""

        super().__init__(parent)
        self._color = color
        self.setFixedSize(QSize(_COLOR_SWATCH_SIZE, _COLOR_SWATCH_SIZE))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("AppearanceColorSwatch")
        self.set_color(color)

    def set_color(self, color: str) -> None:
        """Apply the preview color."""

        self._color = color
        text_color = legible_text_color_for_background(QColor(color)).name()
        self.setStyleSheet(
            "QWidget#AppearanceColorSwatch {"
            f"background-color: {color};"
            f"color: {text_color};"
            "border-radius: 5px;"
            "border: 1px solid rgba(128, 128, 128, 120);"
            "}"
        )

    def color(self) -> str:
        """Return the currently displayed preview color."""

        return self._color


class _ColorPreviewControls(QWidget):
    """Arrange a swatch, hex label, mode combo, and color action for one row."""

    def __init__(
        self,
        *,
        color: str,
        mode_options: tuple[tuple[str, object], ...],
        mode_combo_name: str,
        choose_button_name: str,
        parent: QWidget,
    ) -> None:
        """Create one Settings trailing control group for color editing."""

        super().__init__(parent)
        self.swatch = _ColorSwatch(color, self)
        self.hex_label = BodyLabel(color, self)
        self.hex_label.setFixedWidth(_COLOR_HEX_LABEL_WIDTH)
        self.mode_combo = ComboBox(self)
        self.mode_combo.setObjectName(mode_combo_name)
        for label, value in mode_options:
            self.mode_combo.addItem(label, userData=value)
        configure_settings_field_width(
            self.mode_combo,
            preferred_width=_COLOR_COMBO_WIDTH,
        )
        self.choose_button = LocalizedPushButton(app_text("Choose"), self)
        self.choose_button.setObjectName(choose_button_name)
        self.choose_button.setFixedWidth(_COLOR_BUTTON_WIDTH)
        widgets: list[QWidget] = [
            self.swatch,
            self.hex_label,
            self.mode_combo,
            self.choose_button,
        ]
        self._controls = SettingsControlGroup(*widgets, parent=self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._controls)

    def set_color(self, color: str) -> None:
        """Update the visible swatch and hex label."""

        self.swatch.set_color(color)
        self.hex_label.setText(color)

    def set_settings_card_layout_mode(self, mode: str) -> None:
        """Forward Settings card wrap mode to the compound controls."""

        setter = getattr(self._controls, "set_settings_card_layout_mode", None)
        if callable(setter):
            setter(mode)


class _SystemColorSettingsControl:
    """Own the segmented Appearance system-color settings control."""

    def __init__(
        self,
        *,
        context: AppearanceSettingsContext,
        parent: QWidget,
    ) -> None:
        """Create the segmented card and bind it to appearance preferences."""

        self._context = context
        self._parent = parent
        self._accent_source_combo = ComboBox(parent)
        self._accent_source_combo.setObjectName("AppearanceAccentSourceCombo")
        configure_settings_field_width(
            self._accent_source_combo,
            preferred_width=_COLOR_COMBO_WIDTH,
        )
        for label, value in (
            ("Custom", AppearanceAccentSource.CUSTOM),
            ("System", AppearanceAccentSource.SYSTEM),
        ):
            self._accent_source_combo.addItem(label, userData=value)
        self._accent_swatch = _ColorSwatch("#000000", parent)
        self._accent_hex_label = BodyLabel("#000000", parent)
        self._accent_hex_label.setFixedWidth(_COLOR_HEX_LABEL_WIDTH)
        self._choose_accent_button = LocalizedPushButton(app_text("Choose"), parent)
        self._choose_accent_button.setObjectName("AppearanceAccentChooseButton")
        self._choose_accent_button.setFixedWidth(_COLOR_BUTTON_WIDTH)
        accent_trailing = SettingsControlGroup(
            self._accent_swatch,
            self._accent_hex_label,
            self._accent_source_combo,
            self._choose_accent_button,
            parent=parent,
        )
        self._card = SettingsSegmentedCard(parent=parent)
        setattr(self._card, "_system_color_settings_control", self)
        self._card.add_row(
            SettingsSegmentedCardRow(
                title=app_text("Accent color"),
                description=app_text(
                    "Choose the color used for highlights and selected controls."
                ),
                visual_widget=_icon_widget(FIF.PALETTE, self._card),
                trailing_widget=accent_trailing,
                parent=self._card,
            )
        )
        self._warning_controls = _ColorPreviewControls(
            color="#000000",
            mode_options=(
                ("Derived", AppearanceWarningColorMode.DEFAULT),
                ("Yellow", AppearanceWarningColorMode.YELLOW),
                ("Custom", AppearanceWarningColorMode.CUSTOM),
            ),
            mode_combo_name="AppearanceWarningModeCombo",
            choose_button_name="AppearanceWarningChooseButton",
            parent=self._card,
        )
        self._error_controls = _ColorPreviewControls(
            color="#000000",
            mode_options=(
                ("Derived", AppearanceErrorColorMode.DEFAULT),
                ("Red", AppearanceErrorColorMode.RED),
                ("Custom", AppearanceErrorColorMode.CUSTOM),
            ),
            mode_combo_name="AppearanceErrorModeCombo",
            choose_button_name="AppearanceErrorChooseButton",
            parent=self._card,
        )
        self._card.add_row(
            SettingsSegmentedCardRow(
                title=app_text("Warning color"),
                description=app_text("Used for caution states and warning highlights."),
                visual_widget=_named_icon_widget(
                    FIF.INFO,
                    "AppearanceWarningColorIcon",
                    self._card,
                ),
                trailing_widget=self._warning_controls,
                parent=self._card,
            )
        )
        self._card.add_row(
            SettingsSegmentedCardRow(
                title=app_text("Error color"),
                description=app_text(
                    "Used for validation failures and error highlights."
                ),
                visual_widget=_named_icon_widget(
                    FIF.CLOSE,
                    "AppearanceErrorColorIcon",
                    self._card,
                ),
                trailing_widget=self._error_controls,
                parent=self._card,
            )
        )
        self._accent_source_combo.currentIndexChanged.connect(
            self._on_accent_source_changed
        )
        self._warning_controls.mode_combo.currentIndexChanged.connect(
            self._on_warning_mode_changed
        )
        self._error_controls.mode_combo.currentIndexChanged.connect(
            self._on_error_mode_changed
        )
        self._choose_accent_button.clicked.connect(self._choose_accent_color)
        self._warning_controls.choose_button.clicked.connect(self._choose_warning_color)
        self._error_controls.choose_button.clicked.connect(self._choose_error_color)
        self._sync_from_runtime()

    def card(self) -> SettingsSegmentedCard:
        """Return the configured segmented settings card."""

        return self._card

    def _on_accent_source_changed(self, _index: int) -> None:
        """Persist and apply one selected accent source."""

        selected = _combo_data(self._accent_source_combo, AppearanceAccentSource)
        if selected is None:
            return
        self._context.appearance_runtime.set_accent_source(selected)
        self._sync_from_runtime()

    def _on_warning_mode_changed(self, _index: int) -> None:
        """Persist the selected warning color mode."""

        selected = _combo_data(
            self._warning_controls.mode_combo,
            AppearanceWarningColorMode,
        )
        if selected is None:
            return
        preferences = self._context.appearance_runtime.load_preferences()
        if selected is AppearanceWarningColorMode.CUSTOM:
            if preferences.custom_warning_color is None:
                self._context.appearance_runtime.set_custom_warning_color(
                    self._effective_preview_colors().warning
                )
            else:
                self._context.appearance_runtime.set_warning_color_mode(selected)
        else:
            self._context.appearance_runtime.set_warning_color_mode(selected)
        self._sync_from_runtime()

    def _on_error_mode_changed(self, _index: int) -> None:
        """Persist the selected error color mode."""

        selected = _combo_data(
            self._error_controls.mode_combo,
            AppearanceErrorColorMode,
        )
        if selected is None:
            return
        preferences = self._context.appearance_runtime.load_preferences()
        if selected is AppearanceErrorColorMode.CUSTOM:
            if preferences.custom_error_color is None:
                self._context.appearance_runtime.set_custom_error_color(
                    self._effective_preview_colors().error
                )
            else:
                self._context.appearance_runtime.set_error_color_mode(selected)
        else:
            self._context.appearance_runtime.set_error_color_mode(selected)
        self._sync_from_runtime()

    def _choose_accent_color(self) -> None:
        """Open the color picker for the custom accent color."""

        resolved = self._context.appearance_runtime.resolve_preferences()
        self._open_color_dialog(
            initial_color=resolved.requested.custom_accent_color,
            changed=lambda color: (
                self._context.appearance_runtime.set_custom_accent_color(color)
            ),
        )

    def _choose_warning_color(self) -> None:
        """Open the color picker for the warning color override."""

        preview = self._effective_preview_colors()
        initial = (
            self._context.appearance_runtime.load_preferences().custom_warning_color
            or preview.warning
        )
        self._open_color_dialog(
            initial_color=initial,
            changed=lambda color: (
                self._context.appearance_runtime.set_custom_warning_color(color)
            ),
        )

    def _choose_error_color(self) -> None:
        """Open the color picker for the error color override."""

        preview = self._effective_preview_colors()
        initial = (
            self._context.appearance_runtime.load_preferences().custom_error_color
            or preview.error
        )
        self._open_color_dialog(
            initial_color=initial,
            changed=lambda color: (
                self._context.appearance_runtime.set_custom_error_color(color)
            ),
        )

    def _open_color_dialog(
        self,
        *,
        initial_color: str,
        changed: Callable[[str], object],
    ) -> None:
        """Open the localized QFluent color dialog and apply selections live."""

        dialog = LocalizedColorDialog(
            QColor(initial_color),
            app_text("Choose color"),
            self._parent.window(),
        )

        def apply_color(color: QColor) -> None:
            """Persist one color emitted by the color picker."""

            changed(color.name(QColor.NameFormat.HexRgb).upper())
            self._sync_from_runtime()

        dialog.colorChanged.connect(apply_color)
        dialog.exec()

    def _sync_from_runtime(self) -> None:
        """Refresh controls from persisted and resolved appearance preferences."""

        resolved = self._context.appearance_runtime.resolve_preferences()
        requested = resolved.requested
        _set_combo_data(self._accent_source_combo, requested.accent_source)
        preview = self._effective_preview_colors()
        self._accent_swatch.set_color(resolved.effective_accent_color)
        self._accent_hex_label.setText(resolved.effective_accent_color)
        self._warning_controls.set_color(preview.warning)
        self._error_controls.set_color(preview.error)
        self._choose_accent_button.setEnabled(
            resolved.effective_accent_source is AppearanceAccentSource.CUSTOM
        )
        _set_combo_data(
            self._warning_controls.mode_combo,
            requested.warning_color_mode,
        )
        _set_combo_data(
            self._error_controls.mode_combo,
            requested.error_color_mode,
        )
        self._warning_controls.choose_button.setEnabled(
            requested.warning_color_mode is AppearanceWarningColorMode.CUSTOM
        )
        self._error_controls.choose_button.setEnabled(
            requested.error_color_mode is AppearanceErrorColorMode.CUSTOM
        )

    def _effective_preview_colors(self) -> "_SystemColorPreview":
        """Return current effective warning and error color previews."""

        resolved = self._context.appearance_runtime.resolve_preferences()
        accent = QColor(resolved.effective_accent_color)
        palette = resolve_semantic_palette(
            accent=RgbColor(accent.red(), accent.green(), accent.blue()),
            dark_theme=_is_dark_theme(),
            warning_color_mode=resolved.requested.warning_color_mode,
            error_color_mode=resolved.requested.error_color_mode,
            custom_warning_color=resolved.requested.custom_warning_color,
            custom_error_color=resolved.requested.custom_error_color,
        )
        return _SystemColorPreview(
            warning=palette.warning_foreground.to_hex(),
            error=palette.error_foreground.to_hex(),
        )


@dataclass(frozen=True, slots=True)
class _SystemColorPreview:
    """Capture effective semantic color previews for the settings UI."""

    warning: str
    error: str


def _is_dark_theme() -> bool:
    """Return the active QFluent theme darkness for preview derivation."""

    try:
        from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
    except ImportError:
        return False

    return bool(isDarkTheme())


def _combo_data[TValue](combo: ComboBox, value_type: type[TValue]) -> TValue | None:
    """Return current combo data when it matches the expected type."""

    value = combo.currentData()
    if isinstance(value, value_type):
        return value
    return None


def _set_combo_data(combo: ComboBox, value: object) -> None:
    """Select one combo item by stored user data without emitting callbacks."""

    previous = combo.blockSignals(True)
    try:
        index = _combo_index_for_data(combo, value)
        if index >= 0:
            combo.setCurrentIndex(index)
    finally:
        combo.blockSignals(previous)


def _combo_index_for_data(combo: ComboBox, value: object) -> int:
    """Return the first combo index with matching user data."""

    for index in range(combo.count()):
        if combo.itemData(index) == value:
            return index
    return -1


def _appearance_material_row(
    context: AppearanceSettingsContext,
    parent: QWidget,
) -> SettingsCard:
    """Create the appearance window material row."""

    resolved = context.appearance_runtime.resolve_preferences()
    return _combo_row(
        parent=parent,
        icon=FIF.BACKGROUND_FILL,
        title=app_text("Window material"),
        description=app_text("Change the main window backdrop material."),
        options=(
            ("Mica", AppearanceBackdropMode.MICA_ALT),
            ("Acrylic", AppearanceBackdropMode.ACRYLIC),
        ),
        selected=resolved.requested.backdrop_mode,
        on_changed=lambda value: _save_backdrop_mode(context, value),
    )


def _save_backdrop_mode(context: AppearanceSettingsContext, value: object) -> object:
    """Persist one backdrop mode through the restart-required appearance owner."""

    snapshot = context.appearance_restart_coordinator.set_backdrop_mode(
        value
        if isinstance(value, AppearanceBackdropMode)
        else AppearanceBackdropMode.MICA_ALT
    )
    _show_restart_requirements_if_pending(context, snapshot.count)
    return snapshot


def _show_restart_requirements_if_pending(
    context: AppearanceSettingsContext,
    count: int,
) -> None:
    """Open the shared restart dialog after a change leaves pending work."""

    if count > 0 and context.show_restart_requirements is not None:
        context.show_restart_requirements()


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


__all__ = [
    "AppearanceSettingsContext",
    "ComfyUiSettingsContext",
    "GenerationSettingsContext",
    "ModelSourcesSettingsContext",
    "PromptEditingSettingsContext",
    "build_appearance_settings_page",
    "build_comfyui_search_catalog_page",
    "build_generation_settings_page",
    "build_model_sources_settings_page",
    "build_prompt_editing_settings_page",
]
