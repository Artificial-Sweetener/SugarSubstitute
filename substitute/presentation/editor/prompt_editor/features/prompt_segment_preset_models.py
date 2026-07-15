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

"""Define saved prompt-segment menu, source, and snapshot models."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Protocol

from substitute.presentation.editor.prompt_editor.features.catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptFeatureSnapshotIdentity,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetMenuItem:
    """Describe one saved prompt segment insert action."""

    label: str
    text: str
    tooltip: str


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetMenuSection:
    """Group prompt segment insert actions by matching scope."""

    title: str
    presets: tuple[PromptSegmentPresetMenuItem, ...]


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetMenuModel:
    """Return context menu data and save scopes for prompt segments."""

    sections: tuple[PromptSegmentPresetMenuSection, ...] = ()
    save_scopes: tuple[PresetSaveScope, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetSourceSnapshot:
    """Publish prompt segment preset data prepared by the backing source."""

    menu_model: PromptSegmentPresetMenuModel
    catalog_identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus


class PromptSegmentPresetSource(Protocol):
    """Provide prompt segment preset data to the prompt editor."""

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return prepared prompt segment menu data for the active context."""

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: PresetSaveScope,
    ) -> None:
        """Persist selected prompt text as a named segment."""


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetSaveDialogRequest:
    """Describe a save-segment dialog request without constructing a widget."""

    parent: object
    title: str
    scopes: tuple[PresetSaveScope, ...]
    selected_text: str


PromptSegmentPresetDialogResult = tuple[str, PresetSaveScope] | None
PromptSegmentPresetDialogRunner = Callable[
    [PromptSegmentPresetSaveDialogRequest],
    PromptSegmentPresetDialogResult,
]


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetSaveState:
    """Publish selected-text and save-action readiness for context menus."""

    source_available: bool
    selected_text: str
    ready: bool
    disabled_reason: str | None = None
    save_scopes: tuple[PresetSaveScope, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptSegmentPresetSnapshot:
    """Publish prepared prompt segment preset menu, save, and insert state."""

    identity: PromptFeatureSnapshotIdentity
    menu_model: PromptSegmentPresetMenuModel | None
    save_state: PromptSegmentPresetSaveState
    insert_ready: bool
    selected_text_identity: Hashable | None = None
    selection_range: tuple[int, int] | None = None
    read_only: bool = False
    unavailable_reason: str | None = None
    catalog_identity: CatalogSnapshotIdentity = field(
        default_factory=CatalogSnapshotIdentity
    )
    status: CatalogSnapshotStatus = field(
        default_factory=lambda: CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD)
    )


__all__ = [
    "PromptSegmentPresetDialogResult",
    "PromptSegmentPresetDialogRunner",
    "PromptSegmentPresetMenuItem",
    "PromptSegmentPresetMenuModel",
    "PromptSegmentPresetMenuSection",
    "PromptSegmentPresetSaveDialogRequest",
    "PromptSegmentPresetSaveState",
    "PromptSegmentPresetSnapshot",
    "PromptSegmentPresetSource",
    "PromptSegmentPresetSourceSnapshot",
]
