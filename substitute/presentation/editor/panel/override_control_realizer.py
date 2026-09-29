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

"""Realize compact toolbar controls from pinned override projections."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.display_labels import beautify_label
from substitute.application.model_metadata import (
    ThumbnailAssetRepository,
    model_kind_for_field,
)
from substitute.application.node_behavior import (
    FieldPresentation,
    ResolvedFieldSpec,
    is_choice_field_type,
)
from substitute.application.overrides import PinnedOverrideControl
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.presentation.editor.panel.factories.choice_factory import (
    resolve_choice_options_for_field,
)
from substitute.presentation.editor.panel.factories.field_build_outcome import (
    EditorFieldBuildKind,
)
from substitute.presentation.editor.panel.factories.field_build_resolver import (
    resolve_editor_field_build,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    LAYOUT_HANDLED,
    build_widget_for_field_spec,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.override_control_identity import (
    identify_override_surface,
)
from substitute.presentation.editor.panel.override_model_picker_reconciler import (
    reconcile_model_override_picker,
)
from substitute.presentation.editor.panel.override_workflow_state import (
    compact_override_log_value,
)
from substitute.presentation.model_discovery import EmptyModelPickerAction
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.widgets import tooltips
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_warning,
    log_warning_exception,
)

_LOGGER = get_logger("presentation.editor.panel.override_control_realizer")
_TOOLBAR_MAX_WIDGET_WIDTH = 180
_TOOLBAR_CONTROL_HEIGHT = 32


@dataclass(frozen=True, slots=True)
class OverrideControlRealization:
    """Describe one completed toolbar label/control pair and its reuse identity."""

    label_widget: Any
    widget: Any
    signature: tuple[object, ...]


class OverrideControlRealizer:
    """Build and normalize override controls without owning toolbar placement."""

    def __init__(
        self,
        *,
        parent: Callable[[], Any],
        node_definition_gateway: NodeDefinitionGateway,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        danbooru_url_import_service: DanbooruUrlImportService | None,
        danbooru_wiki_service: DanbooruWikiContentService | None,
        danbooru_image_preview_service: DanbooruImagePreviewService | None,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None,
        prompt_spellcheck_service: PromptSpellcheckService | None,
        model_choice_snapshot_controller: PanelModelChoiceSnapshotController | None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None,
        empty_model_picker_action: EmptyModelPickerAction | None,
        model_updates: ModelUpdatePickerBridge | None,
    ) -> None:
        """Capture the field-factory collaborators needed for toolbar realization."""

        self._parent = parent
        self._node_definition_gateway = node_definition_gateway
        self._prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self._prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self._danbooru_url_import_service = danbooru_url_import_service
        self._danbooru_wiki_service = danbooru_wiki_service
        self._danbooru_image_preview_service = danbooru_image_preview_service
        self._danbooru_recent_posts_service = danbooru_recent_posts_service
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._prompt_spellcheck_service = prompt_spellcheck_service
        self._model_choice_snapshot_controller = model_choice_snapshot_controller
        self._thumbnail_asset_repository = thumbnail_asset_repository
        self._model_metadata_action_handler = model_metadata_action_handler
        self._empty_model_picker_action = empty_model_picker_action
        self._model_updates = model_updates

    def realize(
        self,
        control: PinnedOverrideControl,
    ) -> OverrideControlRealization | None:
        """Build one complete override surface or report an unavailable control."""

        log_debug(
            _LOGGER,
            "create override widget started",
            override_key=control.override_key,
            value=compact_override_log_value(control.value),
            representative_cube=control.spec.cube_alias,
            representative_node=control.spec.node_name,
            representative_class=control.spec.class_type,
            representative_field=control.spec.field_key,
            spec_value=compact_override_log_value(control.spec.value),
            spec_raw_value=compact_override_log_value(control.spec.raw_value),
            spec_value_source=control.spec.value_source.value,
        )
        widget_spec = self.toolbar_field_spec(control.spec, control.value)
        parent = self._parent()

        def build_override_surface() -> object | None:
            """Invoke the raw factory inside the shared typed outcome boundary."""

            return cast(
                object | None,
                build_widget_for_field_spec(
                    parent=parent,
                    field_spec=widget_spec,
                    prompt_autocomplete_gateway=self._prompt_autocomplete_gateway,
                    prompt_wildcard_catalog_gateway=(
                        self._prompt_wildcard_catalog_gateway
                    ),
                    danbooru_url_import_service=self._danbooru_url_import_service,
                    danbooru_wiki_service=self._danbooru_wiki_service,
                    danbooru_image_preview_service=(
                        self._danbooru_image_preview_service
                    ),
                    danbooru_recent_posts_service=(self._danbooru_recent_posts_service),
                    prompt_lora_catalog_service=self._prompt_lora_catalog_service,
                    prompt_spellcheck_service=self._prompt_spellcheck_service,
                    model_choice_snapshot_controller=(
                        self._model_choice_snapshot_controller
                    ),
                    thumbnail_asset_repository=self._thumbnail_asset_repository,
                    model_metadata_action_handler=(self._model_metadata_action_handler),
                    empty_model_picker_action=self._empty_model_picker_action,
                    model_updates=self._model_updates,
                    node_definition_gateway=self._node_definition_gateway,
                ),
            )

        outcome = resolve_editor_field_build(
            field_spec=widget_spec,
            build=build_override_surface,
            layout_handled_sentinel=LAYOUT_HANDLED,
        )
        if outcome.kind is EditorFieldBuildKind.ERROR:
            error = outcome.error
            if error is not None:
                log_warning_exception(
                    _LOGGER,
                    "Failed to build pinned override control",
                    error=error,
                    override_key=control.override_key,
                    class_type=control.spec.class_type,
                    field_key=control.spec.field_key,
                )
            return None
        if not outcome.rendered:
            log_warning(
                _LOGGER,
                "Skipped unavailable pinned override control",
                override_key=control.override_key,
                class_type=control.spec.class_type,
                field_key=control.spec.field_key,
                outcome=outcome.kind.value,
                reason=outcome.reason,
            )
            return None
        result = outcome.surface
        if result is None:
            return None
        widget = result[0] if isinstance(result, tuple) else result
        label_widget = CaptionLabel(beautify_label(control.label), parent)
        label_widget.setContentsMargins(4, 0, 4, 0)
        self.apply_toolbar_label_size(label_widget)
        self.apply_toolbar_widget_size(control.spec, widget)
        identify_override_surface(
            override_key=control.override_key,
            label_widget=label_widget,
            control_widget=widget,
        )
        tooltips.bind_fluent_tooltip(
            label_widget,
            tooltips.tooltip_from_field_meta(widget_spec.meta_info),
            label_widget,
            cast(QWidget, widget),
            show_delay_ms=600,
        )
        log_debug(
            _LOGGER,
            "create override widget completed",
            override_key=control.override_key,
            widget_type=type(widget).__name__,
            label_type=type(label_widget).__name__,
            widget_metadata=compact_override_log_value(
                widget.property("input_metadata")
                if hasattr(widget, "property")
                else None
            ),
        )
        return OverrideControlRealization(
            label_widget=label_widget,
            widget=widget,
            signature=self.signature(control),
        )

    def normalize(
        self,
        control: PinnedOverrideControl,
        label_widget: Any,
        widget: Any,
    ) -> None:
        """Restore compact sizing and live model choices on a reused control."""

        self.apply_toolbar_label_size(label_widget)
        self.apply_toolbar_widget_size(control.spec, widget)
        reconcile_model_override_picker(
            control=control,
            widget=widget,
            snapshots=self._model_choice_snapshot_controller,
            node_definitions=self._node_definition_gateway,
            thumbnail_repository_available=(
                self._thumbnail_asset_repository is not None
            ),
        )

    def signature(self, control: PinnedOverrideControl) -> tuple[object, ...]:
        """Return the render contract used to decide toolbar control reuse."""

        spec = control.spec
        behavior = spec.field_behavior
        model_options_are_dynamic = (
            model_kind_for_field(
                class_type=spec.class_type,
                input_key=spec.field_key,
            )
            is not None
        )
        return (
            control.override_key,
            control.label,
            repr(control.value),
            spec.class_type,
            spec.field_key,
            spec.field_type,
            repr(sorted(spec.constraints.items())),
            "dynamic_model_options"
            if model_options_are_dynamic
            else repr(spec.field_info),
            ()
            if model_options_are_dynamic
            else self._choice_inventory_signature(control),
            behavior.presentation.value,
            behavior.control_name,
            repr(sorted(behavior.style.items())),
        )

    def _choice_inventory_signature(
        self,
        control: PinnedOverrideControl,
    ) -> tuple[str, ...]:
        """Return choice options that affect rendering and control reuse."""

        spec = control.spec
        if not is_choice_field_type(spec.field_type):
            return ()
        return resolve_choice_options_for_field(
            key=spec.field_key,
            node_type=spec.class_type,
            node_definition_gateway=self._node_definition_gateway,
            field_info=spec.field_info,
            value=control.value,
        )

    @staticmethod
    def toolbar_field_spec(spec: ResolvedFieldSpec, value: Any) -> ResolvedFieldSpec:
        """Derive a toolbar render spec from one representative field spec."""

        toolbar_meta = dict(spec.meta_info)
        toolbar_meta["node_data"] = None
        return ResolvedFieldSpec(
            cube_alias=spec.cube_alias,
            node_name=spec.node_name,
            class_type=spec.class_type,
            field_key=spec.field_key,
            field_type=spec.field_type,
            constraints=dict(spec.constraints),
            meta_info=toolbar_meta,
            field_info=list(spec.field_info) if spec.field_info is not None else None,
            value=value,
            field_behavior=spec.field_behavior,
            label_source=spec.label_source,
            raw_value=spec.raw_value,
            value_source=spec.value_source,
        )

    @staticmethod
    def apply_toolbar_label_size(label_widget: Any) -> None:
        """Keep toolbar labels from absorbing horizontal toolbar slack."""

        if hasattr(label_widget, "setSizePolicy"):
            label_widget.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Preferred,
            )

    @staticmethod
    def apply_toolbar_widget_size(spec: ResolvedFieldSpec, widget: Any) -> None:
        """Keep controls compact while allowing width-pressure shrinkage."""

        if spec.field_behavior.presentation is FieldPresentation.SEED_BOX:
            restore_size_contract = getattr(widget, "restore_size_contract", None)
            if callable(restore_size_contract):
                restore_size_contract()
            return
        if hasattr(widget, "setSizePolicy"):
            widget.setSizePolicy(
                QSizePolicy.Policy.Maximum,
                QSizePolicy.Policy.Fixed,
            )
        if spec.field_type in {"INT", "FLOAT"}:
            if hasattr(widget, "setFixedHeight"):
                widget.setFixedHeight(_TOOLBAR_CONTROL_HEIGHT)
            return
        if hasattr(widget, "setMaximumWidth"):
            widget.setMaximumWidth(_TOOLBAR_MAX_WIDGET_WIDTH)


__all__ = ["OverrideControlRealization", "OverrideControlRealizer"]
