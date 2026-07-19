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

"""Expose filesystem-backed persistence adapters without eager imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.infrastructure.persistence.danbooru_cache_store import (
        SqliteDanbooruCacheStore,
    )
    from substitute.infrastructure.persistence.file_appearance_preference_repository import (
        FileAppearancePreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_civitai_preference_repository import (
        FileCivitaiPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_danbooru_preference_repository import (
        FileDanbooruPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_generation_preview_preference_repository import (
        FileGenerationPreviewPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_output_preference_repository import (
        FileOutputPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_prompt_autocomplete_gateway import (
        FilePromptAutocompleteGateway,
    )
    from substitute.infrastructure.persistence.file_prompt_editor_preference_repository import (
        FilePromptEditorPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
        FilePromptWildcardCatalogGateway,
    )
    from substitute.infrastructure.persistence.file_prompt_wildcard_file_repository import (
        FilePromptWildcardFileRepository,
    )
    from substitute.infrastructure.persistence.file_prompt_wildcard_preference_repository import (
        FilePromptWildcardPreferenceRepository,
    )
    from substitute.infrastructure.persistence.file_recipe_repository import (
        FileRecipeRepository,
    )
    from substitute.infrastructure.persistence.file_restore_projection_cache import (
        FileRestoreProjectionCacheRepository,
    )
    from substitute.infrastructure.persistence.file_session_snapshot_repository import (
        FileSessionSnapshotRepository,
    )
    from substitute.infrastructure.persistence.file_startup_diagnostics_ignore_repository import (
        FileStartupDiagnosticsIgnoreRepository,
    )
    from substitute.infrastructure.persistence.file_workflow_repository import (
        FileWorkflowRepository,
    )
    from substitute.infrastructure.persistence.image_naming import (
        get_next_bucket_run_number,
        get_next_image_counter,
    )
    from substitute.infrastructure.persistence.image_store import QtImageStore
    from substitute.infrastructure.persistence.model_metadata_catalog_query_repository import (
        JsonModelMetadataCatalogQueryRepository,
    )
    from substitute.infrastructure.persistence.model_metadata_catalog_store import (
        JsonModelMetadataCatalogStore,
    )
    from substitute.infrastructure.persistence.model_thumbnail_store import (
        ModelThumbnailStore,
    )
    from substitute.infrastructure.persistence.output_run_number_allocator import (
        FileOutputRunNumberAllocator,
    )
    from substitute.infrastructure.persistence.sqlite_cube_classification_cache import (
        SqliteCubeClassificationCache,
    )
    from substitute.infrastructure.persistence.sqlite_cube_icon_cache import (
        SqliteCubeIconCache,
    )
    from substitute.infrastructure.persistence.sqlite_model_catalog_snapshot_store import (
        SqliteModelCatalogSnapshotStore,
    )
    from substitute.infrastructure.persistence.sqlite_model_metadata_store import (
        SqliteModelMetadataStore,
    )
    from substitute.infrastructure.persistence.user_presets_json_repository import (
        JsonUserPresetRepository,
    )
    from substitute.infrastructure.persistence.workflow_debug_dump import (
        dump_workflow_raw,
    )

_LAZY_EXPORTS = {
    "FileAppearancePreferenceRepository": (
        "substitute.infrastructure.persistence.file_appearance_preference_repository",
        "FileAppearancePreferenceRepository",
    ),
    "FileCivitaiPreferenceRepository": (
        "substitute.infrastructure.persistence.file_civitai_preference_repository",
        "FileCivitaiPreferenceRepository",
    ),
    "FileDanbooruPreferenceRepository": (
        "substitute.infrastructure.persistence.file_danbooru_preference_repository",
        "FileDanbooruPreferenceRepository",
    ),
    "FileGenerationPreviewPreferenceRepository": (
        "substitute.infrastructure.persistence.file_generation_preview_preference_repository",
        "FileGenerationPreviewPreferenceRepository",
    ),
    "FileOutputPreferenceRepository": (
        "substitute.infrastructure.persistence.file_output_preference_repository",
        "FileOutputPreferenceRepository",
    ),
    "FilePromptAutocompleteGateway": (
        "substitute.infrastructure.persistence.file_prompt_autocomplete_gateway",
        "FilePromptAutocompleteGateway",
    ),
    "FilePromptEditorPreferenceRepository": (
        "substitute.infrastructure.persistence.file_prompt_editor_preference_repository",
        "FilePromptEditorPreferenceRepository",
    ),
    "FilePromptWildcardCatalogGateway": (
        "substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway",
        "FilePromptWildcardCatalogGateway",
    ),
    "FilePromptWildcardFileRepository": (
        "substitute.infrastructure.persistence.file_prompt_wildcard_file_repository",
        "FilePromptWildcardFileRepository",
    ),
    "FilePromptWildcardPreferenceRepository": (
        "substitute.infrastructure.persistence.file_prompt_wildcard_preference_repository",
        "FilePromptWildcardPreferenceRepository",
    ),
    "FileRecipeRepository": (
        "substitute.infrastructure.persistence.file_recipe_repository",
        "FileRecipeRepository",
    ),
    "FileRestoreProjectionCacheRepository": (
        "substitute.infrastructure.persistence.file_restore_projection_cache",
        "FileRestoreProjectionCacheRepository",
    ),
    "FileSessionSnapshotRepository": (
        "substitute.infrastructure.persistence.file_session_snapshot_repository",
        "FileSessionSnapshotRepository",
    ),
    "FileStartupDiagnosticsIgnoreRepository": (
        "substitute.infrastructure.persistence.file_startup_diagnostics_ignore_repository",
        "FileStartupDiagnosticsIgnoreRepository",
    ),
    "FileWorkflowRepository": (
        "substitute.infrastructure.persistence.file_workflow_repository",
        "FileWorkflowRepository",
    ),
    "FileOutputRunNumberAllocator": (
        "substitute.infrastructure.persistence.output_run_number_allocator",
        "FileOutputRunNumberAllocator",
    ),
    "JsonModelMetadataCatalogQueryRepository": (
        "substitute.infrastructure.persistence.model_metadata_catalog_query_repository",
        "JsonModelMetadataCatalogQueryRepository",
    ),
    "JsonModelMetadataCatalogStore": (
        "substitute.infrastructure.persistence.model_metadata_catalog_store",
        "JsonModelMetadataCatalogStore",
    ),
    "JsonUserPresetRepository": (
        "substitute.infrastructure.persistence.user_presets_json_repository",
        "JsonUserPresetRepository",
    ),
    "ModelThumbnailStore": (
        "substitute.infrastructure.persistence.model_thumbnail_store",
        "ModelThumbnailStore",
    ),
    "QtImageStore": (
        "substitute.infrastructure.persistence.image_store",
        "QtImageStore",
    ),
    "SqliteCubeClassificationCache": (
        "substitute.infrastructure.persistence.sqlite_cube_classification_cache",
        "SqliteCubeClassificationCache",
    ),
    "SqliteCubeIconCache": (
        "substitute.infrastructure.persistence.sqlite_cube_icon_cache",
        "SqliteCubeIconCache",
    ),
    "SqliteDanbooruCacheStore": (
        "substitute.infrastructure.persistence.danbooru_cache_store",
        "SqliteDanbooruCacheStore",
    ),
    "SqliteModelCatalogSnapshotStore": (
        "substitute.infrastructure.persistence.sqlite_model_catalog_snapshot_store",
        "SqliteModelCatalogSnapshotStore",
    ),
    "SqliteModelMetadataStore": (
        "substitute.infrastructure.persistence.sqlite_model_metadata_store",
        "SqliteModelMetadataStore",
    ),
    "dump_workflow_raw": (
        "substitute.infrastructure.persistence.workflow_debug_dump",
        "dump_workflow_raw",
    ),
    "get_next_bucket_run_number": (
        "substitute.infrastructure.persistence.image_naming",
        "get_next_bucket_run_number",
    ),
    "get_next_image_counter": (
        "substitute.infrastructure.persistence.image_naming",
        "get_next_image_counter",
    ),
}


def __getattr__(name: str) -> object:
    """Load exported persistence adapters on first access."""

    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "FilePromptAutocompleteGateway",
    "FileAppearancePreferenceRepository",
    "FileCivitaiPreferenceRepository",
    "FileDanbooruPreferenceRepository",
    "FilePromptEditorPreferenceRepository",
    "FileGenerationPreviewPreferenceRepository",
    "FileOutputPreferenceRepository",
    "FilePromptWildcardCatalogGateway",
    "FilePromptWildcardFileRepository",
    "FilePromptWildcardPreferenceRepository",
    "FileStartupDiagnosticsIgnoreRepository",
    "FileRecipeRepository",
    "FileSessionSnapshotRepository",
    "FileRestoreProjectionCacheRepository",
    "FileWorkflowRepository",
    "FileOutputRunNumberAllocator",
    "JsonModelMetadataCatalogStore",
    "JsonModelMetadataCatalogQueryRepository",
    "JsonUserPresetRepository",
    "ModelThumbnailStore",
    "QtImageStore",
    "SqliteDanbooruCacheStore",
    "SqliteCubeClassificationCache",
    "SqliteCubeIconCache",
    "SqliteModelCatalogSnapshotStore",
    "SqliteModelMetadataStore",
    "dump_workflow_raw",
    "get_next_bucket_run_number",
    "get_next_image_counter",
]
