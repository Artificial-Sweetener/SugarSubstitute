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

"""Build prompt preset scope options from active model catalog metadata."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text

from dataclasses import dataclass

from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
)
from substitute.application.model_metadata.model_family_resolver import (
    model_family_associations_for_catalog_item,
)
from substitute.domain.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    UserPresetAssociation,
    UserPresetAssociationScope,
)

_LOCAL_MODEL_PROVIDER = "local"


@dataclass(frozen=True, slots=True)
class PromptPresetScopeOption:
    """Describe one save/list scope available for the active checkpoint."""

    title: ApplicationText
    full_label: ApplicationText
    association: UserPresetAssociation


def prompt_preset_scope_options_for_catalog_item(
    item: ModelCatalogItem | None,
    *,
    model_kind: str | None,
) -> tuple[PromptPresetScopeOption, ...]:
    """Return prompt preset save scopes for the active generative model."""

    options: list[PromptPresetScopeOption] = [
        PromptPresetScopeOption(
            title=app_text("Global"),
            full_label=app_text("Global"),
            association=GLOBAL_PRESET_ASSOCIATION,
        )
    ]
    for association in model_family_associations_for_catalog_item(item):
        options.append(
            PromptPresetScopeOption(
                title=association.label,
                full_label=app_text("Base model: %1", association.label),
                association=association,
            )
        )
    exact_association = exact_model_association_for_catalog_item(item)
    if exact_association is not None:
        exact_title = _exact_model_title(model_kind)
        options.append(
            PromptPresetScopeOption(
                title=exact_title,
                full_label=app_text(
                    "%1: %2",
                    exact_title,
                    exact_association.label,
                ),
                association=exact_association,
            )
        )
    return tuple(options)


def prompt_preset_listing_associations_for_catalog_item(
    item: ModelCatalogItem | None,
) -> tuple[UserPresetAssociation, ...]:
    """Return prompt preset associations ordered from most specific to broadest."""

    associations: list[UserPresetAssociation] = []
    exact_association = exact_model_association_for_catalog_item(item)
    if exact_association is not None:
        associations.append(exact_association)
    associations.extend(model_family_associations_for_catalog_item(item))
    associations.append(GLOBAL_PRESET_ASSOCIATION)
    return tuple(associations)


def exact_model_association_for_catalog_item(
    item: ModelCatalogItem | None,
) -> UserPresetAssociation | None:
    """Return the most specific stable association for one generative model."""

    if item is None:
        return None
    if item.provider_name and item.provider_model_version_id:
        return UserPresetAssociation(
            scope=UserPresetAssociationScope.PROVIDER_MODEL_VERSION,
            provider=item.provider_name,
            key=item.provider_model_version_id,
            label=_checkpoint_label(item),
        )
    local_key = _local_model_key(item)
    if local_key is None:
        return None
    return UserPresetAssociation(
        scope=UserPresetAssociationScope.LOCAL_MODEL,
        provider=_LOCAL_MODEL_PROVIDER,
        key=local_key,
        label=_checkpoint_label(item),
    )


def _checkpoint_label(item: ModelCatalogItem) -> str:
    """Return a human label for one checkpoint association."""

    if item.display_subtitle:
        return f"{item.display_name} - {item.display_subtitle}"
    return item.display_name


def _exact_model_title(model_kind: str | None) -> ApplicationText:
    """Return the compact exact-model scope title for one catalog kind."""

    if model_kind == "diffusion_models":
        return app_text("Diffusion model")
    return app_text("Checkpoint")


def _local_model_key(item: ModelCatalogItem) -> str | None:
    """Return a stable local model key for provider-less checkpoint scopes."""

    for value in (item.backend_value, item.relative_path):
        stripped = value.strip()
        if stripped:
            return stripped.replace("\\", "/").casefold()
    return None


__all__ = [
    "PromptPresetScopeOption",
    "exact_model_association_for_catalog_item",
    "prompt_preset_listing_associations_for_catalog_item",
    "prompt_preset_scope_options_for_catalog_item",
]
