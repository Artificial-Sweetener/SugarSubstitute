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

"""Coordinate prompt wildcard preprocessing preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.domain.prompt import PromptWildcardSyntaxProfile

PROMPT_WILDCARD_PREFERENCES_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PromptWildcardPreferences:
    """Capture user-configurable wildcard preprocessing settings."""

    resolve_on_generation: bool = True

    def syntax_profile(self) -> PromptWildcardSyntaxProfile:
        """Return the fixed curly-brace wildcard parser profile."""

        return PromptWildcardSyntaxProfile.default()


class PromptWildcardPreferenceRepository(Protocol):
    """Persist and load wildcard preprocessing preferences."""

    def load(self) -> PromptWildcardPreferences:
        """Load persisted wildcard preferences."""

    def save(self, preferences: PromptWildcardPreferences) -> None:
        """Persist wildcard preferences."""


class PromptWildcardPreferenceService:
    """Own normalized wildcard preference use cases."""

    def __init__(self, repository: PromptWildcardPreferenceRepository) -> None:
        """Store the preference repository."""

        self._repository = repository

    def load_preferences(self) -> PromptWildcardPreferences:
        """Load current wildcard preprocessing preferences."""

        return self._repository.load()

    def save_preferences(self, preferences: PromptWildcardPreferences) -> None:
        """Persist normalized wildcard preprocessing preferences."""

        preferences.syntax_profile()
        self._repository.save(preferences)

    def set_resolve_on_generation(self, enabled: bool) -> PromptWildcardPreferences:
        """Persist whether generation preprocessing resolves wildcards."""

        updated = PromptWildcardPreferences(
            resolve_on_generation=enabled,
        )
        self.save_preferences(updated)
        return updated


__all__ = [
    "PROMPT_WILDCARD_PREFERENCES_SCHEMA_VERSION",
    "PromptWildcardPreferenceRepository",
    "PromptWildcardPreferenceService",
    "PromptWildcardPreferences",
]
