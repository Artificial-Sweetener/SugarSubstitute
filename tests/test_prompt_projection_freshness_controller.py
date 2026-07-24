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

"""Tests for projection freshness ownership and scheduling decisions."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptSemanticSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
    PromptLayoutRevision,
    PromptProjectionIdentity,
    PromptProjectionRevision,
    PromptSemanticIdentity,
    PromptSemanticRevision,
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.core.state.semantic_state import (
    PromptEditorSemanticSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDisplayMode,
)
from tests.prompt_projection_test_helpers import ensure_qapp


def test_freshness_controller_preserves_committed_metrics_while_stale_safe() -> None:
    """Stale-safe layout sync should keep passive metrics on committed geometry."""

    controller = _controller()

    assert _freshness(controller) is ProjectionFreshness.UNAVAILABLE
    assert controller.can_use_committed_passive_metrics() is False

    assert (
        controller.sync_layout_metrics(
            commit_projection=True,
            reorder_preview_active=False,
            layout_identity=_layout_identity(source_revision=1),
            content_height=100.0,
            content_width=220.0,
            layout_width=320.0,
            display_mode=PromptProjectionDisplayMode.PROJECTED,
        )
        is True
    )
    assert _freshness(controller) is ProjectionFreshness.FRESH

    controller.mark_source_text_changed(deferrable_projection=True, source_revision=2)

    assert _freshness(controller) is ProjectionFreshness.STALE_SAFE
    assert controller.fill_band_source_identity(
        current_source_identity=PromptSourceIdentity(source_revision=2),
    ) == PromptSourceIdentity(source_revision=1, source_length=0)
    assert (
        controller.fill_band_source_text(
            committed_source_text="committed",
            live_source_text="live",
        )
        == "committed"
    )

    assert (
        controller.sync_layout_metrics(
            commit_projection=False,
            reorder_preview_active=False,
            layout_identity=_layout_identity(source_revision=2),
            content_height=150.0,
            content_width=240.0,
            layout_width=360.0,
            display_mode=PromptProjectionDisplayMode.PROJECTED,
        )
        is False
    )
    assert controller.committed_metrics is not None
    assert controller.committed_metrics.source_revision == 1

    assert (
        controller.sync_layout_metrics(
            commit_projection=True,
            reorder_preview_active=False,
            layout_identity=_layout_identity(source_revision=2),
            content_height=150.0,
            content_width=240.0,
            layout_width=360.0,
            display_mode=PromptProjectionDisplayMode.PROJECTED,
        )
        is True
    )
    assert _freshness(controller) is ProjectionFreshness.FRESH
    assert controller.committed_metrics is not None
    assert controller.committed_metrics.source_revision == 2


def test_freshness_controller_schedules_safe_typing_only_when_unblocked() -> None:
    """Safe typing scheduling should require deferral state and no blockers."""

    applied: list[str] = []
    controller = _controller(apply_update=lambda update: applied.append(update.reason))
    controller.set_defer_source_rebuilds_until_prompt_state(True)
    controller.sync_layout_metrics(
        commit_projection=True,
        reorder_preview_active=False,
        layout_identity=_layout_identity(source_revision=1),
        content_height=100.0,
        content_width=220.0,
        layout_width=320.0,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
    )
    controller.mark_source_text_changed(deferrable_projection=True, source_revision=2)

    assert controller.can_schedule_prompt_state_projection(_blockers()) is True
    assert (
        controller.can_schedule_prompt_state_projection(
            _blockers(autocomplete_preview_active=True)
        )
        is False
    )

    controller.schedule_safe_typing_update(
        snapshot=_semantic_snapshot(
            "alpha beta",
            source_revision=2,
            semantic_revision=2,
        ),
        previous_snapshot=_semantic_snapshot(
            "alpha",
            source_revision=1,
            semantic_revision=1,
        ),
    )

    assert controller.has_pending_update() is True
    assert controller.can_schedule_prompt_state_projection(_blockers()) is False
    assert applied == []

    controller.clear_pending_after_immediate_apply()

    assert controller.has_pending_update() is False


def test_freshness_controller_source_rebuild_deferral_reasons() -> None:
    """Source edit deferral should return stable rejection and success reasons."""

    controller = _controller()

    assert controller.can_defer_source_rebuild_for_edit(
        blockers=_blockers(),
        start=1,
        end=1,
        replaced_text="",
        replacement_text="a",
        origin=PromptSourceEditOrigin.TYPED,
        updated_text="aa",
        normalized_text="aa",
        edit_inside_projected_token=False,
        delete_intersects_projected_token=False,
        typed_character_requires_immediate_projection=False,
        syntax_sensitive_autocomplete_prefix=False,
    ) == (False, "prompt_state_deferral_disabled")

    controller.set_defer_source_rebuilds_until_prompt_state(True)
    controller.sync_layout_metrics(
        commit_projection=True,
        reorder_preview_active=False,
        layout_identity=_layout_identity(source_revision=1),
        content_height=100.0,
        content_width=220.0,
        layout_width=320.0,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
    )

    assert controller.can_defer_source_rebuild_for_edit(
        blockers=_blockers(),
        start=1,
        end=1,
        replaced_text="",
        replacement_text="<",
        origin=PromptSourceEditOrigin.TYPED,
        updated_text="a<",
        normalized_text="a<",
        edit_inside_projected_token=False,
        delete_intersects_projected_token=False,
        typed_character_requires_immediate_projection=True,
        syntax_sensitive_autocomplete_prefix=True,
    ) == (True, "syntax_sensitive_autocomplete_prefix")
    assert controller.can_defer_source_rebuild_for_edit(
        blockers=_blockers(),
        start=1,
        end=2,
        replaced_text="b",
        replacement_text="",
        origin=PromptSourceEditOrigin.TYPED,
        updated_text="a",
        normalized_text="a",
        edit_inside_projected_token=False,
        delete_intersects_projected_token=True,
        typed_character_requires_immediate_projection=False,
        syntax_sensitive_autocomplete_prefix=False,
    ) == (False, "delete_intersects_projected_token")


def test_freshness_controller_fallback_deferral_requires_safe_context() -> None:
    """Fallback deferral should fail closed when context or blockers are unsafe."""

    controller = _controller()
    controller.set_defer_source_rebuilds_until_prompt_state(True)
    controller.sync_layout_metrics(
        commit_projection=True,
        reorder_preview_active=False,
        layout_identity=_layout_identity(source_revision=1),
        content_height=100.0,
        content_width=220.0,
        layout_width=320.0,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
    )

    assert controller.can_defer_immediate_projection_fallback_edit(
        blockers=_blockers(),
        previous_text="ab",
        next_text="acb",
        start=1,
        end=1,
        replacement_text="c",
        projection_deferral_reason="plain_single_character_requires_layout",
        insertion_inside_projected_token=False,
        deletion_intersects_projected_token=False,
        transient_insertion_overlay_deferrable=True,
        typed_character_requires_immediate_projection=False,
        syntax_sensitive_autocomplete_prefix=False,
    ) == (True, "plain_single_character_requires_layout")
    assert controller.can_defer_immediate_projection_fallback_edit(
        blockers=_blockers(autocomplete_preview_active=True),
        previous_text="ab",
        next_text="acb",
        start=1,
        end=1,
        replacement_text="c",
        projection_deferral_reason="plain_single_character_requires_layout",
        insertion_inside_projected_token=False,
        deletion_intersects_projected_token=False,
        transient_insertion_overlay_deferrable=True,
        typed_character_requires_immediate_projection=False,
        syntax_sensitive_autocomplete_prefix=False,
    ) == (False, "autocomplete_preview_active")


def _controller(
    *,
    apply_update: Callable[[PendingProjectionUpdate], None] | None = None,
) -> PromptProjectionFreshnessController:
    """Return a controller with an active Qt application."""

    ensure_qapp()
    if apply_update is None:
        return PromptProjectionFreshnessController(
            apply_update=lambda update: None,
            parent=None,
        )
    return PromptProjectionFreshnessController(
        apply_update=apply_update,
        parent=None,
    )


def _freshness(
    controller: PromptProjectionFreshnessController,
) -> ProjectionFreshness:
    """Return freshness through a helper so mypy does not narrow later reads."""

    return controller.freshness


def _blockers(
    *,
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    reorder_preview_active: bool = False,
    autocomplete_preview_active: bool = False,
    exact_weight_edit_active: bool = False,
    expanded_source_range_active: bool = False,
) -> PromptProjectionFreshnessBlockers:
    """Return a blocker snapshot for controller decision tests."""

    return PromptProjectionFreshnessBlockers(
        display_mode=display_mode,
        reorder_preview_active=reorder_preview_active,
        autocomplete_preview_active=autocomplete_preview_active,
        exact_weight_edit_active=exact_weight_edit_active,
        expanded_source_range_active=expanded_source_range_active,
    )


def _document_view(source_text: str) -> PromptDocumentView:
    """Return a minimal prompt document view for scheduling tests."""

    return PromptDocumentView(
        source_text=source_text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(len(source_text)),
        has_trailing_comma=False,
    )


def _semantic_snapshot(
    source_text: str,
    *,
    source_revision: int,
    semantic_revision: int,
) -> PromptEditorSemanticSnapshot:
    """Return one semantic publication with explicit source lineage."""

    return PromptSemanticSnapshot(
        identity=PromptSemanticIdentity(
            source=PromptSourceIdentity(source_revision, len(source_text)),
            semantic_revision=PromptSemanticRevision(semantic_revision),
        ),
        document=_document_view(source_text),
        render_plan=PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        ),
    )


def _layout_identity(*, source_revision: int) -> PromptLayoutIdentity:
    """Return layout lineage representing one committed source revision."""

    semantic = PromptSemanticIdentity(
        source=PromptSourceIdentity(source_revision, 0),
        semantic_revision=PromptSemanticRevision(source_revision),
    )
    projection = PromptProjectionIdentity(
        semantic=semantic,
        projection_revision=PromptProjectionRevision(source_revision),
    )
    return PromptLayoutIdentity(
        projection=projection,
        layout_revision=PromptLayoutRevision(source_revision),
    )
