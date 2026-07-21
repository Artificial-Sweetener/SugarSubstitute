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

"""Build deterministic external-service fixtures for hostile editor scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.application.danbooru import (
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptSpellcheckService,
)
from substitute.devtools.prompt_editor_performance.fakes import (
    danbooru_url_import_service,
    danbooru_wiki_service_for_scenario,
    lora_catalog,
    spellcheck_service_for_scenario,
    wildcard_gateway,
)
from substitute.devtools.prompt_editor_performance.metrics import OperationCounter
from substitute.devtools.prompt_editor_performance.scenarios import Scenario
from substitute.domain.prompt.features import PromptEditorFeature

from .models import PromptAbuseScenario


@dataclass(frozen=True, slots=True)
class PromptAbuseFixtureBundle:
    """Carry fake external boundaries required by one production mount."""

    wildcard_catalog_gateway: PromptWildcardCatalogGateway | None = None
    lora_catalog_service: PromptLoraCatalogLookup | None = None
    spellcheck_service: PromptSpellcheckService | None = None
    danbooru_import_service: DanbooruUrlImportService | None = None
    danbooru_wiki_service: DanbooruWikiContentService | None = None
    feature_profile: PromptEditorFeatureProfile | None = None


def build_fixture_bundle(scenario: PromptAbuseScenario) -> PromptAbuseFixtureBundle:
    """Return deterministic services explicitly requested by a workload."""

    features = frozenset(scenario.fixture_features)
    if not features:
        return PromptAbuseFixtureBundle()
    fixture_scenario = Scenario(
        name=scenario.name,
        initial_text=scenario.initial_text,
        wildcard_gateway=("static" if "wildcard_catalog" in features else "empty"),
        lora_catalog=("static" if "lora_catalog" in features else "empty"),
        spellcheck_enabled="spellcheck" in features,
        danbooru_import_enabled="danbooru_import" in features,
        danbooru_wiki_enabled="danbooru_wiki" in features,
        scheduled_lora_context_enabled="scheduled_lora" in features,
    )
    return PromptAbuseFixtureBundle(
        wildcard_catalog_gateway=(
            cast(
                PromptWildcardCatalogGateway,
                wildcard_gateway("static", OperationCounter()),
            )
            if "wildcard_catalog" in features
            else None
        ),
        lora_catalog_service=(
            cast(
                PromptLoraCatalogLookup,
                lora_catalog("static", OperationCounter()),
            )
            if "lora_catalog" in features
            else None
        ),
        spellcheck_service=cast(
            PromptSpellcheckService | None,
            spellcheck_service_for_scenario(fixture_scenario),
        ),
        danbooru_import_service=(
            danbooru_url_import_service() if "danbooru_import" in features else None
        ),
        danbooru_wiki_service=danbooru_wiki_service_for_scenario(fixture_scenario),
        feature_profile=PromptEditorFeatureProfile.enabled_profile(
            tuple(PromptEditorFeature)
        ),
    )


__all__ = ["PromptAbuseFixtureBundle", "build_fixture_bundle"]
