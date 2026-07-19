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

"""Prepare panel model-choice snapshots before widget construction."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from substitute.application.display_labels import beautify_label
from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogLookup,
    RichChoiceContext,
    RichChoiceItem,
    RichChoiceResolution,
    RichChoiceResolver,
    RichChoiceSource,
)
from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    is_choice_field_type,
    resolve_choice_inventory_for_field,
)
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.catalog.model_catalog_snapshots import (
    prepared_model_catalog_rows,
)
from substitute.presentation.widgets.media_wall import (
    MediaThumbnailReadiness,
    MediaThumbnailReadinessStatus,
    unavailable_thumbnail_readiness,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.model_choice_resolution_adapter import (
    catalog_resolution,
    literal_model_choice_resolution,
)
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.editor.panel.model_choice_snapshot_controller")


class PanelModelChoiceSnapshotKind(StrEnum):
    """Classify the prepared choice payload a field factory may consume."""

    NONE = "none"
    EXPLICIT_MODEL_PICKER = "explicit_model_picker"
    RICH_MODEL_PICKER = "rich_model_picker"


@dataclass(frozen=True, slots=True)
class PanelModelChoiceSnapshotRequest:
    """Carry field identity needed to prepare a model-choice snapshot."""

    field_behavior: FieldBehavior
    node_name: str
    key: str
    value: object
    node_type: object
    field_type: object
    field_info: object
    node_definition_gateway: object
    cube_alias: str | None = None
    thumbnail_repository_available: bool = False


@dataclass(frozen=True, slots=True)
class PanelModelChoiceSnapshot:
    """Publish prepared model-choice data for foreground widget construction."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    kind: PanelModelChoiceSnapshotKind
    options: tuple[str, ...] = ()
    model_kind: str | None = None
    resolution: RichChoiceResolution | None = None
    choice_source: RichChoiceSource | None = None
    search_placeholder: str = "Search models"
    thumbnail_readiness: MediaThumbnailReadiness = field(
        default_factory=lambda: unavailable_thumbnail_readiness(
            "not_model_choice_field"
        )
    )

    @property
    def consumable(self) -> bool:
        """Return whether the snapshot carries renderable prepared choice data."""

        return self.status.consumable

    @property
    def should_build_picker(self) -> bool:
        """Return whether the field factory should construct a model picker."""

        return self.choice_source is not None and self.kind is not (
            PanelModelChoiceSnapshotKind.NONE
        )


class PanelPreparedModelChoiceSource:
    """Expose prepared model choices and defer refreshes to explicit widget events."""

    def __init__(
        self,
        *,
        resolver: RichChoiceResolver | None,
        options: Sequence[str],
        context: RichChoiceContext,
        initial_resolution: RichChoiceResolution,
    ) -> None:
        """Store a prepared first-render resolution and optional refresh resolver."""

        self._resolver = resolver
        self._options = tuple(str(option) for option in options)
        self._context = context
        self._resolution = initial_resolution

    def current_resolution(self) -> RichChoiceResolution:
        """Return the prepared resolution without consulting catalog services."""

        return self._resolution

    def refresh(self) -> RichChoiceResolution:
        """Refresh model metadata when the widget explicitly requests it."""

        if self._resolver is None:
            return self._resolution
        self._resolution = self._resolver.refresh(
            self._options,
            context=self._context,
            previous_resolution=self._resolution,
        )
        return self._resolution

    def extra_item_for_value(self, value: str) -> RichChoiceItem | None:
        """Return metadata for a selected value absent from the option list."""

        if self._resolver is None:
            return None
        return self._resolver.extra_item_for_value(
            value,
            previous_resolution=self._resolution,
        )


class PanelModelChoiceSnapshotController:
    """Own panel model-choice lookup decisions outside widget factories."""

    def __init__(
        self,
        *,
        model_catalog_service: ModelCatalogLookup | None,
        model_choice_resolver: RichChoiceResolver | None,
        panel_context_id_provider: Callable[[], Hashable | None] | None = None,
    ) -> None:
        """Store services used to prepare cache-only model-choice snapshots."""

        self._model_catalog_service = model_catalog_service
        self._model_choice_resolver = model_choice_resolver
        self._panel_context_id_provider = panel_context_id_provider or (lambda: None)
        self._snapshots: dict[Hashable, PanelModelChoiceSnapshot] = {}

    def snapshot_for_field(
        self,
        request: PanelModelChoiceSnapshotRequest,
    ) -> PanelModelChoiceSnapshot:
        """Return the prepared model-choice snapshot for one field."""

        if request.field_behavior.presentation == FieldPresentation.MODEL_PICKER:
            return self._explicit_model_picker_snapshot(request)
        if request.field_behavior.presentation != FieldPresentation.STANDARD:
            return self._none_snapshot(request)
        if not is_choice_field_type(request.field_type):
            return self._none_snapshot(request)
        return self._catalog_backed_list_choice_snapshot(request)

    def _explicit_model_picker_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
    ) -> PanelModelChoiceSnapshot:
        """Prepare an explicit model-picker snapshot from cached catalog rows."""

        model_kind = request.field_behavior.style.get("model_kind")
        if not isinstance(model_kind, str) or not model_kind.strip():
            raise RuntimeError(
                f"MODEL_PICKER field {request.node_name}.{request.key} "
                "requires style['model_kind']."
            )
        normalized_kind = model_kind.strip()
        identity = self._identity_for_request(
            request,
            model_kind=normalized_kind,
            query_mode=PanelModelChoiceSnapshotKind.EXPLICIT_MODEL_PICKER,
        )
        if self._model_catalog_service is None:
            return self._unavailable_snapshot(
                request,
                identity=identity,
                kind=PanelModelChoiceSnapshotKind.EXPLICIT_MODEL_PICKER,
                model_kind=normalized_kind,
                reason="model_catalog_unavailable",
            )
        catalog_items, revision = self._cached_catalog_items(normalized_kind)
        identity = self._identity_for_request(
            request,
            model_kind=normalized_kind,
            query_mode=PanelModelChoiceSnapshotKind.EXPLICIT_MODEL_PICKER,
            catalog_revision=revision,
        )
        if catalog_items is None:
            return self._cold_snapshot(
                request,
                identity=identity,
                kind=PanelModelChoiceSnapshotKind.EXPLICIT_MODEL_PICKER,
                model_kind=normalized_kind,
            )
        options = tuple(item.backend_value for item in catalog_items)
        resolution = catalog_resolution(
            options=options,
            catalog_items=catalog_items,
            matched_kind=normalized_kind,
            reason="explicit model picker consumed prepared catalog snapshot",
        )
        source = PanelPreparedModelChoiceSource(
            resolver=self._compatible_resolver(normalized_kind),
            options=options,
            context=RichChoiceContext(
                node_name=request.node_name,
                field_key=request.key,
                model_kind=normalized_kind,
            ),
            initial_resolution=resolution,
        )
        snapshot = PanelModelChoiceSnapshot(
            identity=identity,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            kind=PanelModelChoiceSnapshotKind.EXPLICIT_MODEL_PICKER,
            options=options,
            model_kind=normalized_kind,
            resolution=resolution,
            choice_source=source,
            search_placeholder=f"Search {beautify_label(normalized_kind)}",
            thumbnail_readiness=_thumbnail_readiness_for_resolution(
                resolution,
                repository_available=request.thumbnail_repository_available,
            ),
        )
        self._snapshots[identity.query_identity or id(snapshot)] = snapshot
        return snapshot

    def _catalog_backed_list_choice_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
    ) -> PanelModelChoiceSnapshot:
        """Prepare a picker only when exact options identify one allowed catalog."""

        snapshot_started_at = panel_projection_observability_started_at()
        options = resolve_choice_inventory_for_field(
            key=request.key,
            node_type=request.node_type,
            node_definition_gateway=request.node_definition_gateway,
            field_info=request.field_info,
        ).string_options
        log_panel_projection_timing(
            "model_choice.snapshot_options",
            started_at=snapshot_started_at,
            cube_alias=request.cube_alias or "",
            node_name=request.node_name,
            field_key=request.key,
            node_class=request.node_type if isinstance(request.node_type, str) else "",
            projection_mode="snapshot",
            option_count=len(options),
        )
        prepared_catalog = self._prepared_eligible_catalog()
        if prepared_catalog is None or self._model_choice_resolver is None:
            return self._none_snapshot(request, options=options)
        catalog_items, catalog_revision = prepared_catalog
        context = RichChoiceContext(
            node_class=request.node_type
            if isinstance(request.node_type, str)
            else None,
            node_name=request.node_name,
            field_key=request.key,
        )
        resolution = self._model_choice_resolver.resolve_prepared(
            options,
            catalog_items=catalog_items,
            context=context,
        )
        if not resolution.should_use_rich_picker or len(resolution.matched_kinds) != 1:
            return self._none_snapshot(request, options=options)
        model_kind = resolution.matched_kinds[0]
        context = RichChoiceContext(
            node_class=context.node_class,
            node_name=context.node_name,
            field_key=context.field_key,
            model_kind=model_kind,
        )
        identity = self._identity_for_request(
            request,
            model_kind=model_kind,
            query_mode=PanelModelChoiceSnapshotKind.RICH_MODEL_PICKER,
            options=options,
            catalog_revision=catalog_revision,
        )
        source = PanelPreparedModelChoiceSource(
            resolver=self._model_choice_resolver,
            options=options,
            context=context,
            initial_resolution=resolution,
        )
        snapshot = PanelModelChoiceSnapshot(
            identity=identity,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            kind=PanelModelChoiceSnapshotKind.RICH_MODEL_PICKER,
            options=tuple(options),
            model_kind=model_kind,
            resolution=resolution,
            choice_source=source,
            search_placeholder=_rich_choice_search_placeholder(
                resolution.matched_kinds
            ),
            thumbnail_readiness=_thumbnail_readiness_for_resolution(
                resolution,
                repository_available=request.thumbnail_repository_available,
            ),
        )
        self._snapshots[identity.query_identity or id(snapshot)] = snapshot
        return snapshot

    def _none_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
        *,
        options: Sequence[str] = (),
    ) -> PanelModelChoiceSnapshot:
        """Return a disabled snapshot for non-model choice fields."""

        return PanelModelChoiceSnapshot(
            identity=self._identity_for_request(
                request,
                model_kind=None,
                query_mode=PanelModelChoiceSnapshotKind.NONE,
                options=options,
            ),
            status=CatalogSnapshotStatus(
                CatalogSnapshotReadiness.DISABLED,
                unavailable_reason="not_model_choice_field",
            ),
            kind=PanelModelChoiceSnapshotKind.NONE,
            options=tuple(options),
            thumbnail_readiness=unavailable_thumbnail_readiness(
                "not_model_choice_field"
            ),
        )

    def _cold_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
        *,
        identity: CatalogSnapshotIdentity,
        kind: PanelModelChoiceSnapshotKind,
        model_kind: str,
    ) -> PanelModelChoiceSnapshot:
        """Return a non-consumable cold snapshot for unavailable cached rows."""

        _ = request
        resolution = literal_model_choice_resolution(
            options=(), matched_kind=model_kind
        )
        return PanelModelChoiceSnapshot(
            identity=identity,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD),
            kind=kind,
            options=(),
            model_kind=model_kind,
            resolution=resolution,
            choice_source=PanelPreparedModelChoiceSource(
                resolver=self._compatible_resolver(model_kind),
                options=(),
                context=RichChoiceContext(
                    node_name=request.node_name,
                    field_key=request.key,
                    model_kind=model_kind,
                ),
                initial_resolution=resolution,
            ),
            search_placeholder=f"Search {beautify_label(model_kind)}",
            thumbnail_readiness=unavailable_thumbnail_readiness(
                "thumbnail_variant_unavailable"
            ),
        )

    def _unavailable_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
        *,
        identity: CatalogSnapshotIdentity,
        kind: PanelModelChoiceSnapshotKind,
        model_kind: str,
        reason: str,
    ) -> PanelModelChoiceSnapshot:
        """Return an unavailable snapshot with an empty picker source."""

        resolution = RichChoiceResolution(
            items=(),
            should_use_rich_picker=True,
            matched_kinds=(model_kind,),
            option_count=0,
            enriched_count=0,
            ambiguous_count=0,
            unmatched_count=0,
            reason=reason,
            unavailable_reason=reason,
        )
        return PanelModelChoiceSnapshot(
            identity=identity.with_stale_state(
                stale=False,
                unavailable_reason=reason,
            ),
            status=CatalogSnapshotStatus(
                CatalogSnapshotReadiness.UNAVAILABLE,
                unavailable_reason=reason,
            ),
            kind=kind,
            options=(),
            model_kind=model_kind,
            resolution=resolution,
            choice_source=PanelPreparedModelChoiceSource(
                resolver=None,
                options=(),
                context=RichChoiceContext(
                    node_name=request.node_name,
                    field_key=request.key,
                    model_kind=model_kind,
                ),
                initial_resolution=resolution,
            ),
            search_placeholder=f"Search {beautify_label(model_kind)}",
            thumbnail_readiness=unavailable_thumbnail_readiness(
                "thumbnail_repository_unavailable"
            ),
        )

    def _cached_catalog_items(
        self,
        model_kind: str,
    ) -> tuple[tuple[ModelCatalogItem, ...] | None, Hashable | None]:
        """Return foreground-safe cached or local metadata rows for a model kind."""

        catalog = self._model_catalog_service
        if catalog is None:
            return None, None
        prepared = prepared_model_catalog_rows(catalog, model_kind)
        return prepared.items, prepared.revision

    def _prepared_eligible_catalog(
        self,
    ) -> tuple[tuple[ModelCatalogItem, ...], Hashable] | None:
        """Return complete prepared rows for every picker-eligible model catalog."""

        catalog = self._model_catalog_service
        resolver = self._model_choice_resolver
        if catalog is None or resolver is None:
            return None
        items: list[ModelCatalogItem] = []
        revisions: list[tuple[str, Hashable]] = []
        for model_kind in resolver.enabled_kinds:
            prepared = prepared_model_catalog_rows(catalog, model_kind)
            if prepared.items is None:
                return None
            items.extend(prepared.items)
            revision = prepared.revision
            revisions.append(
                (
                    model_kind,
                    revision if isinstance(revision, Hashable) else repr(revision),
                )
            )
        return tuple(items), tuple(revisions)

    def _compatible_resolver(
        self,
        model_kind: str | None,
    ) -> RichChoiceResolver | None:
        """Return the shared resolver only when it can refresh the model kind."""

        if model_kind is None or self._model_choice_resolver is None:
            return None
        if model_kind not in self._model_choice_resolver.enabled_kinds:
            return None
        return self._model_choice_resolver

    def _identity_for_request(
        self,
        request: PanelModelChoiceSnapshotRequest,
        *,
        model_kind: str | None,
        query_mode: PanelModelChoiceSnapshotKind,
        options: Sequence[str] = (),
        catalog_revision: Hashable | None = None,
    ) -> CatalogSnapshotIdentity:
        """Return a stable identity for one prepared model-choice snapshot."""

        query_identity = (
            query_mode.value,
            request.cube_alias,
            request.node_name,
            request.node_type
            if isinstance(request.node_type, Hashable)
            else repr(request.node_type),
            request.key,
            model_kind,
            tuple(options),
        )
        return CatalogSnapshotIdentity(
            panel_context_id=self._panel_context_id_provider(),
            catalog_revision=catalog_revision,
            query_identity=query_identity,
            request_identity=(
                request.cube_alias,
                request.node_name,
                request.key,
                repr(request.value),
            ),
        )


def _thumbnail_readiness_for_resolution(
    resolution: RichChoiceResolution,
    *,
    repository_available: bool,
) -> MediaThumbnailReadiness:
    """Return metadata-only thumbnail readiness for prepared model choices."""

    storage_key = _first_resolution_thumbnail_storage_key(resolution)
    if storage_key is None:
        return unavailable_thumbnail_readiness("thumbnail_variant_unavailable")
    if not repository_available:
        return unavailable_thumbnail_readiness("thumbnail_repository_unavailable")
    return MediaThumbnailReadiness(
        status=MediaThumbnailReadinessStatus.PENDING,
        storage_key=storage_key,
    )


def _first_resolution_thumbnail_storage_key(
    resolution: RichChoiceResolution,
) -> str | None:
    """Return the first prepared thumbnail storage key without reading assets."""

    for item in resolution.items:
        for variant in item.thumbnail_variants:
            if variant.storage_key:
                return variant.storage_key
    return None


def _rich_choice_search_placeholder(matched_kinds: tuple[str, ...]) -> str:
    """Return a concise search placeholder for one rich choice resolution."""

    if len(matched_kinds) == 1:
        return f"Search {beautify_label(matched_kinds[0])}"
    return "Search models"


__all__ = [
    "PanelModelChoiceSnapshot",
    "PanelModelChoiceSnapshotController",
    "PanelModelChoiceSnapshotKind",
    "PanelModelChoiceSnapshotRequest",
    "PanelPreparedModelChoiceSource",
]
