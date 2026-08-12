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

"""Load strict machine-readable architecture policy and current state."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import cast

from .model import (
    ArchitectureDebt,
    ArchitecturePolicy,
    ArchitectureState,
    ArchitectureWaiver,
)


def load_policy(path: Path) -> ArchitecturePolicy:
    """Load one schema-versioned architecture policy."""

    data = _document(path, expected_version=1)
    _exact_keys(data, {"schema_version", "structure", "registries"}, str(path))
    structure = _mapping(data, "structure")
    registries = _mapping(data, "registries")
    _exact_keys(
        structure,
        {"soft_lines", "hard_lines", "source_roots", "excluded_paths"},
        "structure policy",
    )
    _exact_keys(
        registries,
        {"debt", "waivers"},
        "architecture registries",
    )
    return ArchitecturePolicy(
        soft_lines=_positive_int(structure, "soft_lines"),
        hard_lines=_positive_int(structure, "hard_lines"),
        source_roots=tuple(
            Path(value) for value in _strings(structure, "source_roots")
        ),
        excluded_paths=frozenset(_strings(structure, "excluded_paths")),
        debt_registry=Path(_string(registries, "debt")),
        waiver_registry=Path(_string(registries, "waivers")),
    )


def load_state(root: Path, policy: ArchitecturePolicy) -> ArchitectureState:
    """Load all exact current architecture state registries."""

    debt_data = _registry_document(root / policy.debt_registry, "debts")
    waiver_data = _registry_document(root / policy.waiver_registry, "waivers")
    return ArchitectureState(
        debts=tuple(_parse_debt(item) for item in _tables(debt_data, "debts")),
        waivers=tuple(_parse_waiver(item) for item in _tables(waiver_data, "waivers")),
    )


def _parse_debt(data: Mapping[str, object]) -> ArchitectureDebt:
    """Parse one assessed mixed-ownership record."""

    _exact_keys(
        data,
        {
            "id",
            "owner",
            "paths",
            "fingerprint",
            "issue",
            "review_by",
            "responsibilities",
            "next_extraction",
        },
        "architecture debt",
    )
    responsibilities = _strings(data, "responsibilities")
    if len(responsibilities) < 2:
        raise ValueError("architecture debt must name at least two responsibilities")
    return ArchitectureDebt(
        identifier=_string(data, "id"),
        owner=_string(data, "owner"),
        paths=_strings(data, "paths"),
        fingerprint=_string(data, "fingerprint"),
        issue=_string(data, "issue"),
        review_by=_date(data, "review_by"),
        responsibilities=responsibilities,
        next_extraction=_string(data, "next_extraction"),
    )


def _parse_waiver(data: Mapping[str, object]) -> ArchitectureWaiver:
    """Parse one bounded structural or remediation waiver."""

    kind = _string(data, "kind")
    if kind not in {"structural", "remediation"}:
        raise ValueError("architecture waiver kind must be structural or remediation")
    fields = {
        "id",
        "owner",
        "rule",
        "path",
        "kind",
        "justification",
        "issue",
        "review_by",
        "max_lines",
    }
    if kind == "remediation":
        fields |= {"next_limit", "debt"}
    _exact_keys(data, fields, "architecture waiver")
    return ArchitectureWaiver(
        identifier=_string(data, "id"),
        owner=_string(data, "owner"),
        rule=_string(data, "rule"),
        path=_string(data, "path"),
        kind=kind,
        justification=_string(data, "justification"),
        issue=_string(data, "issue"),
        review_by=_date(data, "review_by"),
        max_lines=_positive_int(data, "max_lines"),
        next_limit=(
            _positive_int(data, "next_limit") if kind == "remediation" else None
        ),
        debt=_string(data, "debt") if kind == "remediation" else None,
    )


def _document(path: Path, *, expected_version: int) -> Mapping[str, object]:
    """Read one TOML document and validate its schema envelope."""

    data = cast(Mapping[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
    if data.get("schema_version") != expected_version:
        raise ValueError(f"{path} must declare schema_version = {expected_version}")
    return data


def _registry_document(path: Path, collection: str) -> Mapping[str, object]:
    """Read one strict registry envelope containing current state only."""

    data = _document(path, expected_version=1)
    _exact_keys(data, {"schema_version", collection}, str(path))
    return data


def _exact_keys(
    data: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    """Reject missing fields and history-shaped surplus fields."""

    missing = expected - set(data)
    unknown = set(data) - expected
    if missing or unknown:
        raise ValueError(
            f"{label} fields differ: missing={sorted(missing)}, "
            f"unsupported={sorted(unknown)}"
        )


def _mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    """Return one required TOML table."""

    value = data.get(key)
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be a table")
    return cast(Mapping[str, object], value)


def _tables(data: Mapping[str, object], key: str) -> tuple[Mapping[str, object], ...]:
    """Return one optional array of TOML tables."""

    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{key} must be an array of tables")
    return tuple(cast(list[Mapping[str, object]], value))


def _string(data: Mapping[str, object], key: str) -> str:
    """Return one required nonempty string."""

    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a nonempty string")
    return value


def _strings(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    """Return one required nonempty array of unique strings."""

    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{key} must be a nonempty string array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{key} must contain nonempty strings")
    strings = tuple(cast(list[str], value))
    if len(strings) != len(set(strings)):
        raise ValueError(f"{key} must not contain duplicates")
    return strings


def _positive_int(data: Mapping[str, object], key: str) -> int:
    """Return one required positive integer."""

    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _date(data: Mapping[str, object], key: str) -> date:
    """Return one required TOML date."""

    value = data.get(key)
    if not isinstance(value, date):
        raise TypeError(f"{key} must be an ISO date")
    return value
