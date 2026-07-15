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

"""Own projection freshness state and scheduled projection update policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)

from .model import PromptProjectionDisplayMode
from ..editing_session import PromptSourceEditOrigin
from .update_scheduler import PendingProjectionUpdate, PromptProjectionUpdateScheduler

_MINIMUM_VALID_LAYOUT_WIDTH = 120
_FALLBACK_LAYOUT_WIDTH = 760.0


class ProjectionFreshness(Enum):
    """Describe whether passive projection metrics match the latest source."""

    FRESH = "fresh"
    STALE_SAFE = "stale_safe"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PromptProjectionCommittedMetrics:
    """Cache passive layout metrics from the latest committed projection."""

    source_revision: int
    content_height: float
    content_width: float
    viewport_width: int
    display_mode: PromptProjectionDisplayMode


@dataclass(frozen=True, slots=True)
class PromptProjectionFreshnessBlockers:
    """Describe active projection modes that prevent deferred projection work."""

    display_mode: PromptProjectionDisplayMode
    reorder_preview_active: bool
    autocomplete_preview_active: bool
    exact_weight_edit_active: bool
    expanded_source_range_active: bool


class PromptProjectionFreshnessController:
    """Coordinate projection freshness, committed metrics, and pending updates."""

    def __init__(
        self,
        *,
        apply_update: Callable[[PendingProjectionUpdate], None],
        parent: QObject | None,
    ) -> None:
        """Create a controller around the projection update timer mechanism."""

        self._freshness: ProjectionFreshness = ProjectionFreshness.UNAVAILABLE
        self._committed_metrics: PromptProjectionCommittedMetrics | None = None
        self._last_source_edit_deferrable_for_projection = False
        self._defer_source_rebuilds_until_prompt_state = False
        self._applying_scheduled_projection_update = False
        self._update_scheduler = PromptProjectionUpdateScheduler(
            apply_update=self._apply_scheduled_update,
            parent=parent,
        )
        self._apply_update = apply_update

    @property
    def freshness(self) -> ProjectionFreshness:
        """Return the current projection freshness state."""

        return self._freshness

    @property
    def committed_metrics(self) -> PromptProjectionCommittedMetrics | None:
        """Return the latest committed projection metrics, when available."""

        return self._committed_metrics

    @committed_metrics.setter
    def committed_metrics(
        self,
        metrics: PromptProjectionCommittedMetrics | None,
    ) -> None:
        """Replace committed metrics for focused tests and explicit resets."""

        self._committed_metrics = metrics
        if metrics is None:
            self._freshness = ProjectionFreshness.UNAVAILABLE

    @property
    def update_scheduler(self) -> PromptProjectionUpdateScheduler:
        """Return the owned timer scheduler for focused scheduler tests."""

        return self._update_scheduler

    def set_defer_source_rebuilds_until_prompt_state(self, enabled: bool) -> None:
        """Set whether source edits wait for controller-owned prompt snapshots."""

        self._defer_source_rebuilds_until_prompt_state = enabled

    def has_pending_update(self) -> bool:
        """Return whether a safe projection rebuild is waiting to flush."""

        return self._update_scheduler.has_pending_update()

    def has_stale_projection_geometry(self) -> bool:
        """Return whether layout metrics still describe an older source snapshot."""

        return self._freshness is ProjectionFreshness.STALE_SAFE

    def can_use_committed_passive_metrics(self) -> bool:
        """Return whether passive metric readers can use committed layout metrics."""

        return (
            self._committed_metrics is not None
            and self._freshness is not ProjectionFreshness.UNAVAILABLE
        )

    def mark_source_text_changed(
        self,
        *,
        deferrable_projection: bool,
        source_revision: int,
    ) -> None:
        """Record source freshness after the editing session commits new text."""

        self._last_source_edit_deferrable_for_projection = deferrable_projection
        self._freshness = (
            ProjectionFreshness.STALE_SAFE
            if deferrable_projection and self._committed_metrics is not None
            else ProjectionFreshness.UNAVAILABLE
        )
        if self._committed_metrics is None:
            return
        if self._committed_metrics.source_revision == source_revision:
            self._freshness = ProjectionFreshness.FRESH

    def schedule_safe_typing_update(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        source_revision: int,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Schedule one source-changing prompt-state update after safe typing."""

        self._update_scheduler.schedule(
            PendingProjectionUpdate.create(
                document_view=document_view,
                render_plan=render_plan,
                reason="safe_typing",
                source_revision=source_revision,
                previous_document_view=previous_document_view,
                previous_render_plan=previous_render_plan,
            )
        )
        self._last_source_edit_deferrable_for_projection = False

    def schedule_metadata_update(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        source_revision: int,
    ) -> None:
        """Schedule one same-source metadata projection update."""

        self._update_scheduler.schedule(
            PendingProjectionUpdate.create(
                document_view=document_view,
                render_plan=render_plan,
                reason="metadata",
                source_revision=source_revision,
            )
        )
        self._last_source_edit_deferrable_for_projection = False

    def clear_pending_after_immediate_apply(self) -> None:
        """Cancel pending work and clear deferrable-source state after direct apply."""

        self._update_scheduler.cancel()
        self._last_source_edit_deferrable_for_projection = False

    def flush_pending_update(self, *, reason: str) -> None:
        """Apply scheduled projection work before exact geometry is read."""

        if self._applying_scheduled_projection_update:
            return
        self._update_scheduler.flush_now(reason=reason)

    def cancel_stale_safe_projection_update(
        self,
        *,
        source_text: str,
    ) -> bool:
        """Drop stale safe-typing projection work before superseding source edits."""

        if self._applying_scheduled_projection_update:
            return False
        cancelled = self._update_scheduler.cancel_if_stale_safe_source_unchanged(
            source_text
        )
        if cancelled:
            self._last_source_edit_deferrable_for_projection = False
        return cancelled

    def cancel_pending_projection_update(self) -> None:
        """Cancel stale scheduled projection work before immediate rebuild paths."""

        if self._applying_scheduled_projection_update:
            return
        self.clear_pending_after_immediate_apply()

    def can_schedule_prompt_state_projection(
        self,
        blockers: PromptProjectionFreshnessBlockers,
    ) -> bool:
        """Return whether the latest semantic prompt state may rebuild later."""

        return bool(
            self._last_source_edit_deferrable_for_projection
            and self._defer_source_rebuilds_until_prompt_state
            and self._projection_blockers_allow_scheduling(blockers)
        )

    def can_schedule_metadata_prompt_state_projection(
        self,
        blockers: PromptProjectionFreshnessBlockers,
    ) -> bool:
        """Return whether unchanged-source metadata can rebuild later."""

        return self._projection_blockers_allow_scheduling(blockers)

    def can_defer_wrap_reflow_projection_update(
        self,
        blockers: PromptProjectionFreshnessBlockers,
    ) -> bool:
        """Return whether a wrap-only edit may wait for prompt-state projection."""

        return bool(
            self._defer_source_rebuilds_until_prompt_state
            and self._committed_metrics is not None
            and self._projection_blockers_allow_scheduling(blockers)
        )

    def layout_width_for_projection_rebuild(
        self,
        *,
        viewport_width: int,
        parent_width: int | None,
    ) -> float:
        """Return a non-pathological layout width for projection wrapping."""

        if viewport_width >= _MINIMUM_VALID_LAYOUT_WIDTH:
            return float(viewport_width)
        if (
            self._committed_metrics is not None
            and self._committed_metrics.viewport_width >= _MINIMUM_VALID_LAYOUT_WIDTH
        ):
            return float(self._committed_metrics.viewport_width)
        if parent_width is not None:
            return float(parent_width)
        return _FALLBACK_LAYOUT_WIDTH

    def sync_layout_metrics(
        self,
        *,
        commit_projection: bool,
        reorder_preview_active: bool,
        source_revision: int,
        content_height: float,
        content_width: float,
        layout_width: float,
        display_mode: PromptProjectionDisplayMode,
    ) -> bool:
        """Commit passive layout metrics and return whether height is publishable."""

        projection_was_stale_safe = self._freshness is ProjectionFreshness.STALE_SAFE
        if not reorder_preview_active and (
            commit_projection or not projection_was_stale_safe
        ):
            self._committed_metrics = PromptProjectionCommittedMetrics(
                source_revision=source_revision,
                content_height=content_height,
                content_width=content_width,
                viewport_width=int(round(layout_width)),
                display_mode=display_mode,
            )
            self._freshness = ProjectionFreshness.FRESH
        return self._freshness is ProjectionFreshness.FRESH

    def fill_band_source_text(
        self,
        *,
        committed_source_text: str,
        live_source_text: str,
    ) -> str:
        """Return the source text matching passive fill-band layout freshness."""

        if self._freshness is ProjectionFreshness.STALE_SAFE:
            return committed_source_text
        return live_source_text

    def fill_band_source_revision(self, *, current_source_revision: int) -> int:
        """Return the revision matching passive fill-band layout freshness."""

        if (
            self._freshness is ProjectionFreshness.STALE_SAFE
            and self._committed_metrics is not None
        ):
            return self._committed_metrics.source_revision
        return current_source_revision

    def fill_band_content_width(self, *, current_content_width: float) -> float:
        """Return the content width matching passive fill-band layout freshness."""

        if self._committed_metrics is not None:
            return self._committed_metrics.content_width
        return current_content_width

    def transient_committed_source_revision(
        self,
        *,
        current_source_revision: int,
    ) -> int:
        """Return the source revision owned by committed projection geometry."""

        if self._committed_metrics is not None:
            return self._committed_metrics.source_revision
        return current_source_revision

    def transient_fallback_committed_source_revision(
        self,
        *,
        current_source_revision: int,
    ) -> int:
        """Return committed source revision for fallback overlay estimates."""

        if self._committed_metrics is not None:
            return self._committed_metrics.source_revision
        return max(0, current_source_revision - 1)

    def can_defer_source_rebuild_for_edit(
        self,
        *,
        blockers: PromptProjectionFreshnessBlockers,
        start: int,
        end: int,
        replaced_text: str,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        updated_text: str,
        normalized_text: str,
        edit_inside_projected_token: bool,
        delete_intersects_projected_token: bool,
        typed_character_requires_immediate_projection: bool,
        syntax_sensitive_autocomplete_prefix: bool,
    ) -> tuple[bool, str]:
        """Return whether one edit can wait for controller-owned prompt state."""

        if not self._defer_source_rebuilds_until_prompt_state:
            return False, "prompt_state_deferral_disabled"
        if blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED:
            return False, "display_mode_not_projected"
        if self._committed_metrics is None:
            return False, "committed_metrics_unavailable"
        if blockers.reorder_preview_active:
            return False, "reorder_preview_active"
        if blockers.expanded_source_range_active:
            return False, "expanded_token_active"
        if blockers.exact_weight_edit_active:
            return False, "exact_weight_edit_active"
        if origin in {
            PromptSourceEditOrigin.PASTE,
            PromptSourceEditOrigin.AUTOCOMPLETE,
        }:
            return False, "canonicalizing_origin"
        if normalized_text != updated_text:
            return False, "normalization_changed_text"
        if replacement_text == "":
            return self.can_defer_source_delete_for_edit(
                start=start,
                end=end,
                replaced_text=replaced_text,
                delete_intersects_projected_token=delete_intersects_projected_token,
            )
        if start != end:
            return False, "selection_replacement"
        if len(replacement_text) != 1:
            return False, "replacement_not_single_character"
        if replacement_text in {"\n", "\r", "\t"}:
            return False, "control_character"
        if edit_inside_projected_token:
            return False, "edit_inside_projected_token"
        if typed_character_requires_immediate_projection:
            if syntax_sensitive_autocomplete_prefix:
                return True, "syntax_sensitive_autocomplete_prefix"
            return False, "syntax_sensitive_character"
        return True, "plain_single_character"

    def can_defer_source_delete_for_edit(
        self,
        *,
        start: int,
        end: int,
        replaced_text: str,
        delete_intersects_projected_token: bool,
    ) -> tuple[bool, str]:
        """Return whether one deletion can use a transient erase overlay."""

        if end != start + 1:
            return False, "delete_not_single_character"
        if replaced_text in {"\n", "\r", "\t"}:
            return False, "delete_control_character"
        if delete_intersects_projected_token:
            return False, "delete_intersects_projected_token"
        return True, "plain_single_character_delete"

    def can_extend_deferred_plain_source_edit(
        self,
        *,
        previous_projection_freshness: ProjectionFreshness,
        start: int,
        end: int,
        replacement_text: str,
        typed_character_requires_immediate_projection: bool,
        syntax_sensitive_autocomplete_prefix: bool,
    ) -> bool:
        """Return whether deferred plain-source edit state can be extended."""

        if previous_projection_freshness is not ProjectionFreshness.STALE_SAFE:
            return False
        if start != end or len(replacement_text) != 1:
            return False
        if replacement_text in {"\n", "\r", "\t"}:
            return False
        if typed_character_requires_immediate_projection:
            return syntax_sensitive_autocomplete_prefix
        return True

    def can_defer_immediate_projection_fallback_edit(
        self,
        *,
        blockers: PromptProjectionFreshnessBlockers,
        previous_text: str | None,
        next_text: str,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        projection_deferral_reason: str,
        insertion_inside_projected_token: bool,
        deletion_intersects_projected_token: bool,
        transient_insertion_overlay_deferrable: bool,
        typed_character_requires_immediate_projection: bool,
        syntax_sensitive_autocomplete_prefix: bool,
    ) -> tuple[bool, str]:
        """Return whether a failed immediate projection apply can become stale-safe."""

        if projection_deferral_reason not in {
            "plain_single_character_requires_layout",
            "syntax_sensitive_autocomplete_prefix",
            "syntax_sensitive_autocomplete_prefix_requires_layout",
            "plain_single_character",
            "plain_single_character_delete",
            "plain_single_character_delete_requires_layout",
        }:
            return False, "deferral_reason_not_safe"
        if not self._defer_source_rebuilds_until_prompt_state:
            return False, "prompt_state_deferral_disabled"
        if blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED:
            return False, "display_mode_not_projected"
        if self._committed_metrics is None:
            return False, "committed_metrics_unavailable"
        if blockers.reorder_preview_active:
            return False, "reorder_preview_active"
        if blockers.autocomplete_preview_active:
            return False, "autocomplete_preview_active"
        if blockers.exact_weight_edit_active:
            return False, "exact_weight_edit_active"
        if blockers.expanded_source_range_active:
            return False, "expanded_token_active"
        if (
            previous_text is None
            or start is None
            or end is None
            or start < 0
            or end < start
            or end > len(previous_text)
        ):
            return False, "missing_edit_context"
        if replacement_text is None:
            return False, "missing_replacement_text"
        if previous_text[:start] + replacement_text + previous_text[end:] != next_text:
            return False, "edit_context_mismatch"
        if replacement_text == "":
            if end != start + 1:
                return False, "delete_not_single_character"
            if previous_text[start:end] in {"\r", "\t"}:
                return False, "delete_control_character"
            if deletion_intersects_projected_token:
                return False, "delete_intersects_projected_token"
            return True, "plain_single_character_delete"
        if start != end:
            return False, "selection_replacement"
        if len(replacement_text) != 1:
            return False, "replacement_not_single_character"
        if replacement_text in {"\n", "\r", "\t"}:
            return False, "control_character"
        if insertion_inside_projected_token:
            return False, "edit_inside_projected_token"
        if not transient_insertion_overlay_deferrable:
            return False, "requires_layout"
        if typed_character_requires_immediate_projection:
            return (
                syntax_sensitive_autocomplete_prefix,
                "syntax_sensitive_autocomplete_prefix"
                if syntax_sensitive_autocomplete_prefix
                else "syntax_sensitive_character",
            )
        return True, projection_deferral_reason

    def _projection_blockers_allow_scheduling(
        self,
        blockers: PromptProjectionFreshnessBlockers,
    ) -> bool:
        """Return whether active projection modes permit scheduled rebuilding."""

        return bool(
            blockers.display_mode is PromptProjectionDisplayMode.PROJECTED
            and not blockers.reorder_preview_active
            and not blockers.autocomplete_preview_active
            and not blockers.exact_weight_edit_active
            and not blockers.expanded_source_range_active
        )

    def _apply_scheduled_update(self, update: PendingProjectionUpdate) -> None:
        """Apply one timer-delivered update while guarding reentrant flushes."""

        self._applying_scheduled_projection_update = True
        try:
            self._apply_update(update)
        finally:
            self._applying_scheduled_projection_update = False


__all__ = [
    "ProjectionFreshness",
    "PromptProjectionCommittedMetrics",
    "PromptProjectionFreshnessBlockers",
    "PromptProjectionFreshnessController",
]
