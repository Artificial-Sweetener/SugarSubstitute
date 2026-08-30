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

"""Validate discovered test candidates against exact reviewed state."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from tools.architecture_governance.model import Diagnostic

from .discovery import discover_test_candidates
from .loading import load_test_policy, load_test_state
from .metrics import reviewed_state_fingerprint
from .model import (
    TestCandidate,
    TestDebt,
    TestPolicy,
    TestState,
    TestValidationResult,
    TestWaiver,
)

_MINIMUM_RATIONALE_LENGTH = 120
_CLASSIFICATION_DISPOSITIONS = frozenset(
    {
        "false_positive",
        "framework_infrastructure",
        "intentional_real_time",
        "performance_qualification",
        "platform_native",
        "process_isolated",
        "resource_locked",
    }
)


def validate_test_governance(
    root: Path,
    *,
    policy_path: Path | None = None,
    today: date | None = None,
) -> TestValidationResult:
    """Return discovered candidates and every current governance diagnostic."""

    try:
        policy = load_test_policy(policy_path or root / "TEST_POLICY.toml")
        state = load_test_state(root, policy)
        candidates = discover_test_candidates(root, policy)
    except (OSError, SyntaxError, TypeError, ValueError) as error:
        return TestValidationResult(
            candidates=(),
            diagnostics=(Diagnostic("TSTATE001", "TEST_POLICY.toml", str(error)),),
        )
    current_date = today or datetime.now(UTC).date()
    diagnostics = [
        *_validate_policy(root, policy),
        *_validate_unique_state(state),
        *_validate_state(root, policy, state, candidates, current_date),
    ]
    return TestValidationResult(
        candidates=candidates,
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (item.path, item.rule, item.severity, item.message),
            )
        ),
    )


def _validate_policy(root: Path, policy: TestPolicy) -> list[Diagnostic]:
    """Validate exact policy paths and non-overlapping source declarations."""

    diagnostics: list[Diagnostic] = []
    if not (root / policy.test_root).is_dir():
        diagnostics.append(
            Diagnostic("TPOLICY001", "TEST_POLICY.toml", "test_root must exist")
        )
    for support_root in policy.semantic_support_roots:
        if not (root / support_root).is_dir():
            diagnostics.append(
                Diagnostic(
                    "TPOLICY004",
                    "TEST_POLICY.toml",
                    f"semantic support root {support_root.as_posix()} must exist",
                )
            )
    if not (root / policy.serial_policy).is_file():
        diagnostics.append(
            Diagnostic("TPOLICY002", "TEST_POLICY.toml", "serial_policy must exist")
        )
    for allowed_path in sorted(policy.allowed_root_source_paths):
        path = root / allowed_path
        if not path.is_file() or path.parent != root / policy.test_root:
            diagnostics.append(
                Diagnostic(
                    "TPOLICY003",
                    "TEST_POLICY.toml",
                    f"allowed root source {allowed_path} must exist directly under the test root",
                )
            )
    return diagnostics


def _validate_unique_state(state: TestState) -> list[Diagnostic]:
    """Reject duplicate identifiers and candidate dispositions."""

    diagnostics: list[Diagnostic] = []
    identifiers = [
        *(debt.identifier for debt in state.debts),
        *(waiver.identifier for waiver in state.waivers),
    ]
    for identifier, count in Counter(identifiers).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "TSTATE002",
                    "TEST_POLICY.toml",
                    f"test-governance record id {identifier} is not unique",
                )
            )
    classified = [
        candidate for waiver in state.waivers for candidate in waiver.candidates
    ]
    for candidate, count in Counter(classified).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "TSTATE003",
                    "TEST_WAIVERS.toml",
                    f"candidate {candidate} has multiple dispositions",
                )
            )
    debt_candidates = [
        candidate for debt in state.debts for candidate in debt.candidates
    ]
    for candidate, count in Counter(debt_candidates).items():
        if count > 1:
            diagnostics.append(
                Diagnostic(
                    "TSTATE004",
                    "TEST_DEBT.toml",
                    f"candidate {candidate} appears in multiple debt records",
                )
            )
    return diagnostics


def _validate_state(
    root: Path,
    policy: TestPolicy,
    state: TestState,
    candidates: tuple[TestCandidate, ...],
    today: date,
) -> list[Diagnostic]:
    """Validate reviewed records and require one disposition per candidate."""

    diagnostics: list[Diagnostic] = []
    candidates_by_key = {candidate.key: candidate for candidate in candidates}
    debt_by_id = {debt.identifier: debt for debt in state.debts}
    for debt in state.debts:
        diagnostics.extend(
            _validate_debt(root, policy, debt, candidates_by_key, state, today)
        )
    for waiver in state.waivers:
        diagnostics.extend(
            _validate_waiver(
                root,
                policy,
                waiver,
                candidates_by_key,
                debt_by_id,
                today,
            )
        )
    classified = {
        candidate for waiver in state.waivers for candidate in waiver.candidates
    }
    for candidate in candidates:
        if candidate.key in classified:
            continue
        diagnostics.append(
            Diagnostic(
                candidate.rule,
                candidate.path,
                f"{candidate.evidence} at {candidate.locator}; perform source-level review "
                "and record an exact classification or debt-remediation waiver",
            )
        )
    return diagnostics


def _validate_debt(
    root: Path,
    policy: TestPolicy,
    debt: TestDebt,
    candidates: dict[str, TestCandidate],
    state: TestState,
    today: date,
) -> list[Diagnostic]:
    """Validate one exact current test-debt assessment."""

    registry = policy.debt_registry.as_posix()
    diagnostics = _validate_record_identity(
        root,
        registry,
        debt.rule,
        debt.candidates,
        debt.paths,
        debt.fingerprint,
        candidates,
        "TDEBT",
    )
    if debt.review_by < today:
        diagnostics.append(
            Diagnostic(
                "TDEBT004",
                registry,
                f"debt {debt.identifier} expired on {debt.review_by.isoformat()}",
            )
        )
    linked = tuple(
        waiver
        for waiver in state.waivers
        if waiver.kind == "remediation" and waiver.debt == debt.identifier
    )
    if len(linked) != 1:
        diagnostics.append(
            Diagnostic(
                "TDEBT005",
                registry,
                f"debt {debt.identifier} must have exactly one remediation waiver; "
                f"found {len(linked)}",
            )
        )
    elif (
        linked[0].rule != debt.rule
        or linked[0].candidates != debt.candidates
        or linked[0].paths != debt.paths
        or linked[0].fingerprint != debt.fingerprint
    ):
        diagnostics.append(
            Diagnostic(
                "TDEBT006",
                registry,
                f"debt {debt.identifier} and its remediation waiver must cover identical state",
            )
        )
    return diagnostics


def _validate_waiver(
    root: Path,
    policy: TestPolicy,
    waiver: TestWaiver,
    candidates: dict[str, TestCandidate],
    debts: dict[str, TestDebt],
    today: date,
) -> list[Diagnostic]:
    """Validate one reviewed classification or remediation waiver."""

    registry = policy.waiver_registry.as_posix()
    diagnostics = _validate_record_identity(
        root,
        registry,
        waiver.rule,
        waiver.candidates,
        waiver.paths,
        waiver.fingerprint,
        candidates,
        "TWAIVER",
    )
    if waiver.review_by < today:
        diagnostics.append(
            Diagnostic(
                "TWAIVER004",
                registry,
                f"waiver {waiver.identifier} expired on {waiver.review_by.isoformat()}",
            )
        )
    if len(waiver.rationale) < _MINIMUM_RATIONALE_LENGTH:
        diagnostics.append(
            Diagnostic(
                "TWAIVER005",
                registry,
                f"waiver {waiver.identifier} requires a substantive source-specific rationale",
            )
        )
    if waiver.kind == "classification":
        if waiver.disposition not in _CLASSIFICATION_DISPOSITIONS:
            diagnostics.append(
                Diagnostic(
                    "TWAIVER006",
                    registry,
                    f"waiver {waiver.identifier} uses unsupported classification "
                    f"{waiver.disposition}",
                )
            )
    else:
        if waiver.disposition != "debt":
            diagnostics.append(
                Diagnostic(
                    "TWAIVER007",
                    registry,
                    f"remediation waiver {waiver.identifier} must use disposition debt",
                )
            )
        if waiver.debt not in debts:
            diagnostics.append(
                Diagnostic(
                    "TWAIVER008",
                    registry,
                    f"waiver {waiver.identifier} must link existing test debt",
                )
            )
    return diagnostics


def _validate_record_identity(
    root: Path,
    registry: str,
    rule: str,
    candidate_keys: tuple[str, ...],
    paths: tuple[str, ...],
    fingerprint: str,
    candidates: dict[str, TestCandidate],
    prefix: str,
) -> list[Diagnostic]:
    """Validate candidate, path, ordering, and source identity for one record."""

    diagnostics: list[Diagnostic] = []
    exact_candidates = tuple(
        candidates[key] for key in candidate_keys if key in candidates
    )
    if len(exact_candidates) != len(candidate_keys):
        diagnostics.append(
            Diagnostic(
                f"{prefix}001",
                registry,
                "record must reference exact current candidate keys",
            )
        )
        return diagnostics
    if any(candidate.rule != rule for candidate in exact_candidates):
        diagnostics.append(
            Diagnostic(
                f"{prefix}002",
                registry,
                f"record rule {rule} does not match all referenced candidates",
            )
        )
    expected_paths = tuple(sorted({candidate.path for candidate in exact_candidates}))
    if paths != expected_paths:
        diagnostics.append(
            Diagnostic(
                f"{prefix}003",
                registry,
                f"record paths must exactly equal sorted candidate paths {expected_paths}",
            )
        )
    elif (
        reviewed_state_fingerprint(
            root,
            rule=rule,
            candidates=candidate_keys,
            paths=paths,
        )
        != fingerprint
    ):
        diagnostics.append(
            Diagnostic(
                f"{prefix}009",
                registry,
                "record source fingerprint is stale; repeat human review",
            )
        )
    if candidate_keys != tuple(sorted(candidate_keys)):
        diagnostics.append(
            Diagnostic(
                f"{prefix}010",
                registry,
                "record candidates must use stable sorted order",
            )
        )
    return diagnostics
