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

"""Load wildcard catalog metadata from approved custom-node data directories."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.domain.prompt import PromptWildcardCsvSource, PromptWildcardTextSource
from substitute.shared.logging.logger import get_logger, log_debug, log_warning
from substitute.shared.util.path_safety import ensure_within_root

_LOGGER = get_logger("infrastructure.persistence.file_prompt_wildcard_catalog_gateway")
_PLUGIN_DIRECTORY_NAME = "comfyui-csvwildcards"
_DATA_DIRECTORY_NAME = "data"
_SIMPLE_WILDCARD_FORM = "simple"
_CSV_WILDCARD_FORM = "csv"
_CATALOG_CACHE_REVISION = 0
DEFAULT_COMFY_CUSTOM_NODES = Path.cwd() / "comfyui" / "custom_nodes"
DEFAULT_USER_WILDCARDS_ROOT = Path.cwd() / "user" / "wildcards"


@dataclass(frozen=True, slots=True)
class _WildcardCatalog:
    """Cache normalized wildcard identifiers and CSV column metadata."""

    simple_identifiers: frozenset[str]
    csv_columns_by_identifier: dict[str, tuple[str, ...]]
    csv_column_lookup: dict[str, dict[str, str]]


class FilePromptWildcardCatalogGateway(PromptWildcardCatalogGateway):
    """Resolve prompt wildcard metadata and values from safe filesystem catalog roots."""

    def __init__(
        self,
        *,
        user_wildcards_root: Path = DEFAULT_USER_WILDCARDS_ROOT,
        comfy_custom_nodes_root: Path | None = DEFAULT_COMFY_CUSTOM_NODES,
    ) -> None:
        """Store the approved catalog roots used for wildcard metadata scans."""

        self._user_wildcards_root = user_wildcards_root
        self._comfy_custom_nodes_root = comfy_custom_nodes_root

    @property
    def cache_revision(self) -> int:
        """Return the process-wide wildcard catalog cache revision."""

        return _CATALOG_CACHE_REVISION

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return catalog resolution state aligned with the supplied reference order."""

        if not references:
            return ()

        catalog = _load_catalog(
            str(self._user_wildcards_root),
            _optional_path_key(self._comfy_custom_nodes_root),
        )
        resolutions: list[PromptWildcardResolution] = []
        for reference in references:
            if reference.wildcard_form == _SIMPLE_WILDCARD_FORM:
                normalized_identifier = _normalize_lookup_identifier(
                    reference.identifier
                )
                resolutions.append(
                    PromptWildcardResolution(
                        identifier=reference.identifier,
                        wildcard_form=reference.wildcard_form,
                        csv_column=reference.csv_column,
                        exists=normalized_identifier in catalog.simple_identifiers,
                    )
                )
                continue

            if reference.wildcard_form == _CSV_WILDCARD_FORM:
                normalized_identifier = _normalize_lookup_identifier(
                    reference.identifier
                )
                normalized_column = _normalize_lookup_column(reference.csv_column)
                available_columns = catalog.csv_columns_by_identifier.get(
                    normalized_identifier,
                    (),
                )
                matched_csv_column = None
                exists = False
                if normalized_column is not None:
                    matched_csv_column = catalog.csv_column_lookup.get(
                        normalized_identifier,
                        {},
                    ).get(normalized_column)
                    exists = matched_csv_column is not None
                resolutions.append(
                    PromptWildcardResolution(
                        identifier=reference.identifier,
                        wildcard_form=reference.wildcard_form,
                        csv_column=reference.csv_column,
                        exists=exists,
                        matched_csv_column=matched_csv_column,
                        available_csv_columns=available_columns,
                    )
                )
                continue

            resolutions.append(
                PromptWildcardResolution(
                    identifier=reference.identifier,
                    wildcard_form=reference.wildcard_form,
                    csv_column=reference.csv_column,
                    exists=False,
                )
            )
        return tuple(resolutions)

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return wildcard identifier suggestions from enabled catalog files."""

        if limit <= 0:
            return ()
        catalog = _load_catalog(
            str(self._user_wildcards_root),
            _optional_path_key(self._comfy_custom_nodes_root),
        )
        return _search_catalog_wildcards(catalog, prefix=prefix, limit=limit)

    def load_text_source(self, identifier: str) -> PromptWildcardTextSource | None:
        """Load simple wildcard line candidates from the first matching approved root."""

        source_path = self._find_source_file(identifier, suffix=".txt")
        if source_path is None:
            return None
        try:
            with source_path.open("r", encoding="utf-8") as handle:
                lines = tuple(line.strip() for line in handle if line.strip())
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to read wildcard text source.",
                identifier=identifier,
                file_name=source_path.name,
                error=repr(error),
            )
            return None
        return PromptWildcardTextSource(source_id=str(source_path), lines=lines)

    def load_csv_source(self, identifier: str) -> PromptWildcardCsvSource | None:
        """Load CSV wildcard row candidates from the first matching approved root."""

        source_path = self._find_source_file(identifier, suffix=".csv")
        if source_path is None:
            return None
        try:
            with source_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                headers = next(reader, None)
                if not headers:
                    return PromptWildcardCsvSource(
                        source_id=str(source_path),
                        rows=(),
                    )
                normalized_headers = [header.strip().lower() for header in headers]
                rows = tuple(
                    {
                        header: value.strip()
                        for header, value in zip(normalized_headers, row, strict=False)
                    }
                    for row in reader
                )
        except (csv.Error, OSError, UnicodeDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to read wildcard CSV source.",
                identifier=identifier,
                file_name=source_path.name,
                error=repr(error),
            )
            return None
        return PromptWildcardCsvSource(source_id=str(source_path), rows=rows)

    def _find_source_file(self, identifier: str, *, suffix: str) -> Path | None:
        """Return the first existing source file for one wildcard identifier."""

        normalized_identifier = _normalize_catalog_identifier(Path(identifier))
        if normalized_identifier is None:
            return None

        for data_root in self._source_data_roots():
            candidate = data_root / Path(*normalized_identifier.split("/"))
            source_path = candidate.with_suffix(suffix)
            try:
                safe_source_path = ensure_within_root(
                    source_path,
                    root_path=data_root,
                    subject="prompt wildcard source file",
                )
            except ValueError:
                log_warning(
                    _LOGGER,
                    "Skipping wildcard source outside approved data root.",
                    identifier=identifier,
                    suffix=suffix,
                )
                continue
            if safe_source_path.is_file():
                return safe_source_path
        return None

    def _source_data_roots(self) -> tuple[Path, ...]:
        """Return existing source data roots in value-resolution priority order."""

        roots: list[Path] = []
        for root in (
            self._user_wildcards_root,
            _resolve_wildcard_data_root(
                custom_nodes_root=self._comfy_custom_nodes_root,
                root_label="comfy",
            ),
        ):
            if root is not None and root.exists() and root.is_dir():
                roots.append(root)
        return tuple(roots)


@lru_cache(maxsize=None)
def _load_catalog(
    user_wildcards_root: str,
    comfy_custom_nodes_root: str,
) -> _WildcardCatalog:
    """Load and cache wildcard metadata for the current process lifetime."""

    simple_identifiers: set[str] = set()
    csv_columns_by_identifier: dict[str, list[str]] = {}
    csv_column_lookup: dict[str, dict[str, str]] = {}

    _merge_direct_catalog_entries(
        simple_identifiers=simple_identifiers,
        csv_columns_by_identifier=csv_columns_by_identifier,
        csv_column_lookup=csv_column_lookup,
        root_label="user",
        data_root=Path(user_wildcards_root),
    )

    for root_label, custom_nodes_root in _custom_node_roots(comfy_custom_nodes_root):
        if not custom_nodes_root.exists():
            log_debug(
                _LOGGER,
                "Skipping missing wildcard custom-nodes root.",
                root_label=root_label,
            )
            continue
        if not custom_nodes_root.is_dir():
            log_debug(
                _LOGGER,
                "Skipping wildcard custom-nodes root because it is not a directory.",
                root_label=root_label,
            )
            continue

        _merge_catalog_entries(
            simple_identifiers=simple_identifiers,
            csv_columns_by_identifier=csv_columns_by_identifier,
            csv_column_lookup=csv_column_lookup,
            root_label=root_label,
            custom_nodes_root=custom_nodes_root,
        )

    return _WildcardCatalog(
        simple_identifiers=frozenset(simple_identifiers),
        csv_columns_by_identifier={
            identifier: tuple(columns)
            for identifier, columns in csv_columns_by_identifier.items()
        },
        csv_column_lookup=csv_column_lookup,
    )


def _merge_catalog_entries(
    *,
    simple_identifiers: set[str],
    csv_columns_by_identifier: dict[str, list[str]],
    csv_column_lookup: dict[str, dict[str, str]],
    root_label: str,
    custom_nodes_root: Path,
) -> None:
    """Merge one approved custom-nodes root into the in-memory wildcard catalog."""

    data_root = _resolve_wildcard_data_root(
        custom_nodes_root=custom_nodes_root,
        root_label=root_label,
    )
    if data_root is None:
        return

    _merge_direct_catalog_entries(
        simple_identifiers=simple_identifiers,
        csv_columns_by_identifier=csv_columns_by_identifier,
        csv_column_lookup=csv_column_lookup,
        root_label=root_label,
        data_root=data_root,
    )


def _merge_direct_catalog_entries(
    *,
    simple_identifiers: set[str],
    csv_columns_by_identifier: dict[str, list[str]],
    csv_column_lookup: dict[str, dict[str, str]],
    root_label: str,
    data_root: Path,
) -> None:
    """Merge one approved wildcard data root into the in-memory catalog."""

    if not data_root.exists():
        log_debug(
            _LOGGER,
            "Skipping missing wildcard data root.",
            root_label=root_label,
        )
        return
    if not data_root.is_dir():
        log_debug(
            _LOGGER,
            "Skipping wildcard data root because it is not a directory.",
            root_label=root_label,
        )
        return

    for candidate_path in data_root.rglob("*"):
        if not candidate_path.is_file():
            continue
        try:
            safe_candidate_path = ensure_within_root(
                candidate_path,
                root_path=data_root,
                subject="prompt wildcard catalog file",
            )
        except ValueError:
            log_warning(
                _LOGGER,
                "Skipping wildcard catalog file outside approved data root.",
                root_label=root_label,
                file_name=candidate_path.name,
            )
            continue

        suffix = safe_candidate_path.suffix.lower()
        if suffix not in {".txt", ".csv"}:
            continue

        relative_path = safe_candidate_path.relative_to(data_root)
        normalized_identifier = _normalize_catalog_identifier(relative_path)
        if normalized_identifier is None:
            log_debug(
                _LOGGER,
                "Skipping wildcard catalog file with unsupported identifier path.",
                root_label=root_label,
                file_name=safe_candidate_path.name,
            )
            continue

        if suffix == ".txt":
            simple_identifiers.add(normalized_identifier)
            continue

        columns = _read_csv_columns(safe_candidate_path, root_label=root_label)
        if not columns:
            continue

        existing_columns = csv_columns_by_identifier.setdefault(
            normalized_identifier, []
        )
        existing_lookup = csv_column_lookup.setdefault(normalized_identifier, {})
        for column_name in columns:
            normalized_column = _normalize_lookup_column(column_name)
            if normalized_column is None or normalized_column in existing_lookup:
                continue
            existing_lookup[normalized_column] = column_name
            existing_columns.append(column_name)


def _search_catalog_wildcards(
    catalog: _WildcardCatalog,
    *,
    prefix: str,
    limit: int,
) -> tuple[PromptAutocompleteSuggestion, ...]:
    """Return ranked wildcard completion rows from loaded catalog metadata."""

    normalized_prefix = prefix.casefold()
    csv_only = normalized_prefix.startswith("csv:")
    normalized_csv_prefix = normalized_prefix.removeprefix("csv:")
    ranked: list[tuple[int, str, PromptAutocompleteSuggestion]] = []

    if not csv_only:
        for identifier in sorted(catalog.simple_identifiers):
            match_score = _wildcard_match_score(
                identifier=identifier,
                tag=identifier,
                prefix=normalized_prefix,
            )
            if match_score is None:
                continue
            ranked.append(
                (
                    match_score,
                    identifier,
                    PromptAutocompleteSuggestion(
                        tag=identifier,
                        source_label="TXT wildcard",
                        source_kind="wildcard",
                    ),
                )
            )

    for identifier, columns in sorted(catalog.csv_columns_by_identifier.items()):
        for column in columns:
            tag = f"csv:{identifier}:{column}"
            match_score = _wildcard_match_score(
                identifier=identifier,
                tag=tag,
                prefix=normalized_csv_prefix if csv_only else normalized_prefix,
            )
            if match_score is None:
                continue
            ranked.append(
                (
                    match_score + 10,
                    tag.casefold(),
                    PromptAutocompleteSuggestion(
                        tag=tag,
                        source_label="CSV wildcard",
                        source_kind="wildcard",
                    ),
                )
            )

    return tuple(
        suggestion
        for _, _, suggestion in sorted(ranked, key=lambda item: (item[0], item[1]))[
            :limit
        ]
    )


def _wildcard_match_score(
    *,
    identifier: str,
    tag: str,
    prefix: str,
) -> int | None:
    """Return a stable ranking score for one wildcard autocomplete candidate."""

    if not prefix:
        return 100
    normalized_identifier = identifier.casefold()
    normalized_tag = tag.casefold()
    if normalized_identifier.startswith(prefix):
        return 0
    if normalized_tag.startswith(prefix):
        return 20
    if prefix in normalized_identifier:
        return 200
    if prefix in normalized_tag:
        return 220
    return None


def _resolve_wildcard_data_root(
    *,
    custom_nodes_root: Path | None,
    root_label: str,
) -> Path | None:
    """Return the validated wildcard data root for one approved custom-nodes root."""

    if custom_nodes_root is None:
        return None
    try:
        plugin_root = ensure_within_root(
            custom_nodes_root / _PLUGIN_DIRECTORY_NAME,
            root_path=custom_nodes_root,
            subject="prompt wildcard plugin root",
        )
        data_root = ensure_within_root(
            plugin_root / _DATA_DIRECTORY_NAME,
            root_path=plugin_root,
            subject="prompt wildcard data root",
        )
    except ValueError:
        log_warning(
            _LOGGER,
            "Skipping wildcard plugin root that resolves outside the approved custom-nodes root.",
            root_label=root_label,
        )
        return None

    if not data_root.exists():
        log_debug(
            _LOGGER,
            "Skipping missing wildcard data root.",
            root_label=root_label,
        )
        return None
    if not data_root.is_dir():
        log_debug(
            _LOGGER,
            "Skipping wildcard data root because it is not a directory.",
            root_label=root_label,
        )
        return None
    return data_root


def _normalize_catalog_identifier(relative_path: Path) -> str | None:
    """Return the normalized wildcard identifier for one relative catalog file path."""

    if not relative_path.stem:
        return None
    identifier_path = relative_path.with_suffix("")
    normalized_identifier = PurePosixPath(identifier_path.as_posix())
    if normalized_identifier.is_absolute():
        return None
    if any(part in {"", ".", ".."} for part in normalized_identifier.parts):
        return None
    return str(normalized_identifier).lower()


def _normalize_lookup_identifier(identifier: str) -> str:
    """Normalize one wildcard identifier for case-insensitive lookup."""

    return str(PurePosixPath(identifier)).lower()


def _normalize_lookup_column(column_name: str | None) -> str | None:
    """Normalize one CSV column lookup key for case-insensitive matching."""

    if column_name is None:
        return None
    normalized_column = column_name.strip().lower()
    if not normalized_column:
        return None
    return normalized_column


def _read_csv_columns(
    csv_path: Path,
    *,
    root_label: str,
) -> tuple[str, ...]:
    """Read CSV headers from one wildcard catalog file and return cleaned display names."""

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            raw_headers = next(reader, None)
    except (csv.Error, OSError, UnicodeDecodeError):
        log_warning(
            _LOGGER,
            "Skipping unreadable wildcard CSV catalog file.",
            root_label=root_label,
            file_name=csv_path.name,
        )
        return ()

    if not raw_headers:
        return ()

    columns: list[str] = []
    seen_columns: set[str] = set()
    for raw_header in raw_headers:
        if not isinstance(raw_header, str):
            continue
        display_name = raw_header.strip()
        normalized_column = _normalize_lookup_column(display_name)
        if normalized_column is None or normalized_column in seen_columns:
            continue
        seen_columns.add(normalized_column)
        columns.append(display_name)
    return tuple(columns)


def clear_prompt_wildcard_catalog_caches() -> None:
    """Clear process-wide wildcard metadata caches."""

    global _CATALOG_CACHE_REVISION
    _CATALOG_CACHE_REVISION += 1
    _load_catalog.cache_clear()


def _optional_path_key(path: Path | None) -> str:
    """Return a stable catalog-cache key for an optional filesystem root."""

    return "" if path is None else str(path)


def _custom_node_roots(comfy_custom_nodes_root: str) -> tuple[tuple[str, Path], ...]:
    """Return local Comfy custom-node roots that may contribute wildcard data."""

    if not comfy_custom_nodes_root:
        return ()
    return (("comfy", Path(comfy_custom_nodes_root)),)


__all__ = [
    "FilePromptWildcardCatalogGateway",
    "clear_prompt_wildcard_catalog_caches",
]
