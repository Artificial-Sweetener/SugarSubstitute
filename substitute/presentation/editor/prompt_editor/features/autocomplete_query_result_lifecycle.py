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

"""Own autocomplete query/result freshness below Qt interaction adapters."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import replace
from typing import Literal, Protocol, cast

from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from .autocomplete_query_controller import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQuerySourceSnapshot,
    PromptAutocompleteQueryState,
)
from .autocomplete_result_controller import (
    PromptAutocompleteResultController,
    PromptAutocompleteResultSnapshot,
)
from .autocomplete_scene_context import PromptAutocompleteSceneContextController

PromptAutocompleteDismissReason = Literal[
    "accepted",
    "escape",
    "focus_lost",
    "editor_hidden",
    "caret_left_query",
    "selection_started",
    "incompatible_query",
    "no_query",
]


class PromptAutocompleteResultPublication(Protocol):
    """Publish immutable query/result transitions to the session presentation owner."""

    def has_active_session(self) -> bool:
        """Return whether a live session can be retargeted."""

    def retarget_from_query_state(
        self,
        query_state: PromptAutocompleteQueryState,
    ) -> bool:
        """Retarget the live session to one compatible prepared query state."""

    def publish_result(
        self,
        result: PromptAutocompleteResultSnapshot,
        query_state: PromptAutocompleteQueryState,
    ) -> None:
        """Publish one ready immutable result with its source-safe query state."""

    def dismiss_autocomplete(self, reason: PromptAutocompleteDismissReason) -> None:
        """Dismiss a session for one explicit lifecycle reason."""


class PromptAutocompleteCurrentSource(Protocol):
    """Expose only the live source identity needed for async stale rejection."""

    def __call__(self) -> PromptSourceIdentity | None:
        """Return the current source identity, if a source owner has one."""


class PromptAutocompleteQueryResultLifecycle:
    """Build, refresh, and republish autocomplete results from prepared snapshots.

    The lifecycle owns query-kind priority, cached-result refresh, and the latest
    prompt-safe identity used by wildcard and scheduled-LoRA async callbacks. It
    deliberately receives source data only as immutable query states and publishes
    through a narrow session port, so it neither reads Qt state nor knows panel or
    ghost-rendering details.
    """

    def __init__(
        self,
        *,
        query_controller: PromptAutocompleteQueryController,
        result_controller: PromptAutocompleteResultController,
        scene_context_controller: PromptAutocompleteSceneContextController,
        publication: PromptAutocompleteResultPublication,
        current_source_identity: PromptAutocompleteCurrentSource,
        lora_autocomplete_enabled: Callable[[], bool],
        lora_thumbnail_cache_available: Callable[[], bool],
    ) -> None:
        """Store query, result, publication, and freshness collaborators."""

        self._query_controller = query_controller
        self._result_controller = result_controller
        self._scene_context_controller = scene_context_controller
        self._publication = publication
        self._current_source_identity = current_source_identity
        self._lora_autocomplete_enabled = lora_autocomplete_enabled
        self._lora_thumbnail_cache_available = lora_thumbnail_cache_available
        self._latest_query_state: PromptAutocompleteQueryState | None = None

    @property
    def latest_query_state(self) -> PromptAutocompleteQueryState | None:
        """Return the latest source-safe query state used by async refreshes."""

        return self._latest_query_state

    def retarget_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteQuerySourceSnapshot,
    ) -> bool:
        """Retarget an active session without constructing dormant-query work."""

        if not self._publication.has_active_session():
            return False
        query_state = self._query_controller.query_state_from_source_snapshot(snapshot)
        self._latest_query_state = query_state
        return self._publication.retarget_from_query_state(query_state)

    def refresh_results_from_source_snapshot(
        self,
        snapshot: PromptAutocompleteQuerySourceSnapshot,
    ) -> None:
        """Build and publish results from one prepared source snapshot."""

        self.refresh_results_for_query_state(
            self._query_controller.query_state_from_source_snapshot(snapshot)
        )

    def refresh_results_for_query_state(
        self,
        query_state: PromptAutocompleteQueryState,
    ) -> None:
        """Build and publish the applicable result for one immutable query state."""

        self._latest_query_state = query_state
        if query_state.refresh_intent in {"caret_navigation", "mouse_navigation"}:
            self._clear_latest_query_and_dismiss()
            return
        if query_state.lora_query is not None:
            self._publish_lora_result(query_state, query_state.lora_query)
            return
        if query_state.wildcard_query is not None:
            self._publish_wildcard_result(query_state)
            return
        if query_state.scene_query is not None:
            self._publish_scene_result(query_state)
            return
        self._publish_tag_result(query_state)

    def current_source_identity(self) -> PromptSourceIdentity | None:
        """Return the live source identity used by scheduled async callbacks."""

        return self._current_source_identity()

    def current_query_identity(self) -> Hashable | None:
        """Return the active prompt-safe tag identity for stale async rejection."""

        query_state = self._latest_query_state
        query = None if query_state is None else query_state.tag_query
        if query is None:
            return None
        return self._result_controller.safe_tag_query_identity(query)

    def refresh_current_query(self) -> None:
        """Refresh the latest tag query after scheduled context publication."""

        query_state = self._latest_query_state
        if query_state is None or query_state.tag_query is None:
            return
        self.refresh_results_for_query_state(query_state)

    def refresh_active_scene_session(self) -> None:
        """Refresh the active scene query after the workflow title catalog changes."""

        query_state = self._latest_query_state
        if query_state is None or query_state.scene_query is None:
            return
        self.refresh_results_for_query_state(query_state)

    def dismiss_autocomplete(self, reason: PromptAutocompleteDismissReason) -> None:
        """Dismiss presentation when timing invalidates the active source state."""

        self._latest_query_state = None
        self._publication.dismiss_autocomplete(reason)

    def _publish_tag_result(self, query_state: PromptAutocompleteQueryState) -> None:
        """Build and publish tag suggestions while retaining fallback query state."""

        query = query_state.tag_query
        if query is None:
            self._clear_latest_query_and_dismiss()
            return
        source_identity = cast(PromptSourceIdentity | None, query_state.source_identity)
        scene_context = self._scene_context_controller.context_for_tag_query(
            query,
            source_text=query_state.source_text,
            source_identity=source_identity,
            feature_profile_identity=query_state.feature_profile_identity,
            query_identity=query_state.query_identity,
        )
        result = self._result_controller.result_for_tag_query(
            query=query,
            context=scene_context.tag_context,
            source_identity=source_identity,
        )
        self._latest_query_state = replace(query_state, tag_query=result.tag_query)
        self._publish_or_dismiss(result, self._latest_query_state)

    def _publish_scene_result(self, query_state: PromptAutocompleteQueryState) -> None:
        """Build and publish scene-title suggestions for one prepared query state."""

        query = query_state.scene_query
        if query is None:
            self._clear_latest_query_and_dismiss()
            return
        result = self._result_controller.result_for_scene_query(
            query,
            source_identity=cast(
                PromptSourceIdentity | None, query_state.source_identity
            ),
        )
        self._publish_or_dismiss(result, query_state)

    def _publish_wildcard_result(
        self, query_state: PromptAutocompleteQueryState
    ) -> None:
        """Build and publish wildcard suggestions with latest-query async guards."""

        query = query_state.wildcard_query
        if query is None:
            self._clear_latest_query_and_dismiss()
            return
        result = self._result_controller.result_for_wildcard_query(
            query,
            source_identity=cast(
                PromptSourceIdentity | None, query_state.source_identity
            ),
            current_query_identity=self._current_wildcard_query_identity,
            refresh_current_query=self._refresh_latest_wildcard_query,
        )
        self._publish_or_dismiss(result, query_state)

    def _publish_lora_result(
        self,
        query_state: PromptAutocompleteQueryState,
        query: PromptLoraAutocompleteQuery,
    ) -> None:
        """Build and publish LoRA candidates from cached catalog state only."""

        result = self._result_controller.result_for_lora_query(
            query,
            source_identity=cast(
                PromptSourceIdentity | None, query_state.source_identity
            ),
            enabled=self._lora_autocomplete_enabled(),
            thumbnail_cache_available=self._lora_thumbnail_cache_available(),
        )
        self._publish_or_dismiss(result, query_state)

    def _publish_or_dismiss(
        self,
        result: PromptAutocompleteResultSnapshot,
        query_state: PromptAutocompleteQueryState,
    ) -> None:
        """Publish ready content or clear the session through its sole output port."""

        if result.status != "ready" or not (
            result.suggestions or result.lora_candidates
        ):
            self._publication.dismiss_autocomplete("no_query")
            return
        self._publication.publish_result(result, query_state)

    def _current_wildcard_query_identity(self) -> Hashable | None:
        """Return the active wildcard identity without carrying prompt text."""

        query_state = self._latest_query_state
        query = None if query_state is None else query_state.wildcard_query
        if query is None:
            return None
        return (
            "wildcard",
            query.prefix,
            self._result_controller.limit,
            self._result_controller.wildcard_feature_identity(),
        )

    def _refresh_latest_wildcard_query(self) -> None:
        """Republish the active wildcard query after asynchronous catalog work."""

        query_state = self._latest_query_state
        if query_state is None or query_state.wildcard_query is None:
            return
        self.refresh_results_for_query_state(query_state)

    def _clear_latest_query_and_dismiss(self) -> None:
        """Forget stale query state before clearing visible session state."""

        self._latest_query_state = None
        self._publication.dismiss_autocomplete("no_query")


__all__ = [
    "PromptAutocompleteCurrentSource",
    "PromptAutocompleteDismissReason",
    "PromptAutocompleteQueryResultLifecycle",
    "PromptAutocompleteResultPublication",
]
