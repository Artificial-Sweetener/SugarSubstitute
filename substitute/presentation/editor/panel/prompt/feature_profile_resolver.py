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

"""Resolve and memoize prompt feature profiles within an explicit context scope."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.prompt_editor.lora.effective_provider import (
    WorkflowPromptContext,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_event,
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)

from .profile_policy import PanelPromptFieldProfileDecision, PanelPromptProfilePolicy


class PromptFeatureProfileServiceProtocol(Protocol):
    """Describe prompt feature-profile construction."""

    def build_profile(
        self,
        *,
        field_style: Mapping[str, object],
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptEditorFeatureProfile:
        """Build one prompt feature profile for a field context."""


@dataclass(frozen=True, slots=True)
class _ProfileCacheLogContext:
    """Carry prompt-safe profile-cache diagnostic fields."""

    cube_alias: str
    node_name: str
    field_key: str
    context_source: str
    cache_entry_count: int


class PromptFeatureProfileResolver:
    """Own profile resolution, policy application, and scoped memoization."""

    def __init__(self, service: PromptFeatureProfileServiceProtocol | None) -> None:
        """Store the optional profile service and initialize an empty scope."""

        self._service = service
        self._scope_key: tuple[Hashable, ...] | None = None
        self._cache: dict[tuple[Hashable, ...], PromptEditorFeatureProfile] = {}
        self._policy = PanelPromptProfilePolicy()

    @property
    def entry_count(self) -> int:
        """Return the number of profiles memoized for the active scope."""

        return len(self._cache)

    def clear(self) -> int:
        """Clear the active scope and return its previous entry count."""

        previous_entry_count = len(self._cache)
        self._scope_key = None
        self._cache = {}
        return previous_entry_count

    def reset_scope_if_needed(self, scope_key: tuple[Hashable, ...]) -> None:
        """Clear memoized profiles when prompt-context identity changes."""

        if self._scope_key == scope_key:
            return
        previous_entry_count = len(self._cache)
        self._scope_key = scope_key
        self._cache = {}
        log_panel_projection_event(
            "prompt_context.profile_cache_reset",
            previous_entry_count=previous_entry_count,
        )

    def resolve(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        context_source: str,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile | None:
        """Return one profile, reusing the active context scope when safe."""

        service = self._service
        if service is None:
            return None
        self.reset_scope_if_needed(workflow_context.cache_token)
        cache_key = (
            workflow_context.cache_token,
            cube_alias or "",
            prompt_node_name,
            prompt_field_key,
            _normalized_style_token(field_style),
        )
        log_context = _ProfileCacheLogContext(
            cube_alias=cube_alias or "",
            node_name=prompt_node_name,
            field_key=prompt_field_key,
            context_source=context_source,
            cache_entry_count=len(self._cache),
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            _log_cache_event("prompt_context.profile_cache_hit", log_context)
            return cached
        _log_cache_event("prompt_context.profile_cache_miss", log_context)
        started_at = panel_projection_observability_started_at()
        profile = service.build_profile(
            field_style=field_style,
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )
        log_panel_projection_timing(
            "prompt_context.profile_cache_build",
            started_at=started_at,
            cube_alias=log_context.cube_alias,
            node_name=log_context.node_name,
            field_key=log_context.field_key,
            context_source=log_context.context_source,
            cache_entry_count=log_context.cache_entry_count,
        )
        self._cache[cache_key] = profile
        return profile

    def prepare_field_profile(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        context_source: str,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return syntax and feature policy for one prompt field."""

        feature_profile = self.resolve(
            workflow_context=workflow_context,
            context_source=context_source,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            field_style=field_style,
        )
        return self._policy.prepare_prompt_field_profile(
            field_style=field_style,
            feature_profile=feature_profile,
        )


def _log_cache_event(event: str, context: _ProfileCacheLogContext) -> None:
    """Log one prompt-safe feature-profile cache lifecycle event."""

    log_panel_projection_event(
        event,
        cube_alias=context.cube_alias,
        node_name=context.node_name,
        field_key=context.field_key,
        context_source=context.context_source,
        cache_entry_count=context.cache_entry_count,
    )


def _normalized_style_token(value: object) -> Hashable:
    """Return a deterministic hashable token for prompt field style data."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _normalized_style_token(item))
            for key, item in sorted(value.items(), key=lambda current: str(current[0]))
        )
    if isinstance(value, tuple | list):
        return tuple(_normalized_style_token(item) for item in value)
    if isinstance(value, set | frozenset):
        return tuple(
            sorted((_normalized_style_token(item) for item in value), key=repr)
        )
    return repr(value)


__all__ = ["PromptFeatureProfileResolver", "PromptFeatureProfileServiceProtocol"]
