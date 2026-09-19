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

"""Define immutable panel model-choice snapshots and their prepared source."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from substitute.application.model_metadata import (
    RichChoiceContext,
    RichChoiceItem,
    RichChoiceResolution,
    RichChoiceResolver,
    RichChoiceSource,
)
from substitute.application.node_behavior import FieldBehavior
from substitute.domain.model_suggestions import ModelSuggestionContext
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.widgets.media_wall import (
    MediaThumbnailReadiness,
    unavailable_thumbnail_readiness,
)
from sugarsubstitute_shared.localization import ApplicationText, app_text


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
    target_model: str = ""
    thumbnail_repository_available: bool = False


@dataclass(frozen=True, slots=True)
class PanelModelChoiceSnapshot:
    """Publish prepared model-choice data for foreground widget construction."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    kind: PanelModelChoiceSnapshotKind
    options: tuple[str, ...] = ()
    model_kind: str | None = None
    suggestion_context: ModelSuggestionContext | None = None
    resolution: RichChoiceResolution | None = None
    choice_source: RichChoiceSource | None = None
    search_placeholder: ApplicationText = app_text("Search models")
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

    @property
    def can_offer_suggestions(self) -> bool:
        """Return whether authoritative empty catalog data supports discovery."""

        return (
            self.status.readiness is CatalogSnapshotReadiness.WARM
            and self.suggestion_context is not None
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


__all__ = [
    "PanelModelChoiceSnapshot",
    "PanelModelChoiceSnapshotKind",
    "PanelModelChoiceSnapshotRequest",
    "PanelPreparedModelChoiceSource",
]
