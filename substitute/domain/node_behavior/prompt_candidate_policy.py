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

"""Resolve editable prompt candidates using deterministic evidence tiers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import PromptRole
from .prompt_graph import (
    PromptAmbiguityReason,
    PromptEvidence,
    PromptEvidenceKind,
    PromptGraphField,
    PromptRoleAmbiguity,
)


@dataclass(frozen=True, slots=True)
class PromptCandidateSelection:
    """Carry selected fields or one fail-closed ambiguity."""

    fields: tuple[PromptGraphField, ...] = ()
    ambiguity: PromptRoleAmbiguity | None = None
    evidence: tuple[PromptEvidence, ...] = ()


class PromptCandidatePolicy:
    """Select prompt fields without opaque scores or class-name assumptions."""

    def select(
        self,
        candidates: list[PromptGraphField] | tuple[PromptGraphField, ...],
        role: PromptRole,
    ) -> PromptCandidateSelection:
        """Select a unique candidate by explicit evidence tiers."""

        viable = tuple(dict.fromkeys(candidates))
        if not viable:
            return PromptCandidateSelection()
        conflicting = tuple(
            candidate
            for candidate in viable
            if (candidate_role := self.authored_role(candidate)) is not None
            and candidate_role is not role
        )
        matching = tuple(
            candidate for candidate in viable if self.authored_role(candidate) is role
        )
        if conflicting and not matching:
            return _ambiguous_selection(
                viable,
                "Authored polarity conflicts with conditioning sink polarity.",
            )
        if len(matching) == 1:
            return PromptCandidateSelection(fields=matching)
        if len(matching) > 1:
            return _ambiguous_selection(
                matching,
                "Multiple fields have the same authored prompt polarity.",
            )
        neutral = tuple(
            candidate for candidate in viable if candidate not in conflicting
        )
        prompt_named = tuple(
            candidate for candidate in neutral if self.has_prompt_token(candidate)
        )
        if len(prompt_named) == 1:
            return PromptCandidateSelection(fields=prompt_named)
        if len(prompt_named) > 1:
            return _ambiguous_selection(
                prompt_named,
                "Multiple prompt-named string fields remain indistinguishable.",
            )
        multiline = tuple(candidate for candidate in neutral if candidate.multiline)
        if len(multiline) == 1:
            return PromptCandidateSelection(fields=multiline)
        if len(multiline) > 1:
            return _ambiguous_selection(
                multiline,
                "Multiple multiline string fields remain indistinguishable.",
            )
        if len(neutral) == 1:
            return PromptCandidateSelection(fields=neutral)
        if len(neutral) > 1:
            return _ambiguous_selection(
                neutral,
                "Multiple string fields remain indistinguishable.",
            )
        return PromptCandidateSelection()

    def authored_role(self, field: PromptGraphField) -> PromptRole | None:
        """Return consistent authored polarity across field and node names."""

        field_role = role_from_name(field.label)
        node_role = role_from_name(field.node_title)
        if (
            field_role is not None
            and node_role is not None
            and field_role is not node_role
        ):
            return None
        return field_role or node_role

    def has_prompt_token(self, field: PromptGraphField) -> bool:
        """Return whether the field or node title explicitly names a prompt."""

        return "prompt" in (
            normalized_words(field.label) | normalized_words(field.node_title)
        )

    def is_authored_candidate(self, field: PromptGraphField) -> bool:
        """Return whether a string has enough evidence for name-only inference."""

        return (
            field.multiline
            or self.has_prompt_token(field)
            or self.authored_role(field) is not None
        )

    def candidate_evidence(
        self,
        field: PromptGraphField,
    ) -> tuple[PromptEvidence, ...]:
        """Return non-polarity evidence explaining why a field is prompt-like."""

        evidence: list[PromptEvidence] = []
        if field.multiline:
            evidence.append(
                PromptEvidence(PromptEvidenceKind.MULTILINE_STRING, field.label)
            )
        if self.has_prompt_token(field):
            evidence.append(
                PromptEvidence(PromptEvidenceKind.PROMPT_NAMING, field.label)
            )
        return tuple(evidence)


def normalized_words(value: str) -> frozenset[str]:
    """Return lowercase authored-name tokens without punctuation."""

    return frozenset(re.findall(r"[a-z0-9]+", value.casefold()))


def role_from_name(value: str) -> PromptRole | None:
    """Return unambiguous polarity expressed by an authored name."""

    words = normalized_words(value)
    has_positive = "positive" in words
    has_negative = "negative" in words
    if has_positive == has_negative:
        return None
    return PromptRole.POSITIVE if has_positive else PromptRole.NEGATIVE


def role_from_semantic_sink(name: str, type_name: str) -> PromptRole | None:
    """Return polarity only for explicit conditioning sink names."""

    if normalized_type(type_name) != "CONDITIONING":
        return None
    words = normalized_words(name)
    if words == {"positive"}:
        return PromptRole.POSITIVE
    if words == {"negative"}:
        return PromptRole.NEGATIVE
    return None


def normalized_type(value: str) -> str:
    """Return a normalized Comfy port type."""

    return value.strip().upper()


def is_text_encoder_type(value: str) -> bool:
    """Return whether a typed input carries a text-encoder resource."""

    normalized = normalized_type(value)
    return normalized == "CLIP" or "TEXT_ENCODER" in normalized


def _ambiguous_selection(
    fields: tuple[PromptGraphField, ...],
    detail: str,
) -> PromptCandidateSelection:
    """Return a fail-closed candidate selection."""

    return PromptCandidateSelection(
        ambiguity=PromptRoleAmbiguity(
            locators=tuple(sorted(field.locator for field in fields)),
            reason=PromptAmbiguityReason.INDETERMINATE_FIELD,
            detail=detail,
        )
    )


__all__ = [
    "PromptCandidatePolicy",
    "PromptCandidateSelection",
    "is_text_encoder_type",
    "normalized_type",
    "normalized_words",
    "role_from_name",
    "role_from_semantic_sink",
]
