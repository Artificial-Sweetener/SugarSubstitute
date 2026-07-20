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

"""Build cube picker entries and section groupings."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage, app_text

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Literal

from substitute.application.cubes.cube_tab_presentation import (
    build_cube_tab_presentation,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.domain.cube_library import (
    CubeIconDescriptor,
    CubeSourceMetadata,
)

CubePickerRole = Literal["start", "middle", "end", "unclassified"]
CubePickerViewMode = Literal["kind", "pack", "model"]
CubeSearchTargetKind = Literal[
    "cube",
    "model",
    "pack",
    "node",
    "definition",
    "control",
    "source",
    "technical",
]

_ROLE_TITLES: dict[CubePickerRole, ApplicationMessage] = {
    "start": app_text("Start cubes"),
    "middle": app_text("Middle cubes"),
    "end": app_text("End cubes"),
    "unclassified": app_text("Other cubes"),
}
_ALL_SECTION_ORDER: tuple[CubePickerRole, ...] = (
    "start",
    "middle",
    "end",
    "unclassified",
)
_UNSPECIFIED_MODEL_KEY = "unspecified"
_UNSPECIFIED_MODEL_TITLE = app_text("Unspecified model")


@dataclass(frozen=True)
class CubeSearchTerm:
    """Describe one typed cube metadata term before entry-specific target binding."""

    text: str
    kind: CubeSearchTargetKind


@dataclass(frozen=True)
class CubeSearchTarget:
    """Describe one structured text value searched by the cube picker."""

    text: str
    kind: CubeSearchTargetKind
    cube_id: str
    source_label: str | None = None
    priority: int = 0


@dataclass(frozen=True)
class CubePickerEntry:
    """Represent one cube as rendered and selected by the picker."""

    cube_id: str
    display_name: str
    version: str
    description: str
    secondary_text: str
    icon: CubeIconDescriptor | None
    source: CubeSourceMetadata | None
    role: CubePickerRole
    input_count: int
    output_count: int
    supported_models: tuple[str, ...]
    search_terms: tuple[str, ...]
    search_targets: tuple[CubeSearchTerm, ...]
    content_hash: str = ""
    catalog_revision: str = ""


@dataclass(frozen=True)
class CubePickerClassification:
    """Describe picker-owned cube boundary classification."""

    input_count: int
    output_count: int
    role: CubePickerRole
    supported_models: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()
    search_targets: tuple[CubeSearchTerm, ...] = ()


@dataclass(frozen=True)
class CubePickerSection:
    """Represent one visible section in the cube picker."""

    key: str
    title: str
    entries: tuple[CubePickerEntry, ...]
    role: CubePickerRole | None = None


@dataclass(frozen=True)
class CubePickerRoleSection:
    """Represent one role subsection within a model-grouped picker section."""

    key: CubePickerRole
    title: str
    entries: tuple[CubePickerEntry, ...]


@dataclass(frozen=True)
class CubePickerModelRoleSection:
    """Represent one supported-model section with role subsections."""

    key: str
    title: str
    role_sections: tuple[CubePickerRoleSection, ...]


@dataclass(frozen=True)
class CubePickerPackGroup:
    """Describe the source-pack group for one picker entry."""

    key: str
    title: str
    local: bool
    unknown: bool


def build_cube_picker_entries(
    records: list[CubeCatalogRecord],
    *,
    classifications: Mapping[str, CubePickerClassification] | None = None,
) -> tuple[CubePickerEntry, ...]:
    """Convert catalog records into deterministic picker entries."""

    role_map = classifications or {}
    entries = [_entry_from_record(record, role_map) for record in records]
    return tuple(sorted(entries, key=_entry_sort_key))


def build_cube_picker_sections(
    records: list[CubeCatalogRecord],
    *,
    view_mode: CubePickerViewMode = "kind",
    classifications: Mapping[str, CubePickerClassification] | None = None,
    search_text: str = "",
) -> tuple[CubePickerSection, ...]:
    """Return visible picker sections after applying search text."""

    entries = _filter_entries(
        build_cube_picker_entries(records, classifications=classifications),
        search_text,
    )
    if view_mode == "kind":
        return _build_kind_sections(entries)
    if view_mode == "pack":
        return _build_pack_sections(entries)
    if view_mode == "model":
        return _build_model_sections(entries)
    raise ValueError(f"Unknown cube picker view mode: {view_mode}")


def build_cube_picker_model_role_sections(
    records: list[CubeCatalogRecord],
    *,
    classifications: Mapping[str, CubePickerClassification] | None = None,
    search_text: str = "",
) -> tuple[CubePickerModelRoleSection, ...]:
    """Return model-first, role-second picker sections after search filtering."""

    entries = _filter_entries(
        build_cube_picker_entries(records, classifications=classifications),
        search_text,
    )
    return _build_model_role_sections(entries)


def build_cube_search_targets(
    records: list[CubeCatalogRecord],
    *,
    classifications: Mapping[str, CubePickerClassification] | None = None,
) -> tuple[CubeSearchTarget, ...]:
    """Return structured searchable targets for the supplied cube records."""

    entries = build_cube_picker_entries(records, classifications=classifications)
    return tuple(
        target for entry in entries for target in _search_targets_for_entry(entry)
    )


def _build_kind_sections(
    entries: tuple[CubePickerEntry, ...],
) -> tuple[CubePickerSection, ...]:
    """Return role-grouped picker sections."""

    sections: list[CubePickerSection] = []
    for role in _ALL_SECTION_ORDER:
        role_entries = tuple(entry for entry in entries if entry.role == role)
        if role_entries:
            sections.append(
                CubePickerSection(
                    key=role,
                    title=_ROLE_TITLES[role],
                    entries=role_entries,
                    role=role,
                )
            )
    return tuple(sections)


def _build_pack_sections(
    entries: tuple[CubePickerEntry, ...],
) -> tuple[CubePickerSection, ...]:
    """Return source-pack-grouped picker sections."""

    groups: dict[str, CubePickerPackGroup] = {}
    grouped_entries: dict[str, list[CubePickerEntry]] = {}
    for entry in entries:
        group = _pack_group_from_entry(entry)
        groups[group.key] = group
        grouped_entries.setdefault(group.key, []).append(entry)
    return tuple(
        CubePickerSection(
            key=group.key,
            title=group.title,
            entries=tuple(sorted(grouped_entries[group.key], key=_entry_sort_key)),
        )
        for group in sorted(groups.values(), key=_pack_section_sort_key)
    )


def _build_model_sections(
    entries: tuple[CubePickerEntry, ...],
) -> tuple[CubePickerSection, ...]:
    """Return model-support-grouped sections, repeating cubes across claims."""

    grouped_entries: dict[str, list[CubePickerEntry]] = {}
    titles: dict[str, str] = {}
    for entry in entries:
        labels = entry.supported_models or (_UNSPECIFIED_MODEL_TITLE,)
        for label in labels:
            key = _model_section_key(label)
            titles[key] = label
            grouped_entries.setdefault(key, []).append(entry)
    return tuple(
        CubePickerSection(
            key=key,
            title=titles[key],
            entries=tuple(sorted(grouped_entries[key], key=_entry_sort_key)),
        )
        for key in sorted(
            grouped_entries, key=lambda value: _model_section_sort_key(titles[value])
        )
    )


def _build_model_role_sections(
    entries: tuple[CubePickerEntry, ...],
) -> tuple[CubePickerModelRoleSection, ...]:
    """Return model-first sections from each cube's owning model folder."""

    grouped_entries: dict[str, list[CubePickerEntry]] = {}
    titles: dict[str, str] = {}
    for entry in entries:
        title = _owning_model_section_title(entry)
        key = _model_section_key(title)
        titles[key] = title
        grouped_entries.setdefault(key, []).append(entry)
    return tuple(
        CubePickerModelRoleSection(
            key=key,
            title=titles[key],
            role_sections=_build_role_subsections(grouped_entries[key]),
        )
        for key in sorted(
            grouped_entries, key=lambda value: _model_section_sort_key(titles[value])
        )
    )


def _build_role_subsections(
    entries: list[CubePickerEntry],
) -> tuple[CubePickerRoleSection, ...]:
    """Return non-empty role subsections for one model group."""

    sections: list[CubePickerRoleSection] = []
    for role in _ALL_SECTION_ORDER:
        role_entries = tuple(
            sorted(
                (entry for entry in entries if entry.role == role), key=_entry_sort_key
            )
        )
        if role_entries:
            sections.append(
                CubePickerRoleSection(
                    key=role,
                    title=_ROLE_TITLES[role],
                    entries=role_entries,
                )
            )
    return tuple(sections)


def _owning_model_section_title(entry: CubePickerEntry) -> str:
    """Return the model folder that owns a cube picker entry."""

    source_path = entry.source.path if entry.source is not None else ""
    for path, source_owned in ((source_path, True), (entry.cube_id, False)):
        candidate = _model_folder_from_path(path)
        if candidate is None:
            continue
        if entry.supported_models and not _folder_matches_supported_model(
            candidate,
            entry.supported_models,
        ):
            continue
        if source_owned or _path_has_model_folder_depth(path):
            return candidate
    return _UNSPECIFIED_MODEL_TITLE


def _model_folder_from_path(path: str) -> str | None:
    """Return the model folder segment from a catalog path or cube id."""

    parts = tuple(part.strip() for part in path.replace("\\", "/").split("/") if part)
    if len(parts) < 2:
        return None
    if len(parts) == 2:
        return parts[0]
    return parts[-2]


def _path_has_model_folder_depth(path: str) -> bool:
    """Return whether a cube id has enough hierarchy to carry a model folder."""

    parts = tuple(part.strip() for part in path.replace("\\", "/").split("/") if part)
    return len(parts) == 2 or len(parts) >= 4


def _folder_matches_supported_model(
    folder: str, supported_models: tuple[str, ...]
) -> bool:
    """Return whether one path folder matches a supported-model label."""

    normalized_folder = _model_label_key(folder)
    return any(
        (model_key := _model_label_key(model)) == normalized_folder
        or model_key.startswith(normalized_folder)
        or normalized_folder.startswith(model_key)
        for model in supported_models
    )


def _model_label_key(value: str) -> str:
    """Return a loose comparison key for model folder labels."""

    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def classify_cube_document(payload: Mapping[str, object]) -> CubePickerClassification:
    """Classify one loaded cube document from its authored boundary maps."""

    supported_models = _supported_models_from_payload(payload)
    search_terms = _cube_search_terms_from_payload(payload)
    search_targets = _cube_search_targets_from_payload(payload)
    implementation = payload.get("implementation")
    if isinstance(implementation, Mapping):
        input_count = _mapping_count(implementation.get("inputs"))
        output_count = _mapping_count(implementation.get("outputs"))
        return classify_cube_boundaries(
            input_count=input_count,
            output_count=output_count,
            supported_models=supported_models,
            search_terms=search_terms,
            search_targets=search_targets,
        )
    return classify_cube_boundaries(
        input_count=_mapping_count(payload.get("inputs")),
        output_count=_mapping_count(payload.get("outputs")),
        supported_models=supported_models,
        search_terms=search_terms,
        search_targets=search_targets,
    )


def classify_cube_boundaries(
    *,
    input_count: int,
    output_count: int,
    supported_models: tuple[str, ...] = (),
    search_terms: tuple[str, ...] = (),
    search_targets: tuple[CubeSearchTerm, ...] = (),
) -> CubePickerClassification:
    """Classify cube kind from input/output counts for picker grouping."""

    normalized_input_count = max(0, input_count)
    normalized_output_count = max(0, output_count)
    if normalized_input_count == 0 and normalized_output_count > 0:
        role: CubePickerRole = "start"
    elif normalized_input_count > 0 and normalized_output_count > 0:
        role = "middle"
    elif normalized_input_count > 0 and normalized_output_count == 0:
        role = "end"
    else:
        role = "unclassified"
    return CubePickerClassification(
        input_count=normalized_input_count,
        output_count=normalized_output_count,
        role=role,
        supported_models=supported_models,
        search_terms=search_terms,
        search_targets=search_targets,
    )


def _entry_from_record(
    record: CubeCatalogRecord,
    classifications: Mapping[str, CubePickerClassification],
) -> CubePickerEntry:
    """Build one picker entry from one catalog record."""

    classification = classifications.get(record.cube_id)
    if classification is None:
        classification = classify_cube_boundaries(input_count=0, output_count=0)
    presentation = build_cube_tab_presentation(
        alias=record.display_name,
        cube_id=record.cube_id,
        version=record.version,
    )
    return CubePickerEntry(
        cube_id=record.cube_id,
        display_name=record.display_name,
        version=record.version,
        description=record.description,
        secondary_text=presentation.secondary_text,
        icon=record.icon,
        source=record.source,
        role=classification.role,
        input_count=classification.input_count,
        output_count=classification.output_count,
        supported_models=_combined_supported_models(
            record.supported_models,
            classification.supported_models,
        ),
        search_terms=classification.search_terms,
        search_targets=classification.search_targets,
        content_hash=record.content_hash,
        catalog_revision=record.catalog_revision,
    )


def _mapping_count(value: object) -> int:
    """Return the number of entries in a mapping value."""

    return len(value) if isinstance(value, Mapping) else 0


def _filter_entries(
    entries: tuple[CubePickerEntry, ...],
    search_text: str,
) -> tuple[CubePickerEntry, ...]:
    """Apply case-insensitive picker search across display and origin metadata."""

    query = search_text.strip().casefold()
    if not query:
        return entries
    return tuple(entry for entry in entries if query in _search_text(entry))


def _pack_group_from_entry(entry: CubePickerEntry) -> CubePickerPackGroup:
    """Return the source-pack group for one picker entry."""

    source = entry.source
    source_kind = _normalized_source_text(source.kind if source is not None else "")
    repo_ref = _normalized_source_text(source.repo_ref if source is not None else "")
    owner = _normalized_source_text(source.owner if source is not None else "")
    repo = _normalized_source_text(source.repo if source is not None else "")
    namespace = _normalized_source_text(source.namespace if source is not None else "")
    owner_repo = f"{owner}/{repo}" if owner and repo else ""
    local = source_kind == "local" or entry.cube_id.casefold().startswith("local/")
    if repo_ref:
        return CubePickerPackGroup(
            key=repo_ref,
            title=repo_ref,
            local=local,
            unknown=False,
        )
    if owner_repo:
        return CubePickerPackGroup(
            key=owner_repo,
            title=owner_repo,
            local=local,
            unknown=False,
        )
    if namespace:
        return CubePickerPackGroup(
            key=namespace,
            title=namespace,
            local=local,
            unknown=False,
        )
    if source_kind:
        title = (
            app_text("Local cubes")
            if source_kind == "local"
            else app_text("%1 cubes", source_kind.title())
        )
        return CubePickerPackGroup(
            key=source_kind,
            title=title,
            local=local,
            unknown=False,
        )
    return CubePickerPackGroup(
        key="unknown",
        title=app_text("Unknown source"),
        local=False,
        unknown=True,
    )


def _pack_section_sort_key(group: CubePickerPackGroup) -> tuple[int, str]:
    """Return deterministic display order for source-pack sections."""

    if group.unknown:
        bucket = 2
    elif group.local:
        bucket = 0
    else:
        bucket = 1
    return (bucket, group.title.casefold())


def _normalized_source_text(value: str) -> str:
    """Return source metadata text normalized for grouping."""

    return value.strip()


def _supported_models_from_payload(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Return normalized model support claims from cube metadata."""

    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return ()
    value = metadata.get("supported_models")
    if isinstance(value, str):
        raw_items: object = value.split(",")
    else:
        raw_items = value
    if not isinstance(raw_items, list | tuple):
        return ()
    return _normalized_label_tuple(raw_items)


def _combined_supported_models(
    record_models: tuple[str, ...],
    classified_models: tuple[str, ...],
) -> tuple[str, ...]:
    """Merge catalog and loaded-document model claims without duplicates."""

    return _normalized_label_tuple((*record_models, *classified_models))


def _cube_search_terms_from_payload(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Return searchable node and surface terms from a loaded cube document."""

    return tuple(term.text for term in _cube_search_targets_from_payload(payload))


def _cube_search_targets_from_payload(
    payload: Mapping[str, object],
) -> tuple[CubeSearchTerm, ...]:
    """Return typed searchable node and surface terms from a cube document."""

    terms: list[CubeSearchTerm] = []
    implementation = payload.get("implementation")
    if isinstance(implementation, Mapping):
        terms.extend(_implementation_search_terms(implementation))
    surface = payload.get("surface")
    if isinstance(surface, Mapping):
        terms.extend(_surface_search_terms(surface))
    return _normalized_search_terms(tuple(terms))


def _implementation_search_terms(
    implementation: Mapping[str, object],
) -> tuple[CubeSearchTerm, ...]:
    """Return searchable terms from canonical cube implementation metadata."""

    terms: list[CubeSearchTerm] = []
    nodes = implementation.get("nodes")
    if isinstance(nodes, Mapping):
        for node_key, node_data in nodes.items():
            terms.append(_search_term(str(node_key), "node"))
            if isinstance(node_data, Mapping):
                terms.extend(
                    _mapping_string_terms(node_data, ("class_type",), kind="node")
                )
    definitions = implementation.get("definitions")
    if isinstance(definitions, Mapping):
        for definition_key, definition_data in definitions.items():
            terms.append(_search_term(str(definition_key), "definition"))
            if isinstance(definition_data, Mapping):
                terms.extend(
                    _mapping_string_terms(
                        definition_data,
                        (
                            "name",
                            "display_name",
                            "category",
                            "python_module",
                            "description",
                        ),
                        kind="definition",
                    )
                )
    layout = implementation.get("layout")
    if isinstance(layout, Mapping):
        terms.extend(_layout_search_terms(layout))
    return tuple(terms)


def _layout_search_terms(layout: Mapping[str, object]) -> tuple[CubeSearchTerm, ...]:
    """Return searchable terms from authored layout node metadata."""

    terms: list[CubeSearchTerm] = []
    for group_key in ("nodes", "markers"):
        group = layout.get(group_key)
        if not isinstance(group, Mapping):
            continue
        for node_key, node_data in group.items():
            terms.append(_search_term(str(node_key), "node"))
            if isinstance(node_data, Mapping):
                terms.extend(
                    _mapping_string_terms(
                        node_data,
                        ("class_type", "title"),
                        kind="node",
                    )
                )
    return tuple(terms)


def _surface_search_terms(surface: Mapping[str, object]) -> tuple[CubeSearchTerm, ...]:
    """Return searchable terms from authored surface controls."""

    controls = surface.get("controls")
    if not isinstance(controls, list | tuple):
        return ()
    terms: list[CubeSearchTerm] = []
    for control in controls:
        if isinstance(control, Mapping):
            terms.extend(
                _mapping_string_terms(
                    control,
                    ("control_id", "symbol", "input_name", "label", "class_type"),
                    kind="control",
                )
            )
    return tuple(terms)


def _mapping_string_terms(
    source: Mapping[str, object],
    keys: tuple[str, ...],
    *,
    kind: CubeSearchTargetKind,
) -> tuple[CubeSearchTerm, ...]:
    """Return selected mapping values as typed search terms."""

    return tuple(
        _search_term(value, kind)
        for key in keys
        if isinstance((value := source.get(key)), str)
    )


def _search_term(text: str, kind: CubeSearchTargetKind) -> CubeSearchTerm:
    """Return one typed metadata search term."""

    return CubeSearchTerm(text=text, kind=kind)


def _normalized_label_tuple(values: object) -> tuple[str, ...]:
    """Return normalized non-empty string labels in first-seen order."""

    if not isinstance(values, list | tuple):
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        label = value.strip()
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        normalized.append(label)
    return tuple(normalized)


def _normalized_search_terms(
    values: tuple[CubeSearchTerm, ...],
) -> tuple[CubeSearchTerm, ...]:
    """Return normalized typed search terms in first-seen order."""

    normalized: list[CubeSearchTerm] = []
    seen: set[tuple[CubeSearchTargetKind, str]] = set()
    for value in values:
        label = value.text.strip()
        key = (value.kind, label.casefold())
        if not label or key in seen:
            continue
        seen.add(key)
        normalized.append(CubeSearchTerm(text=label, kind=value.kind))
    return tuple(normalized)


def _model_section_key(label: str) -> str:
    """Return a stable key for one supported-model section label."""

    if label == _UNSPECIFIED_MODEL_TITLE:
        return _UNSPECIFIED_MODEL_KEY
    return label.casefold()


def _model_section_sort_key(label: str) -> tuple[int, str]:
    """Sort model groups alphabetically with unspecified claims last."""

    if label == _UNSPECIFIED_MODEL_TITLE:
        return (1, label.casefold())
    return (0, label.casefold())


def _search_text(entry: CubePickerEntry) -> str:
    """Return normalized searchable text for one picker entry."""

    return " ".join(
        target.text.casefold() for target in _search_targets_for_entry(entry)
    )


def _search_targets_for_entry(entry: CubePickerEntry) -> tuple[CubeSearchTarget, ...]:
    """Return deduplicated structured search targets for one picker entry."""

    targets: list[CubeSearchTarget] = []
    _append_target(targets, entry=entry, text=entry.display_name, kind="cube")
    _append_target(targets, entry=entry, text=entry.cube_id, kind="technical")
    _append_target(targets, entry=entry, text=entry.version, kind="technical")
    _append_target(targets, entry=entry, text=entry.description, kind="technical")
    _append_target(targets, entry=entry, text=entry.secondary_text, kind="technical")
    for model in entry.supported_models:
        _append_target(targets, entry=entry, text=model, kind="model")
    _append_target(
        targets,
        entry=entry,
        text=_pack_group_from_entry(entry).title,
        kind="pack",
    )
    if entry.source is not None:
        for source_part in (
            entry.source.repo_ref,
            entry.source.owner,
            entry.source.repo,
            entry.source.branch,
            entry.source.namespace,
            entry.source.path,
        ):
            _append_target(targets, entry=entry, text=source_part, kind="source")
    typed_terms_by_text = {
        term.text.casefold(): term.kind for term in entry.search_targets
    }
    for term in entry.search_targets:
        _append_target(targets, entry=entry, text=term.text, kind=term.kind)
    for raw_term in entry.search_terms:
        _append_target(
            targets,
            entry=entry,
            text=raw_term,
            kind=typed_terms_by_text.get(raw_term.casefold(), "technical"),
        )
    return tuple(targets)


def _append_target(
    targets: list[CubeSearchTarget],
    *,
    entry: CubePickerEntry,
    text: str,
    kind: CubeSearchTargetKind,
) -> None:
    """Append one target when text is non-empty and not already present."""

    label = text.strip()
    key = (kind, label.casefold())
    if not label or any(
        target.kind == key[0] and target.text.casefold() == key[1] for target in targets
    ):
        return
    targets.append(
        CubeSearchTarget(
            text=label,
            kind=kind,
            cube_id=entry.cube_id,
            source_label=entry.display_name,
        )
    )


def _entry_sort_key(entry: CubePickerEntry) -> tuple[str, str]:
    """Sort entries predictably by display name, then canonical identity."""

    return (entry.display_name.casefold(), entry.cube_id.casefold())


__all__ = [
    "CubePickerEntry",
    "CubePickerClassification",
    "CubePickerModelRoleSection",
    "CubePickerPackGroup",
    "CubePickerRole",
    "CubePickerRoleSection",
    "CubePickerSection",
    "CubePickerViewMode",
    "CubeSearchTarget",
    "CubeSearchTargetKind",
    "CubeSearchTerm",
    "classify_cube_boundaries",
    "classify_cube_document",
    "build_cube_search_targets",
    "build_cube_picker_entries",
    "build_cube_picker_model_role_sections",
    "build_cube_picker_sections",
]
