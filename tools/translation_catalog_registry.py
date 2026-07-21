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

"""Resolve authored and compiled catalogs from the production locale registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sugarsubstitute_shared.localization import (
    LanguageDefinition,
    LanguageManifest,
    load_language_manifest,
)


class TranslationDomain(Enum):
    """Identify one independently packaged SugarSubstitute text surface."""

    APPLICATION = "app"
    LAUNCHER = "launcher"


@dataclass(frozen=True, slots=True)
class TranslationCatalogArtifact:
    """Pair one release language's authored catalog with its runtime artifact."""

    language: LanguageDefinition
    domain: TranslationDomain
    source_path: Path
    compiled_path: Path


@dataclass(frozen=True, slots=True)
class _DomainLayout:
    """Describe one domain's manifest resource and package destination."""

    domain: TranslationDomain
    resource_name: Callable[[LanguageDefinition], str | None]
    compiled_parent: tuple[str, ...]


_DOMAIN_LAYOUTS = (
    _DomainLayout(
        domain=TranslationDomain.APPLICATION,
        resource_name=lambda language: language.app_qm,
        compiled_parent=("substitute", "presentation", "resources", "i18n"),
    ),
    _DomainLayout(
        domain=TranslationDomain.LAUNCHER,
        resource_name=lambda language: language.launcher_qm,
        compiled_parent=("launcher", "sugarsubstitute_launcher", "i18n"),
    ),
)


def release_translation_catalogs(
    project_root: Path,
    *,
    manifest: LanguageManifest | None = None,
) -> tuple[TranslationCatalogArtifact, ...]:
    """Resolve every non-English release catalog without a locale inventory."""

    active_manifest = manifest or load_language_manifest()
    artifacts: list[TranslationCatalogArtifact] = []
    for language in active_manifest.release_languages:
        if language.identifier == active_manifest.default_language.identifier:
            continue
        source_locale = language.qt_locale_candidates[0]
        for layout in _DOMAIN_LAYOUTS:
            resource_name = layout.resource_name(language)
            if resource_name is None:
                raise ValueError(
                    f"{language.identifier}: release locale has no "
                    f"{layout.domain.value} runtime catalog."
                )
            artifacts.append(
                TranslationCatalogArtifact(
                    language=language,
                    domain=layout.domain,
                    source_path=(
                        project_root
                        / "translations"
                        / f"{layout.domain.value}_{source_locale}.ts"
                    ),
                    compiled_path=(
                        project_root.joinpath(*layout.compiled_parent) / resource_name
                    ),
                )
            )
    return tuple(artifacts)


__all__ = [
    "TranslationCatalogArtifact",
    "TranslationDomain",
    "release_translation_catalogs",
]
