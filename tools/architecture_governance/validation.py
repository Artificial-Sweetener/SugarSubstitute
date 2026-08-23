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

"""Validate structural limits and current architecture state."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from .loading import load_policy, load_state
from .metrics import governed_source_paths, production_line_count, source_fingerprint
from .model import (
    ArchitectureDebt,
    ArchitecturePolicy,
    ArchitectureState,
    ArchitectureWaiver,
    Diagnostic,
)

_OWNERSHIP_RESPONSE = (
    "Assess the file's concern, authoritative state owner, dependency direction, "
    "public boundary, behavior contract, and change cadence. If ownership is "
    "mixed, adding behavior is prohibited: characterize the touched behavior, "
    "extract focused owners, migrate every caller, and remove replaced code and "
    "bridges. A waiver can bound a size exception; it cannot authorize new "
    "behavior in mixed code."
)
_MINIMUM_STRUCTURAL_JUSTIFICATION_LENGTH = 160
_MECHANICAL_STRUCTURAL_JUSTIFICATION = (
    "Its production types and helpers serve that one authoritative contract"
)


def validate_repository(
    root: Path,
    *,
    policy_path: Path | None = None,
    today: date | None = None,
) -> list[Diagnostic]:
    """Return every architecture diagnostic for the current repository."""

    try:
        policy = load_policy(policy_path or root / "ARCHITECTURE_POLICY.toml")
        state = load_state(root, policy)
    except (OSError, TypeError, ValueError) as error:
        return [Diagnostic("STATE001", "ARCHITECTURE_POLICY.toml", str(error))]
    current_date = today or datetime.now(UTC).date()
    diagnostics = [
        *_validate_policy(root, policy),
        *_validate_state(root, policy, state, current_date),
    ]
    diagnostics.extend(_validate_structure(root, policy, state, current_date))
    if (root / "substitute/app/bootstrap/persistent_cache_catalog.py").is_file():
        from tools.cache_governance.validation import validate_cache_governance

        diagnostics.extend(validate_cache_governance(root))
    return sorted(
        diagnostics,
        key=lambda item: (item.path, item.rule, item.severity, item.message),
    )


def _validate_policy(root: Path, policy: ArchitecturePolicy) -> list[Diagnostic]:
    """Validate coherent limits and exact configured source scope."""

    diagnostics: list[Diagnostic] = []
    if policy.soft_lines >= policy.hard_lines:
        diagnostics.append(
            Diagnostic(
                "POLICY001",
                "ARCHITECTURE_POLICY.toml",
                "soft_lines must be lower than hard_lines",
            )
        )
    for source_root in policy.source_roots:
        if not (root / source_root).is_dir():
            diagnostics.append(
                Diagnostic(
                    "POLICY002",
                    "ARCHITECTURE_POLICY.toml",
                    f"source root {source_root.as_posix()} does not exist",
                )
            )
    for source_file in policy.source_files:
        if not (root / source_file).is_file():
            diagnostics.append(
                Diagnostic(
                    "POLICY004",
                    "ARCHITECTURE_POLICY.toml",
                    f"source file {source_file.as_posix()} does not exist",
                )
            )
        elif source_file.suffix not in policy.source_extensions:
            diagnostics.append(
                Diagnostic(
                    "POLICY005",
                    "ARCHITECTURE_POLICY.toml",
                    f"source file {source_file.as_posix()} has an ungoverned extension",
                )
            )
    for excluded_path in sorted(policy.excluded_paths):
        if not (root / excluded_path).is_file():
            diagnostics.append(
                Diagnostic(
                    "POLICY003",
                    "ARCHITECTURE_POLICY.toml",
                    f"excluded source {excluded_path} does not exist",
                )
            )
    return diagnostics


def _validate_state(
    root: Path,
    policy: ArchitecturePolicy,
    state: ArchitectureState,
    today: date,
) -> list[Diagnostic]:
    """Validate registry uniqueness, paths, fingerprints, dates, and links."""

    diagnostics = _validate_unique_state(state)
    governed = {
        path.relative_to(root).as_posix()
        for path in governed_source_paths(root, policy)
    }
    debt_by_id = {debt.identifier: debt for debt in state.debts}
    for debt in state.debts:
        registry = policy.debt_registry.as_posix()
        valid_paths = tuple(path for path in debt.paths if path in governed)
        if len(valid_paths) != len(debt.paths):
            diagnostics.append(
                Diagnostic(
                    "DEBT001",
                    registry,
                    f"debt {debt.identifier} must reference exact governed source paths",
                )
            )
        elif source_fingerprint(root, debt.paths) != debt.fingerprint:
            diagnostics.append(
                Diagnostic(
                    "DEBT002",
                    registry,
                    f"debt {debt.identifier} no longer matches assessed source; reassess "
                    "current responsibilities and the next extraction or delete resolved debt",
                )
            )
        if debt.review_by < today:
            diagnostics.append(
                Diagnostic(
                    "DEBT003",
                    registry,
                    f"debt {debt.identifier} review deadline expired on {debt.review_by.isoformat()}",
                )
            )
        linked_waivers = tuple(
            waiver
            for waiver in state.waivers
            if waiver.kind == "remediation" and waiver.debt == debt.identifier
        )
        if len(linked_waivers) != 1:
            diagnostics.append(
                Diagnostic(
                    "DEBT004",
                    registry,
                    f"debt {debt.identifier} must have exactly one linked remediation "
                    f"waiver; found {len(linked_waivers)}",
                )
            )
    for waiver in state.waivers:
        diagnostics.extend(
            _validate_waiver(root, policy, waiver, debt_by_id, governed, today)
        )
    return diagnostics


def _validate_unique_state(state: ArchitectureState) -> list[Diagnostic]:
    """Reject duplicate paths and record identifiers across current state."""

    diagnostics: list[Diagnostic] = []
    identifiers = [
        *(debt.identifier for debt in state.debts),
        *(waiver.identifier for waiver in state.waivers),
    ]
    for identifier, count in Counter(identifiers).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "STATE002",
                    "ARCHITECTURE_POLICY.toml",
                    f"architecture record id {identifier} is not unique",
                )
            )
    classified_paths = [waiver.path for waiver in state.waivers]
    for path, count in Counter(classified_paths).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "STATE003",
                    "ARCHITECTURE_POLICY.toml",
                    f"source path {path} has multiple structural dispositions",
                )
            )
    debt_paths = [path for debt in state.debts for path in debt.paths]
    for path, count in Counter(debt_paths).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "STATE004",
                    "ARCHITECTURE_DEBT.toml",
                    f"source path {path} appears in multiple debt records",
                )
            )
    structural_justifications = [
        waiver.justification for waiver in state.waivers if waiver.kind == "structural"
    ]
    for justification, count in Counter(structural_justifications).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "WAIVER011",
                    "ARCHITECTURE_WAIVERS.toml",
                    "structural waiver rationales must be unique and file-specific",
                )
            )
    return diagnostics


def _validate_waiver(
    root: Path,
    policy: ArchitecturePolicy,
    waiver: ArchitectureWaiver,
    debts: dict[str, ArchitectureDebt],
    governed: set[str],
    today: date,
) -> list[Diagnostic]:
    """Validate one exact, bounded, current architecture waiver."""

    registry = policy.waiver_registry.as_posix()
    diagnostics: list[Diagnostic] = []
    if waiver.rule != "STRUCT003":
        diagnostics.append(
            Diagnostic(
                "WAIVER001",
                registry,
                f"waiver {waiver.identifier} uses an unsupported rule",
            )
        )
    if waiver.path not in governed:
        diagnostics.append(
            Diagnostic(
                "WAIVER002",
                registry,
                f"waiver {waiver.identifier} path is not governed",
            )
        )
        return diagnostics
    lines = production_line_count(root / waiver.path)
    if waiver.review_by < today:
        diagnostics.append(
            Diagnostic(
                "WAIVER003",
                registry,
                f"waiver {waiver.identifier} expired on {waiver.review_by.isoformat()}",
            )
        )
    if lines > waiver.max_lines:
        diagnostics.append(
            Diagnostic(
                "WAIVER004",
                registry,
                f"waiver {waiver.identifier} caps {waiver.path} at "
                f"{waiver.max_lines} lines but current source has {lines}",
            )
        )
    if lines <= policy.hard_lines:
        diagnostics.append(
            Diagnostic(
                "WAIVER005",
                registry,
                f"waiver {waiver.identifier} matches no current hard-size finding; delete it",
            )
        )
    if lines != waiver.max_lines:
        diagnostics.append(
            Diagnostic(
                "WAIVER008",
                registry,
                f"waiver {waiver.identifier} must cap the exact current size "
                f"of {waiver.path} at {lines} lines; reassess the source",
            )
        )
    if waiver.kind == "remediation":
        debt = debts.get(waiver.debt or "")
        if debt is None or waiver.path not in debt.paths:
            diagnostics.append(
                Diagnostic(
                    "WAIVER006",
                    registry,
                    f"waiver {waiver.identifier} must link assessed debt for the same exact path",
                )
            )
        if waiver.next_limit is None or waiver.next_limit >= waiver.max_lines:
            diagnostics.append(
                Diagnostic(
                    "WAIVER007",
                    registry,
                    f"waiver {waiver.identifier} next_limit must be lower than max_lines",
                )
            )
    else:
        if any(waiver.path in debt.paths for debt in debts.values()):
            diagnostics.append(
                Diagnostic(
                    "WAIVER009",
                    registry,
                    f"structural waiver {waiver.identifier} cannot cover a path recorded "
                    "as mixed-responsibility debt",
                )
            )
        if (
            len(waiver.justification) < _MINIMUM_STRUCTURAL_JUSTIFICATION_LENGTH
            or _MECHANICAL_STRUCTURAL_JUSTIFICATION in waiver.justification
        ):
            diagnostics.append(
                Diagnostic(
                    "WAIVER010",
                    registry,
                    f"structural waiver {waiver.identifier} requires a substantive, "
                    "file-specific cohesion rationale; human source review is mandatory",
                )
            )
    return diagnostics


def _validate_structure(
    root: Path,
    policy: ArchitecturePolicy,
    state: ArchitectureState,
    today: date,
) -> list[Diagnostic]:
    """Enforce the structural size ceiling against exact current dispositions."""

    waivers = {
        waiver.path: waiver
        for waiver in state.waivers
        if waiver.review_by >= today and waiver.rule == "STRUCT003"
    }
    diagnostics: list[Diagnostic] = []
    for path in governed_source_paths(root, policy):
        relative_path = path.relative_to(root).as_posix()
        lines = production_line_count(path)
        if lines > policy.hard_lines:
            if relative_path not in waivers:
                diagnostics.append(
                    Diagnostic(
                        "STRUCT003",
                        relative_path,
                        f"{lines} production lines exceed the hard gate "
                        f"{policy.hard_lines}. {_OWNERSHIP_RESPONSE}",
                    )
                )
        elif lines > policy.soft_lines:
            diagnostics.append(
                Diagnostic(
                    "STRUCT002",
                    relative_path,
                    f"{lines} production lines exceed the soft ceiling "
                    f"{policy.soft_lines}; assess ownership before extending this file",
                    severity="warning",
                )
            )
    return diagnostics
