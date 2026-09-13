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

"""Prepare model-picker snapshots for authoritative empty Comfy fields."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.application.model_metadata import (
    RichChoiceContext,
    RichChoiceResolver,
    model_kind_for_field,
)
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.widgets.media_wall import unavailable_thumbnail_readiness

from .model_choice_resolution_adapter import literal_model_choice_resolution
from .model_choice_snapshot_values import (
    rich_choice_search_placeholder,
    suggestion_context,
)
from .model_choice_snapshots import (
    PanelModelChoiceSnapshot,
    PanelModelChoiceSnapshotKind,
    PanelModelChoiceSnapshotRequest,
    PanelPreparedModelChoiceSource,
)


def known_empty_model_kind(
    request: PanelModelChoiceSnapshotRequest,
    *,
    options: Sequence[str],
    resolver: RichChoiceResolver,
) -> str | None:
    """Resolve an empty picker from its authoritative Comfy field identity."""

    if options or not isinstance(request.node_type, str):
        return None
    model_kind = model_kind_for_field(
        class_type=request.node_type,
        input_key=request.key,
    )
    if model_kind is None or model_kind not in resolver.enabled_kinds:
        return None
    return model_kind


def build_known_empty_model_snapshot(
    request: PanelModelChoiceSnapshotRequest,
    *,
    identity: CatalogSnapshotIdentity,
    model_kind: str,
    resolver: RichChoiceResolver,
) -> PanelModelChoiceSnapshot:
    """Build an empty rich picker without requiring an impossible option match."""

    resolution = literal_model_choice_resolution(
        options=(),
        matched_kind=model_kind,
    )
    return PanelModelChoiceSnapshot(
        identity=identity,
        status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        kind=PanelModelChoiceSnapshotKind.RICH_MODEL_PICKER,
        options=(),
        model_kind=model_kind,
        suggestion_context=suggestion_context(
            model_kind=model_kind,
            target_model=request.target_model,
        ),
        resolution=resolution,
        choice_source=PanelPreparedModelChoiceSource(
            resolver=resolver,
            options=(),
            context=RichChoiceContext(
                node_class=(
                    request.node_type if isinstance(request.node_type, str) else None
                ),
                node_name=request.node_name,
                field_key=request.key,
                model_kind=model_kind,
            ),
            initial_resolution=resolution,
        ),
        search_placeholder=rich_choice_search_placeholder((model_kind,)),
        thumbnail_readiness=unavailable_thumbnail_readiness(
            "thumbnail_variant_unavailable"
        ),
    )


__all__ = ["build_known_empty_model_snapshot", "known_empty_model_kind"]
