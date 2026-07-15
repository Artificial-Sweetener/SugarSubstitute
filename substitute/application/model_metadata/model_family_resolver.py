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

"""Infer broad model-family associations from selected model metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass

from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
)
from substitute.domain.user_presets import (
    UserPresetAssociation,
    UserPresetAssociationScope,
)

_CIVITAI_PROVIDER = "civitai"
_BROAD_FAMILY_KEYS = frozenset({"sdxl"})
_FAMILY_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("anima", "Anima", r"\banima\b"),
    ("sdxl", "SDXL", r"\b(?:sdxl|sdxl\s*1\.?0|stable\s+diffusion\s+xl)\b"),
    ("illustrious", "Illustrious", r"\billustrious\b"),
    ("noobai", "NoobAI", r"\bnoob\s*ai\b|\bnoobai\b"),
    ("pony", "Pony", r"\bpony\b"),
    ("flux", "FLUX", r"\bflux\b"),
)


@dataclass(frozen=True)
class ModelFamily:
    """Describe one broad model family inferred from selected model metadata."""

    provider: str
    key: str
    label: str
    evidence: tuple[str, ...]


def resolve_model_families_for_catalog_item(
    item: ModelCatalogItem | None,
) -> tuple[ModelFamily, ...]:
    """Return broad model-family associations for one selected checkpoint."""

    if item is None:
        return ()
    families: list[ModelFamily] = []
    base_family = _family_from_text(item.base_model, evidence_label="base_model")
    if base_family is not None:
        families.append(base_family)

    should_inspect_secondary_fields = (
        base_family is None or base_family.key in _BROAD_FAMILY_KEYS
    )
    if should_inspect_secondary_fields:
        for evidence_label, text in (
            ("display_name", item.display_name),
            ("tags", " ".join(item.tags)),
        ):
            family = _family_from_text(text, evidence_label=evidence_label)
            if family is not None:
                families.append(family)
    return _dedupe_families(families)


def model_family_associations_for_catalog_item(
    item: ModelCatalogItem | None,
) -> tuple[UserPresetAssociation, ...]:
    """Return preset associations for the selected checkpoint family."""

    return tuple(
        UserPresetAssociation(
            scope=UserPresetAssociationScope.MODEL_FAMILY,
            provider=family.provider,
            key=family.key,
            label=family.label,
        )
        for family in resolve_model_families_for_catalog_item(item)
    )


def _family_from_text(text: str | None, *, evidence_label: str) -> ModelFamily | None:
    """Return the first known family matched in one metadata text field."""

    if not text:
        return None
    normalized = text.casefold()
    for key, label, pattern in _FAMILY_ALIASES:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return ModelFamily(
                provider=_CIVITAI_PROVIDER,
                key=key,
                label=label,
                evidence=(f"{evidence_label}:{text}",),
            )
    return None


def _dedupe_families(families: list[ModelFamily]) -> tuple[ModelFamily, ...]:
    """Return families de-duplicated by provider and key while preserving order."""

    seen: set[tuple[str, str]] = set()
    deduped: list[ModelFamily] = []
    for family in families:
        identity = (family.provider, family.key)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(family)
    return tuple(deduped)


__all__ = [
    "ModelFamily",
    "model_family_associations_for_catalog_item",
    "resolve_model_families_for_catalog_item",
]
