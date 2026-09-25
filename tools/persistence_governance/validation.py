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

"""Enforce the authoritative persisted-format catalog and migration graph."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from pathlib import Path
import tomllib

from tools.architecture_governance.model import Diagnostic

_CATALOG_PATH = Path("governance/persistence/catalog.toml")
_DISCOVERY_ROOTS = ("substitute", "launcher", "sugarsubstitute_shared")
_CLASSIFICATIONS = frozenset(
    {
        "authoritative_state",
        "authored_document",
        "recovery_journal",
        "release_contract",
        "cross_version_protocol",
        "diagnostic",
        "persistent_cache",
    }
)
_PRESERVATION_POLICIES = frozenset(
    {"must_preserve", "preserve_for_diagnosis", "replaceable", "ephemeral"}
)
_COMPATIBILITY_POLICIES = frozenset(
    {"migrate", "compatible_reader", "reject", "discard"}
)
_CLASSIFICATION_DEFAULTS = {
    "authoritative_state": ("must_preserve", "compatible_reader"),
    "authored_document": ("must_preserve", "compatible_reader"),
    "recovery_journal": ("preserve_for_diagnosis", "reject"),
    "release_contract": ("replaceable", "reject"),
    "cross_version_protocol": ("ephemeral", "reject"),
    "diagnostic": ("preserve_for_diagnosis", "compatible_reader"),
    "persistent_cache": ("replaceable", "discard"),
}
_NON_CURRENT_MARKERS = (
    "LEGACY",
    "COMPATIBILITY",
    "SUPPORTED",
    "WRITABLE",
    "SURFACE",
    "PARENT",
    "MILESTONE",
)


@dataclass(frozen=True, slots=True)
class _FormatRecord:
    """Describe one reviewed persisted or cross-version format owner."""

    identifier: str
    owner: str
    constant: str
    current_version: str
    accepted_versions: tuple[str, ...]
    classification: str
    preservation: str
    compatibility: str
    migrations: tuple[str, ...]


def validate_persistence_governance(root: Path) -> list[Diagnostic]:
    """Return completeness, version, review, and migration diagnostics."""

    try:
        records, reviewed_sources_sha256 = _load_catalog(root / _CATALOG_PATH)
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        return [Diagnostic("PERSIST001", _CATALOG_PATH.as_posix(), str(error))]
    diagnostics = _validate_records(root, records)
    diagnostics.extend(
        _validate_reviewed_sources(root, records, reviewed_sources_sha256)
    )
    diagnostics.extend(_validate_discovery_completeness(root, records))
    diagnostics.extend(_validate_guidance(root))
    return diagnostics


def _load_catalog(path: Path) -> tuple[tuple[_FormatRecord, ...], str]:
    """Load the catalog without importing runtime persistence owners."""

    with path.open("rb") as source:
        payload = tomllib.load(source)
    if payload.get("schema_version") != 1:
        raise ValueError("persistence catalog requires schema_version = 1")
    reviewed_sources_sha256 = payload.get("reviewed_sources_sha256")
    if not isinstance(reviewed_sources_sha256, str) or not reviewed_sources_sha256:
        raise ValueError("persistence catalog requires reviewed_sources_sha256")
    values = payload.get("formats")
    if not isinstance(values, list) or not values:
        raise ValueError("persistence catalog must declare at least one format")
    records: list[_FormatRecord] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("each persistence format must be a table")
        classification = _text(value, "classification")
        current_version = _version(value, "current_version")
        default_preservation, default_compatibility = _CLASSIFICATION_DEFAULTS.get(
            classification, ("", "")
        )
        records.append(
            _FormatRecord(
                identifier=_text(value, "id"),
                owner=_text(value, "owner"),
                constant=_text(value, "constant"),
                current_version=current_version,
                accepted_versions=_versions(
                    value,
                    "accepted_versions",
                    default=(current_version,),
                ),
                classification=classification,
                preservation=_optional_text(
                    value, "preservation", default_preservation
                ),
                compatibility=_optional_text(
                    value, "compatibility", default_compatibility
                ),
                migrations=_versions(value, "migrations", default=()),
            )
        )
    return tuple(records), reviewed_sources_sha256


def _validate_records(
    root: Path, records: tuple[_FormatRecord, ...]
) -> list[Diagnostic]:
    """Validate identities, source constants, fingerprints, and migration coverage."""

    diagnostics: list[Diagnostic] = []
    identifiers: set[str] = set()
    owners: set[tuple[str, str]] = set()
    for record in records:
        location = _CATALOG_PATH.as_posix()
        if record.identifier in identifiers:
            diagnostics.append(
                Diagnostic(
                    "PERSIST002", location, f"duplicate format id {record.identifier}"
                )
            )
        identifiers.add(record.identifier)
        owner_key = (record.owner, record.constant)
        if owner_key in owners:
            diagnostics.append(
                Diagnostic(
                    "PERSIST003",
                    location,
                    f"duplicate owner constant {record.owner}:{record.constant}",
                )
            )
        owners.add(owner_key)
        if record.classification not in _CLASSIFICATIONS:
            diagnostics.append(
                Diagnostic(
                    "PERSIST004",
                    location,
                    f"format {record.identifier} has invalid classification",
                )
            )
        if record.preservation not in _PRESERVATION_POLICIES:
            diagnostics.append(
                Diagnostic(
                    "PERSIST005",
                    location,
                    f"format {record.identifier} has invalid preservation policy",
                )
            )
        if record.compatibility not in _COMPATIBILITY_POLICIES:
            diagnostics.append(
                Diagnostic(
                    "PERSIST006",
                    location,
                    f"format {record.identifier} has invalid compatibility policy",
                )
            )
        owner_path = root / record.owner
        if not owner_path.is_file():
            diagnostics.append(
                Diagnostic(
                    "PERSIST007",
                    location,
                    f"format {record.identifier} owner does not exist: {record.owner}",
                )
            )
            continue
        constants = _literal_version_constants(owner_path)
        actual = constants.get(record.constant)
        if actual != record.current_version:
            diagnostics.append(
                Diagnostic(
                    "PERSIST008",
                    record.owner,
                    f"format {record.identifier} declares version {record.current_version}, but {record.constant} is {actual!r}",
                )
            )
        if record.current_version not in record.accepted_versions:
            diagnostics.append(
                Diagnostic(
                    "PERSIST010",
                    location,
                    f"format {record.identifier} must accept its current version",
                )
            )
        diagnostics.extend(_validate_migrations(record))
        if record.preservation == "must_preserve" and record.compatibility == "discard":
            diagnostics.append(
                Diagnostic(
                    "PERSIST011",
                    location,
                    f"must-preserve format {record.identifier} cannot use {record.compatibility} compatibility",
                )
            )
    return diagnostics


def _validate_reviewed_sources(
    root: Path,
    records: tuple[_FormatRecord, ...],
    expected: str,
) -> list[Diagnostic]:
    """Require one stable review fingerprint over every registered source owner."""

    digest = hashlib.sha256()
    for owner in sorted({record.owner for record in records}):
        path = root / owner
        if not path.is_file():
            continue
        digest.update(owner.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    if digest.hexdigest() == expected:
        return []
    return [
        Diagnostic(
            "PERSIST009",
            _CATALOG_PATH.as_posix(),
            "a registered persistence owner changed; review compatibility, advance "
            "schemas when semantics changed, add migrations, and refresh "
            "reviewed_sources_sha256",
        )
    ]


def _validate_migrations(record: _FormatRecord) -> list[Diagnostic]:
    """Require an unbroken forward path for every migratable accepted version."""

    if record.compatibility != "migrate":
        if record.migrations:
            return [
                Diagnostic(
                    "PERSIST012",
                    _CATALOG_PATH.as_posix(),
                    f"non-migrating format {record.identifier} declares migration edges",
                )
            ]
        return []
    edges: dict[str, str] = {}
    for edge in record.migrations:
        parts = edge.split("->", maxsplit=1)
        if len(parts) != 2 or not all(parts):
            return [
                Diagnostic(
                    "PERSIST013",
                    _CATALOG_PATH.as_posix(),
                    f"format {record.identifier} has invalid migration edge {edge!r}",
                )
            ]
        source, destination = parts
        if source in edges:
            return [
                Diagnostic(
                    "PERSIST014",
                    _CATALOG_PATH.as_posix(),
                    f"format {record.identifier} has multiple migrations from {source}",
                )
            ]
        edges[source] = destination
    diagnostics: list[Diagnostic] = []
    for accepted in record.accepted_versions:
        visited: set[str] = set()
        version = accepted
        while version != record.current_version and version not in visited:
            visited.add(version)
            version = edges.get(version, "")
        if version != record.current_version:
            diagnostics.append(
                Diagnostic(
                    "PERSIST015",
                    _CATALOG_PATH.as_posix(),
                    f"format {record.identifier} has no migration path from {accepted} to {record.current_version}",
                )
            )
    return diagnostics


def _validate_discovery_completeness(
    root: Path, records: tuple[_FormatRecord, ...]
) -> list[Diagnostic]:
    """Reject newly introduced schema owners until they receive a catalog policy."""

    registered = {(record.owner, record.constant) for record in records}
    diagnostics: list[Diagnostic] = []
    for base in _DISCOVERY_ROOTS:
        source_root = root / base
        if not source_root.is_dir():
            continue
        for path in sorted(source_root.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            for constant in _literal_version_constants(path):
                if not _is_discovered_current_constant(constant):
                    continue
                if (relative, constant) not in registered:
                    diagnostics.append(
                        Diagnostic(
                            "PERSIST016",
                            relative,
                            f"persisted schema constant {constant} is not registered in {_CATALOG_PATH.as_posix()}",
                        )
                    )
    return diagnostics


def _literal_version_constants(path: Path) -> dict[str, str]:
    """Return literal module-level schema and protocol constants."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants: dict[str, str] = {}
    for node in tree.body:
        targets: tuple[ast.expr, ...]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
            value = node.value
        else:
            continue
        if not isinstance(value, ast.Constant) or type(value.value) not in {int, str}:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                constants[target.id] = str(value.value)
    return constants


def _is_discovered_current_constant(name: str) -> bool:
    """Select current format versions while excluding compatibility aliases."""

    if any(marker in name for marker in _NON_CURRENT_MARKERS):
        return False
    return name.endswith("SCHEMA_VERSION") or name == "CURRENT_SPLASH_PROTOCOL_VERSION"


def _validate_guidance(root: Path) -> list[Diagnostic]:
    """Require contributor guidance that keeps schema governance current."""

    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    fragments = (
        "## Persistence Schema Governance",
        "Register every persisted format",
        "advance the schema version",
    )
    missing = next((fragment for fragment in fragments if fragment not in text), None)
    return (
        []
        if missing is None
        else [
            Diagnostic(
                "PERSIST017",
                "AGENTS.md",
                f"persistence governance guidance is incomplete; missing {missing!r}",
            )
        ]
    )


def _text(value: dict[str, object], key: str) -> str:
    """Read one required nonempty catalog string."""

    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"format field {key} must be nonempty text")
    return item


def _version(value: dict[str, object], key: str) -> str:
    """Normalize one scalar version to its catalog string form."""

    item = value.get(key)
    if type(item) not in {int, str}:
        raise ValueError(f"format field {key} must be a string or integer")
    return str(item)


def _optional_text(value: dict[str, object], key: str, default: str) -> str:
    """Read optional catalog text using the classification-owned policy default."""

    item = value.get(key, default)
    if not isinstance(item, str) or not item:
        raise ValueError(f"format field {key} must be nonempty text")
    return item


def _versions(
    value: dict[str, object],
    key: str,
    *,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    """Normalize a unique ordered catalog version or edge sequence."""

    items = value.get(key, list(default))
    if not isinstance(items, list):
        raise ValueError(f"format field {key} must be a list")
    result = tuple(str(item) for item in items if type(item) in {int, str})
    if len(result) != len(items) or len(set(result)) != len(result):
        raise ValueError(f"format field {key} must contain unique strings or integers")
    return result


__all__ = ["validate_persistence_governance"]
