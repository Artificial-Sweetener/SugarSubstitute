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

"""Validate prompt-editor async result freshness through generic execution."""

from __future__ import annotations

from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from typing import Literal, cast

from substitute.application.execution import StaleResultGuard, TaskIdentity

from .execution import PromptAsyncResultIdentity

PromptFreshnessField = Literal[
    "request_id",
    "editor_session_id",
    "source_revision",
    "feature_profile_id",
    "scene_context_id",
    "cube_context_id",
    "query_identity",
    "cancellation_generation",
]


@dataclass(frozen=True, slots=True)
class PromptFreshnessMismatch:
    """Describe one prompt-safe identity field that failed freshness validation."""

    field_name: PromptFreshnessField
    expected: Hashable | None
    actual: Hashable | None


@dataclass(frozen=True, slots=True)
class PromptFreshnessDecision:
    """Describe whether an async result is fresh enough to publish."""

    is_fresh: bool
    drop_reason: str
    mismatches: tuple[PromptFreshnessMismatch, ...] = ()


class PromptStaleResultGuard:
    """Validate prompt-editor freshness with the generic execution guard."""

    def __init__(self, guard: StaleResultGuard | None = None) -> None:
        """Store the reusable execution freshness guard."""

        self._guard = guard or StaleResultGuard()

    def validate(
        self,
        *,
        result_identity: PromptAsyncResultIdentity,
        current_identity: PromptAsyncResultIdentity,
        required_fields: Iterable[PromptFreshnessField],
    ) -> PromptFreshnessDecision:
        """Return whether a result identity still matches current editor state."""

        fields = tuple(required_fields)
        decision = self._guard.validate(
            result_identity=_generic_identity_from_prompt(result_identity),
            current_identity=_generic_identity_from_prompt(current_identity),
            required_fields=fields,
        )
        return PromptFreshnessDecision(
            is_fresh=decision.is_fresh,
            drop_reason=decision.drop_reason,
            mismatches=tuple(
                PromptFreshnessMismatch(
                    field_name=cast(PromptFreshnessField, mismatch.field_name),
                    expected=mismatch.expected,
                    actual=mismatch.actual,
                )
                for mismatch in decision.mismatches
            ),
        )


def _generic_identity_from_prompt(identity: PromptAsyncResultIdentity) -> TaskIdentity:
    """Map prompt identity fields into generic execution identity parts."""

    parts: list[tuple[str, Hashable]] = []
    for field_name in (
        "editor_session_id",
        "source_revision",
        "feature_profile_id",
        "scene_context_id",
        "cube_context_id",
        "query_identity",
    ):
        value = getattr(identity, field_name)
        if value is not None:
            parts.append((field_name, value))
    return TaskIdentity(
        request_id=identity.request_id,
        domain="prompt_editor",
        parts=tuple(parts),
        cancellation_generation=identity.cancellation_generation or 0,
    )


__all__ = [
    "PromptFreshnessDecision",
    "PromptFreshnessField",
    "PromptFreshnessMismatch",
    "PromptStaleResultGuard",
]
