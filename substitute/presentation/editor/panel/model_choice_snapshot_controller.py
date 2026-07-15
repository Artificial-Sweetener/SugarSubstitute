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

from collections import Counter
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from substitute.application.display_labels import beautify_label
from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogLookup,
    model_kind_for_field,
    RichChoiceContext,
    RichChoiceItem,
    RichChoiceResolution,
    RichChoiceResolver,
    RichChoiceSource,
)
from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    extract_live_list_options,
    is_choice_field_type,
)
from substitute.application.ports import NodeDefinitionGateway
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
    log_panel_projection_event,
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.model_choice_snapshot_controller")
_MODEL_LIST_FIELD_KEYS = frozenset(
    {
        ("CheckpointLoaderSimple", "ckpt_name"),
        ("VAELoader", "vae_name"),
        ("LoraLoader", "lora_name"),
        ("LoraLoaderModelOnly", "lora_name"),
        ("Power Lora Loader (rgthree)", "lora"),
        ("SimpleSyrup.SimpleLoadAnima", "diffusion_model"),
        ("UNETLoader", "unet_name"),
    }
)
_MODEL_LIST_KEY_FRAGMENTS = (
    "ckpt",
    "checkpoint",
    "vae",
    "lora",
    "diffusion",
    "unet",
)


class PanelModelChoiceSnapshotKind(StrEnum):
    """Classify the prepared choice payload a field factory may consume."""

    NONE = "none"
    EXPLICIT_MODEL_PICKER = "explicit_model_picker"
    RICH_MODEL_PICKER = "rich_model_picker"
    LITERAL_MODEL_PICKER = "literal_model_picker"


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
        if not _should_attempt_rich_choice(request.node_type, request.key):
            return self._none_snapshot(request)
        return self._rich_list_choice_snapshot(request)

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
        resolution = _catalog_resolution(
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

    def _rich_list_choice_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
    ) -> PanelModelChoiceSnapshot:
        """Prepare a rich picker snapshot for a model-backed LIST field."""

        snapshot_started_at = panel_projection_observability_started_at()
        options = _resolve_list_choice_options(
            key=request.key,
            node_type=request.node_type,
            node_definition_gateway=request.node_definition_gateway,
            field_info=request.field_info,
        )
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
        if not options:
            return self._none_snapshot(request)

        model_kind = model_kind_for_field(
            class_type=request.node_type if isinstance(request.node_type, str) else "",
            input_key=request.key,
        )
        identity = self._identity_for_request(
            request,
            model_kind=model_kind,
            query_mode=PanelModelChoiceSnapshotKind.RICH_MODEL_PICKER,
            options=options,
        )
        context = RichChoiceContext(
            node_class=request.node_type
            if isinstance(request.node_type, str)
            else None,
            node_name=request.node_name,
            field_key=request.key,
            model_kind=model_kind,
        )
        if model_kind is None:
            return self._none_snapshot(request, options=options)
        catalog_items, revision = self._cached_catalog_items(model_kind)
        identity = self._identity_for_request(
            request,
            model_kind=model_kind,
            query_mode=PanelModelChoiceSnapshotKind.RICH_MODEL_PICKER,
            options=options,
            catalog_revision=revision,
        )
        if catalog_items is None:
            return self._literal_snapshot(
                request,
                identity=identity,
                options=options,
                context=context,
                status=CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD),
            )
        resolution = _catalog_resolution(
            options=options,
            catalog_items=catalog_items,
            matched_kind=model_kind,
            reason="model-backed field consumed prepared catalog snapshot",
        )
        if not resolution.should_use_rich_picker:
            return self._literal_snapshot(
                request,
                identity=identity,
                options=options,
                context=context,
                status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            )
        source = PanelPreparedModelChoiceSource(
            resolver=self._compatible_resolver(model_kind),
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

    def _literal_snapshot(
        self,
        request: PanelModelChoiceSnapshotRequest,
        *,
        identity: CatalogSnapshotIdentity,
        options: Sequence[str],
        context: RichChoiceContext,
        status: CatalogSnapshotStatus,
    ) -> PanelModelChoiceSnapshot:
        """Return a literal model-picker snapshot for cold or unenriched metadata."""

        resolution = _literal_model_choice_resolution(
            options=options,
            matched_kind=context.model_kind,
        )
        source = PanelPreparedModelChoiceSource(
            resolver=self._compatible_resolver(context.model_kind),
            options=options,
            context=context,
            initial_resolution=resolution,
        )
        snapshot = PanelModelChoiceSnapshot(
            identity=identity,
            status=status,
            kind=PanelModelChoiceSnapshotKind.LITERAL_MODEL_PICKER,
            options=tuple(options),
            model_kind=context.model_kind,
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
        log_panel_projection_event(
            "model_choice.literal_snapshot",
            node_name=context.node_name or request.node_name,
            field_key=request.key,
            node_class=context.node_class or "",
            model_kind=context.model_kind or "",
            option_count=len(options),
            readiness=status.readiness.value,
        )
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
        resolution = _literal_model_choice_resolution(
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


def _should_attempt_rich_choice(node_type: object, key: str) -> bool:
    """Return whether a choice field is likely to represent a model file choice."""

    if isinstance(node_type, str) and (node_type, key) in _MODEL_LIST_FIELD_KEYS:
        return True
    normalized_key = key.strip().casefold()
    return any(fragment in normalized_key for fragment in _MODEL_LIST_KEY_FRAGMENTS)


def _resolve_live_choice_options(
    *,
    node_definition_gateway: NodeDefinitionGateway,
    node_type: str,
    key: str,
) -> list[str]:
    """Return normalized live choice options for one node input when available."""

    live_def = node_definition_gateway.get_node_definition(node_type)
    node_def = live_def.get(node_type, {})
    if not isinstance(node_def, dict):
        return []
    input_section = node_def.get("input", {})
    if not isinstance(input_section, dict):
        return []
    required = input_section.get("required", {})
    optional = input_section.get("optional", {})
    live_info = (required.get(key) if isinstance(required, dict) else None) or (
        optional.get(key) if isinstance(optional, dict) else None
    )
    return list(extract_live_list_options(live_info))


def _resolve_list_choice_options(
    *,
    key: str,
    node_type: object,
    node_definition_gateway: object,
    field_info: object,
) -> list[str]:
    """Return exact Comfy choice options from live definitions or field info."""

    options: list[str] | None = None
    if (
        node_type
        and isinstance(node_type, str)
        and isinstance(node_definition_gateway, NodeDefinitionGateway)
    ):
        options = _resolve_live_choice_options(
            node_definition_gateway=node_definition_gateway,
            node_type=node_type,
            key=key,
        )
    if options:
        return options
    return list(extract_live_list_options(field_info))


def _catalog_resolution(
    *,
    options: Sequence[str],
    catalog_items: Sequence[ModelCatalogItem],
    matched_kind: str,
    reason: str,
) -> RichChoiceResolution:
    """Resolve exact option values against prepared catalog rows."""

    items_by_value: Mapping[str, tuple[ModelCatalogItem, ...]] = (
        _catalog_items_by_value(catalog_items)
    )
    rendered_items: list[RichChoiceItem] = []
    enriched_count = 0
    ambiguous_count = 0
    unmatched_count = 0
    for option in options:
        candidates = items_by_value.get(str(option), ())
        if not candidates:
            unmatched_count += 1
            rendered_items.append(_literal_model_choice_item(str(option)))
            continue
        is_ambiguous = len(candidates) > 1
        if is_ambiguous:
            ambiguous_count += 1
        else:
            enriched_count += 1
        rendered_items.append(
            _rich_choice_item(str(option), candidates[0], is_ambiguous)
        )

    should_use_rich_picker = bool(options) and (
        enriched_count > 0 or ambiguous_count > 0
    )
    return RichChoiceResolution(
        items=tuple(rendered_items),
        should_use_rich_picker=should_use_rich_picker,
        matched_kinds=(matched_kind,),
        option_count=len(options),
        enriched_count=enriched_count,
        ambiguous_count=ambiguous_count,
        unmatched_count=unmatched_count,
        reason=reason,
    )


def _catalog_items_by_value(
    catalog_items: Sequence[ModelCatalogItem],
) -> Mapping[str, tuple[ModelCatalogItem, ...]]:
    """Return catalog items grouped by exact Comfy backend value."""

    counter = Counter(item.backend_value for item in catalog_items)
    grouped: dict[str, list[ModelCatalogItem]] = {}
    for item in catalog_items:
        grouped.setdefault(item.backend_value, []).append(item)
    return {
        value: tuple(
            _with_collision_metadata(item, collision_count=counter[value])
            for item in items
        )
        for value, items in grouped.items()
    }


def _with_collision_metadata(
    item: ModelCatalogItem,
    *,
    collision_count: int,
) -> ModelCatalogItem:
    """Return item collision metadata without mutating cached catalog rows."""

    if item.collision_count == collision_count and item.has_collision == (
        collision_count > 1
    ):
        return item
    try:
        from dataclasses import replace

        return replace(
            item,
            collision_count=collision_count,
            has_collision=collision_count > 1,
        )
    except TypeError as error:
        log_warning(
            _LOGGER,
            "Failed to patch model catalog collision metadata",
            model_kind=item.kind,
            backend_value=item.backend_value,
            error_type=type(error).__name__,
        )
        return item


def _rich_choice_item(
    value: str,
    catalog_item: ModelCatalogItem,
    is_ambiguous: bool,
) -> RichChoiceItem:
    """Return one model-enriched choice item from cached catalog metadata."""

    title = catalog_item.display_name or _literal_model_choice_title(value)
    search_parts = (
        catalog_item.search_text,
        title,
        value.replace("\\", "/"),
        catalog_item.display_subtitle or "",
    )
    return RichChoiceItem(
        value=value,
        title=title,
        subtitle=catalog_item.display_subtitle,
        search_text=" ".join(part for part in search_parts if part).casefold(),
        model_kind=catalog_item.kind,
        catalog_item=catalog_item,
        thumbnail_variants=catalog_item.thumbnail_variants,
        is_enriched=not is_ambiguous,
        is_ambiguous=is_ambiguous,
    )


def _literal_model_choice_resolution(
    *,
    options: Sequence[str],
    matched_kind: str | None,
) -> RichChoiceResolution:
    """Return a picker-forcing resolution from exact Comfy options only."""

    items = tuple(_literal_model_choice_item(str(option)) for option in options)
    matched_kinds = (matched_kind,) if matched_kind else ()
    return RichChoiceResolution(
        items=items,
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=len(items),
        enriched_count=0,
        ambiguous_count=0,
        unmatched_count=len(items),
        reason="model-backed field rendered before metadata enrichment",
    )


def _literal_model_choice_item(value: str) -> RichChoiceItem:
    """Return one selectable model choice without metadata enrichment."""

    title = _literal_model_choice_title(value)
    return RichChoiceItem(
        value=value,
        title=title,
        subtitle=None,
        search_text=f"{title} {value}".replace("\\", "/").casefold(),
        model_kind=None,
        catalog_item=None,
        thumbnail_variants=(),
        is_enriched=False,
        is_ambiguous=False,
    )


def _literal_model_choice_title(value: str) -> str:
    """Return a readable title for a literal model backend value."""

    normalized = str(value).replace("\\", "/").strip()
    if not normalized:
        return ""
    title = normalized.rsplit("/", 1)[-1]
    for suffix in (".safetensors", ".ckpt", ".pt"):
        if title.casefold().endswith(suffix):
            return title[: -len(suffix)] or title
    return title


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
