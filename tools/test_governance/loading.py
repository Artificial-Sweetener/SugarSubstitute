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

"""Load strict test policy, debt, and waiver state."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import cast

from .model import TestDebt, TestPolicy, TestState, TestWaiver


def load_test_policy(path: Path) -> TestPolicy:
    """Load one schema-versioned test-governance policy."""

    data = _document(path, expected_version=1)
    _exact_keys(data, {"schema_version", "scope", "discovery", "registries"}, str(path))
    scope = _mapping(data, "scope")
    discovery = _mapping(data, "discovery")
    registries = _mapping(data, "registries")
    _exact_keys(
        scope,
        {
            "test_root",
            "semantic_support_roots",
            "root_source_extensions",
            "allowed_root_source_paths",
        },
        "test scope",
    )
    _exact_keys(
        discovery,
        {
            "serial_policy",
            "wait_calls",
            "wall_clock_calls",
            "xdist_environment_name",
            "repository_scratch_name",
        },
        "test discovery",
    )
    _exact_keys(registries, {"debt", "waivers"}, "test registries")
    return TestPolicy(
        test_root=Path(_string(scope, "test_root")),
        semantic_support_roots=tuple(
            Path(value) for value in _strings(scope, "semantic_support_roots")
        ),
        root_source_extensions=frozenset(_strings(scope, "root_source_extensions")),
        allowed_root_source_paths=frozenset(
            _strings(scope, "allowed_root_source_paths")
        ),
        serial_policy=Path(_string(discovery, "serial_policy")),
        wait_calls=frozenset(_strings(discovery, "wait_calls")),
        wall_clock_calls=frozenset(_strings(discovery, "wall_clock_calls")),
        xdist_environment_name=_string(discovery, "xdist_environment_name"),
        repository_scratch_name=_string(discovery, "repository_scratch_name"),
        debt_registry=Path(_string(registries, "debt")),
        waiver_registry=Path(_string(registries, "waivers")),
    )


def load_test_state(root: Path, policy: TestPolicy) -> TestState:
    """Load exact current test debt and waiver registries."""

    debt_data = _registry_document(root / policy.debt_registry, "debts")
    waiver_data = _registry_document(root / policy.waiver_registry, "waivers")
    return TestState(
        debts=tuple(_parse_debt(item) for item in _tables(debt_data, "debts")),
        waivers=tuple(_parse_waiver(item) for item in _tables(waiver_data, "waivers")),
    )


def _parse_debt(data: Mapping[str, object]) -> TestDebt:
    """Parse one exact test-debt record."""

    _exact_keys(
        data,
        {
            "id",
            "owner",
            "rule",
            "candidates",
            "paths",
            "fingerprint",
            "issue",
            "review_by",
            "problem",
            "remediation",
        },
        "test debt",
    )
    return TestDebt(
        identifier=_string(data, "id"),
        owner=_string(data, "owner"),
        rule=_string(data, "rule"),
        candidates=_strings(data, "candidates"),
        paths=_strings(data, "paths"),
        fingerprint=_string(data, "fingerprint"),
        issue=_string(data, "issue"),
        review_by=_date(data, "review_by"),
        problem=_string(data, "problem"),
        remediation=_string(data, "remediation"),
    )


def _parse_waiver(data: Mapping[str, object]) -> TestWaiver:
    """Parse one exact reviewed test waiver."""

    kind = _string(data, "kind")
    if kind not in {"classification", "remediation"}:
        raise ValueError("test waiver kind must be classification or remediation")
    fields = {
        "id",
        "owner",
        "kind",
        "disposition",
        "rule",
        "candidates",
        "paths",
        "fingerprint",
        "rationale",
        "issue",
        "review_by",
    }
    if kind == "remediation":
        fields.add("debt")
    _exact_keys(data, fields, "test waiver")
    return TestWaiver(
        identifier=_string(data, "id"),
        owner=_string(data, "owner"),
        kind=kind,
        disposition=_string(data, "disposition"),
        rule=_string(data, "rule"),
        candidates=_strings(data, "candidates"),
        paths=_strings(data, "paths"),
        fingerprint=_string(data, "fingerprint"),
        rationale=_string(data, "rationale"),
        issue=_string(data, "issue"),
        review_by=_date(data, "review_by"),
        debt=_string(data, "debt") if kind == "remediation" else None,
    )


def _document(path: Path, *, expected_version: int) -> Mapping[str, object]:
    """Read one TOML document and validate its schema version."""

    data = cast(Mapping[str, object], tomllib.loads(path.read_text(encoding="utf-8")))
    if data.get("schema_version") != expected_version:
        raise ValueError(f"{path} must declare schema_version = {expected_version}")
    return data


def _registry_document(path: Path, collection: str) -> Mapping[str, object]:
    """Read one strict current-state registry envelope."""

    data = _document(path, expected_version=1)
    _exact_keys(data, {"schema_version", collection}, str(path))
    return data


def _exact_keys(data: Mapping[str, object], expected: set[str], label: str) -> None:
    """Reject missing and history-shaped surplus fields."""

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


def _date(data: Mapping[str, object], key: str) -> date:
    """Return one required TOML date."""

    value = data.get(key)
    if not isinstance(value, date):
        raise TypeError(f"{key} must be an ISO date")
    return value
