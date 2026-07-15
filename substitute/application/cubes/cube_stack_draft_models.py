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

"""Build Qt-free draft cube-stack models for picker drawer editing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from substitute.application.cubes.cube_tab_presentation import (
    build_cube_tab_presentation,
)
from substitute.application.ports import CubeCatalogRecord

CubeStackDraftEntrySource = Literal["existing", "new"]


@dataclass(frozen=True)
class CubeStackDraftEntry:
    """Represent one entry in the temporary cube-stack draft."""

    draft_id: str
    source: CubeStackDraftEntrySource
    cube_id: str
    display_name: str
    secondary_text: str
    icon: object | None
    existing_alias: str | None = None
    content_hash: str = ""
    catalog_revision: str = ""


@dataclass(frozen=True)
class CubeStackDraft:
    """Represent the initial ordered stack draft shown by the drawer."""

    entries: tuple[CubeStackDraftEntry, ...]

    @property
    def is_empty(self) -> bool:
        """Return whether this draft has no entries."""

        return not self.entries


@dataclass(frozen=True)
class CubeStackDraftResult:
    """Represent the final ordered stack draft accepted by the user."""

    entries: tuple[CubeStackDraftEntry, ...]

    @property
    def is_empty(self) -> bool:
        """Return whether no draft entries remain."""

        return not self.entries

    def has_changes_from(self, initial_draft: CubeStackDraft) -> bool:
        """Return whether this result differs from the initial drawer draft."""

        return self.entries != initial_draft.entries


def cube_stack_draft_from_workflow(workflow: object) -> CubeStackDraft:
    """Build the initial drawer draft from workflow-local cube state."""

    cubes = getattr(workflow, "cubes", {})
    stack_order = getattr(workflow, "stack_order", [])
    if not isinstance(cubes, dict) or not isinstance(stack_order, list):
        return CubeStackDraft(entries=())

    entries: list[CubeStackDraftEntry] = []
    for raw_alias in stack_order:
        alias = str(raw_alias)
        cube_state = cubes.get(alias)
        if cube_state is None:
            continue
        cube_id = str(getattr(cube_state, "cube_id", alias))
        version = str(getattr(cube_state, "version", ""))
        presentation = build_cube_tab_presentation(
            alias=alias,
            cube_id=cube_id,
            version=version,
        )
        entries.append(
            CubeStackDraftEntry(
                draft_id=f"existing:{alias}",
                source="existing",
                cube_id=cube_id,
                display_name=presentation.primary_text,
                secondary_text=presentation.secondary_text,
                icon=_cube_state_icon_descriptor(cube_state),
                existing_alias=alias,
                content_hash=_cube_state_ui_text(cube_state, "content_hash"),
                catalog_revision=_cube_state_ui_text(cube_state, "catalog_revision"),
            )
        )
    return CubeStackDraft(entries=tuple(entries))


def cube_stack_draft_entry_from_record(
    record: CubeCatalogRecord,
    *,
    draft_id: str | None = None,
) -> CubeStackDraftEntry:
    """Create one new draft stack entry from a catalog record."""

    presentation = build_cube_tab_presentation(
        alias=record.display_name,
        cube_id=record.cube_id,
        version=record.version,
    )
    return CubeStackDraftEntry(
        draft_id=draft_id or uuid4().hex,
        source="new",
        cube_id=record.cube_id,
        display_name=record.display_name,
        secondary_text=presentation.secondary_text,
        icon=record.icon,
        existing_alias=None,
        content_hash=record.content_hash,
        catalog_revision=record.catalog_revision,
    )


def cube_stack_draft_result(
    entries: list[CubeStackDraftEntry],
) -> CubeStackDraftResult:
    """Return a validated immutable draft result."""

    _validate_draft_entries(entries)
    return CubeStackDraftResult(entries=tuple(entries))


def cube_stack_draft(entries: list[CubeStackDraftEntry]) -> CubeStackDraft:
    """Return a validated immutable initial draft."""

    _validate_draft_entries(entries)
    return CubeStackDraft(entries=tuple(entries))


def _validate_draft_entries(entries: list[CubeStackDraftEntry]) -> None:
    """Validate draft identity and source-specific invariants."""

    draft_ids = [entry.draft_id for entry in entries]
    if len(draft_ids) != len(set(draft_ids)):
        raise ValueError("Draft cube ids must be unique")

    existing_aliases: list[str] = []
    for entry in entries:
        if entry.source == "existing":
            if not entry.existing_alias:
                raise ValueError("Existing draft entries must include an alias")
            existing_aliases.append(entry.existing_alias)
            continue
        if entry.existing_alias is not None:
            raise ValueError("New draft entries must not include an existing alias")

    if len(existing_aliases) != len(set(existing_aliases)):
        raise ValueError("Existing draft aliases must be unique")


def _cube_state_icon_descriptor(cube_state: object) -> object | None:
    """Return the persisted cube icon descriptor from workflow state."""

    ui_payload = getattr(cube_state, "ui", None)
    if isinstance(ui_payload, dict):
        return ui_payload.get("cube_icon")
    return None


def _cube_state_ui_text(cube_state: object, key: str) -> str:
    """Return one persisted cube UI text value from workflow state."""

    ui_payload = getattr(cube_state, "ui", None)
    if not isinstance(ui_payload, dict):
        return ""
    value = ui_payload.get(key)
    return value if isinstance(value, str) else ""


__all__ = [
    "CubeStackDraft",
    "CubeStackDraftEntry",
    "CubeStackDraftEntrySource",
    "CubeStackDraftResult",
    "cube_stack_draft",
    "cube_stack_draft_entry_from_record",
    "cube_stack_draft_from_workflow",
    "cube_stack_draft_result",
]
