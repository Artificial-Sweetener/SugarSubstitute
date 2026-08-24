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

"""Prove exact candidate discovery and reviewed test-governance state."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tools.test_governance.discovery import discover_test_candidates
from tools.test_governance.ownership_patterns import (
    MODULE_RESOURCE_RULE,
    SIBLING_IMPORT_RULE,
)
from tools.test_governance.semantic_patterns import (
    DRAIN_RULE,
    NETWORK_RULE,
    OPTIONAL_PROOF_RULE,
    RANDOMNESS_RULE,
    SUPPRESSED_FAILURE_RULE,
    UNBOUNDED_WAIT_RULE,
)
from tools.test_governance.loading import load_test_policy
from tools.test_governance.metrics import reviewed_state_fingerprint
from tools.test_governance.validation import validate_test_governance
from .support import write as _write
from .support import write_fixture as _write_fixture


def test_discovery_reports_layout_stub_execution_time_and_resource_candidates(
    tmp_path: Path,
) -> None:
    """Objective source patterns receive stable rule and scope identities."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/test_candidate.py",
        """import os
import time

def test_candidate() -> None:
    started = time.perf_counter()
    time.sleep(0.1)
    assert (time.perf_counter() - started) < 1.0
    assert os.environ.get("PYTEST_XDIST_WORKER") is None
    artifact = ".pytest-tmp/result.json"
    del artifact

def bind(listener: object) -> None:
    listener.bind(("127.0.0.1", 8123))
""",
    )
    _write(tmp_path / "tests/test_candidate.pyi", "VALUE: int\n")
    _write(
        tmp_path / "tests/ci_test_policy.py",
        'ISOLATED_TEST_MODULES = frozenset({"tests/test_isolated.py"})\n'
        'SERIAL_TEST_MODULES = frozenset({"tests/test_candidate.py"})\n',
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = discover_test_candidates(tmp_path, policy)
    rules = {candidate.rule for candidate in candidates}

    assert rules == {
        "CLOCK001",
        "ISOLATED001",
        "LAYOUT001",
        "RESOURCE001",
        "SCRATCH001",
        "SERIAL001",
        "STUB001",
        "WAIT001",
        "XDIST001",
    }
    assert len({candidate.key for candidate in candidates}) == len(candidates)


def test_discovery_resolves_imported_and_aliased_execution_calls(
    tmp_path: Path,
) -> None:
    """Imported wait, clock, and environment aliases remain visible to policy."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_aliases.py",
        """import os as environment
import time as clock
from time import sleep as pause

def test_aliases() -> None:
    started = clock.perf_counter()
    pause(0.1)
    assert clock.perf_counter() - started < 1.0
    assert environment.getenv("PYTEST_XDIST_WORKER") is None
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = discover_test_candidates(tmp_path, policy)

    assert {candidate.rule for candidate in candidates} == {
        "CLOCK001",
        "WAIT001",
        "XDIST001",
    }
    wait = next(candidate for candidate in candidates if candidate.rule == "WAIT001")
    assert ":wait:time.sleep:" in wait.locator


def test_discovery_reports_real_clock_bounded_polling_loops(tmp_path: Path) -> None:
    """A bounded timeout does not hide manual polling from human review."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_polling.py",
        """import time

def wait_until_ready() -> None:
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if ready():
            return

def ready() -> bool:
    return True
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = discover_test_candidates(tmp_path, policy)

    assert [candidate.rule for candidate in candidates] == ["POLL001"]


def test_discovery_reports_direct_process_environment_mutation(tmp_path: Path) -> None:
    """Process-global environment writes require exact ownership review."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_environment.py",
        """import os as environment

environment.environ.setdefault("MODE", "test")
environment.environ["OWNER"] = "capability"
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = discover_test_candidates(tmp_path, policy)

    assert [candidate.rule for candidate in candidates] == ["ENV001", "ENV001"]


def test_discovery_rejects_renamed_count_shaped_queued_turn_facades(
    tmp_path: Path,
) -> None:
    """Detect fake repetition contracts by semantics while allowing real bounds."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_event_delivery.py",
        """from tests.support.qt.semantic_wait import wait_for_queued_qt_turn as barrier

def settle_delivery(pass_count: int = 8) -> None:
    _ = pass_count
    barrier()

def optionally_settle(turn_budget: int = 8) -> None:
    if turn_budget:
        barrier()

def deliver_repeatedly(pass_count: int = 8) -> None:
    for _ in range(pass_count):
        barrier()

def bounded_barrier(timeout_ms: int = 3000) -> None:
    barrier(timeout_ms=timeout_ms)
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == DRAIN_RULE
    ]

    assert [candidate.locator for candidate in candidates] == [
        "optionally_settle:count-shaped-queued-turn:turn_budget",
        "settle_delivery:count-shaped-queued-turn:pass_count",
    ]


def test_discovery_rejects_executable_sibling_test_module_imports(
    tmp_path: Path,
) -> None:
    """Keep shared support out of executable test modules regardless of aliases."""

    _write_fixture(tmp_path)
    _write(tmp_path / "tests/capability/support.py", "VALUE = 1\n")
    _write(tmp_path / "tests/capability/test_owner.py", "VALUE = 2\n")
    _write(
        tmp_path / "tests/capability/test_consumer.py",
        """from . import support
from .test_owner import VALUE as OWNER_VALUE

def test_consumer() -> None:
    assert support.VALUE != OWNER_VALUE
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == SIBLING_IMPORT_RULE
    ]

    assert len(candidates) == 1
    assert candidates[0].path == "tests/capability/test_consumer.py"
    assert candidates[0].evidence.endswith("tests/capability/test_owner.py")


def test_discovery_rejects_optional_retry_and_order_dependent_proof(
    tmp_path: Path,
) -> None:
    """Detect renamed suppression mechanisms while allowing platform ownership."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_optional_proof.py",
        """import pytest as framework
from pytest import skip as omit

@framework.mark.skipif(condition(), reason="optional")
def test_conditionally_omitted() -> None:
    omit("missing prerequisite")

@framework.mark.flaky(reruns=3)
def test_retried() -> None:
    pass

@framework.mark.order(2)
def test_ordered() -> None:
    pass

@framework.mark.platforms("windows")
def test_platform_owned() -> None:
    pass
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == OPTIONAL_PROOF_RULE
    ]

    assert len(candidates) == 4
    assert all("platforms" not in candidate.evidence for candidate in candidates)


def test_discovery_rejects_unbounded_external_operations_and_waits(
    tmp_path: Path,
) -> None:
    """Resolve aliases and require explicit failure bounds at external boundaries."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_bounds.py",
        """import subprocess as process
from requests import get as fetch

def unbounded(worker: object, barrier: object) -> None:
    process.run(["tool"])
    fetch("https://example.invalid")
    worker.join()
    barrier.wait()

def bounded(worker: object, barrier: object) -> None:
    process.run(["tool"], timeout=10)
    fetch("https://example.invalid", timeout=10)
    worker.join(10)
    barrier.wait(timeout=10)
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == UNBOUNDED_WAIT_RULE
    ]

    assert len(candidates) == 4


def test_discovery_rejects_silent_broad_failure_suppression(tmp_path: Path) -> None:
    """Require broad failures to remain observable regardless of renamed helpers."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_suppression.py",
        """import contextlib as contexts

def suppressed() -> None:
    try:
        operation()
    except Exception:
        pass
    with contexts.suppress(BaseException):
        operation()

def observable() -> None:
    try:
        operation()
    except Exception as error:
        raise AssertionError("operation failed") from error
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == SUPPRESSED_FAILURE_RULE
    ]

    assert len(candidates) == 2


def test_discovery_rejects_module_resources_and_uncontrolled_randomness(
    tmp_path: Path,
) -> None:
    """Keep mutable resources test-owned and randomized behavior replayable."""

    _write_fixture(tmp_path)
    _write(
        tmp_path / "tests/capability/test_lifecycle.py",
        """import random as chance
import socket as networking
from PySide6.QtCore import QTimer as Timer
from tempfile import TemporaryDirectory as Scratch

LISTENER = networking.socket()
ROOT = Scratch()
TIMER = Timer()

def uncontrolled() -> object:
    return chance.choice((1, 2))

def replayable() -> object:
    positional = chance.Random(17).choice((1, 2))
    keyword = chance.Random(seed=17).choice((1, 2))
    return positional, keyword
""",
    )

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = discover_test_candidates(tmp_path, policy)

    assert (
        len(
            [
                candidate
                for candidate in candidates
                if candidate.rule == MODULE_RESOURCE_RULE
            ]
        )
        == 3
    )
    assert (
        len(
            [candidate for candidate in candidates if candidate.rule == RANDOMNESS_RULE]
        )
        == 1
    )


def test_discovery_reviews_real_network_outside_qualification(tmp_path: Path) -> None:
    """Keep environmental network access in an explicit qualification owner."""

    _write_fixture(tmp_path)
    source = """from requests import get as fetch

def contact_service() -> None:
    fetch("https://example.invalid", timeout=10)
"""
    _write(tmp_path / "tests/capability/test_network.py", source)
    _write(tmp_path / "tests/qualification/capability/test_network.py", source)

    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidates = [
        candidate
        for candidate in discover_test_candidates(tmp_path, policy)
        if candidate.rule == NETWORK_RULE
    ]

    assert len(candidates) == 1
    assert candidates[0].path == "tests/capability/test_network.py"


def test_unreviewed_candidate_fails_with_human_disposition_requirement(
    tmp_path: Path,
) -> None:
    """Mechanical discovery cannot silently decide whether a pattern is valid."""

    _write_fixture(tmp_path)
    _write(tmp_path / "tests/test_candidate.py", "VALUE = 1\n")

    result = validate_test_governance(tmp_path, today=date(2026, 8, 16))

    error = next(item for item in result.diagnostics if item.rule == "LAYOUT001")
    assert "perform source-level review" in error.message
    assert "classification or debt-remediation waiver" in error.message


def test_exact_classification_waiver_satisfies_one_current_candidate(
    tmp_path: Path,
) -> None:
    """A legitimate reviewed classification is exact, expiring, and fingerprinted."""

    _write_fixture(tmp_path)
    source_path = "tests/capability/test_candidate.py"
    _write(
        tmp_path / source_path,
        'import os\nVALUE = os.getenv("PYTEST_XDIST_WORKER")\n',
    )
    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidate = next(
        item
        for item in discover_test_candidates(tmp_path, policy)
        if item.rule == "XDIST001"
    )
    fingerprint = reviewed_state_fingerprint(
        tmp_path,
        rule=candidate.rule,
        candidates=(candidate.key,),
        paths=(source_path,),
    )
    rationale = (
        "This fixture deliberately represents framework infrastructure at the package "
        "root, where pytest must discover it before capability packages are imported; "
        "moving it would fragment the one collection-time contract."
    )
    _write(
        tmp_path / "TEST_WAIVERS.toml",
        "schema_version = 1\n[[waivers]]\n"
        'id = "TEST-WAIVER-001"\nowner = "test infrastructure"\n'
        'kind = "classification"\ndisposition = "framework_infrastructure"\n'
        'rule = "XDIST001"\n'
        f'candidates = ["{candidate.key}"]\npaths = ["{source_path}"]\n'
        f'fingerprint = "{fingerprint}"\n'
        f'rationale = "{rationale}"\nissue = "chore:TEST-WAIVER-001"\n'
        "review_by = 2026-12-15\n",
    )

    result = validate_test_governance(tmp_path, today=date(2026, 8, 16))

    assert not [item for item in result.diagnostics if item.severity == "error"]


def test_debt_requires_an_identical_linked_remediation_waiver(tmp_path: Path) -> None:
    """Inappropriate current test design remains explicit and bounded."""

    _write_fixture(tmp_path)
    source_path = "tests/test_candidate.py"
    _write(tmp_path / source_path, "VALUE = 1\n")
    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidate = discover_test_candidates(tmp_path, policy)[0]
    fingerprint = reviewed_state_fingerprint(
        tmp_path,
        rule=candidate.rule,
        candidates=(candidate.key,),
        paths=(source_path,),
    )
    common = (
        'rule = "LAYOUT001"\n'
        f'candidates = ["{candidate.key}"]\npaths = ["{source_path}"]\n'
        f'fingerprint = "{fingerprint}"\n'
        'issue = "chore:TEST-DEBT-001"\nreview_by = 2026-12-15\n'
    )
    _write(
        tmp_path / "TEST_DEBT.toml",
        "schema_version = 1\n[[debts]]\n"
        'id = "TEST-DEBT-001"\nowner = "candidate capability"\n'
        + common
        + 'problem = "The test is stored outside its capability owner."\n'
        + 'remediation = "Move the test into the candidate capability suite."\n',
    )
    rationale = (
        "The existing root placement is bounded only while the capability suites are "
        "created. The file may not grow at the root and will move atomically with its "
        "support imports and targeted execution path."
    )
    _write(
        tmp_path / "TEST_WAIVERS.toml",
        "schema_version = 1\n[[waivers]]\n"
        'id = "TEST-REMEDIATION-001"\nowner = "candidate capability"\n'
        'kind = "remediation"\ndisposition = "debt"\n'
        + common
        + f'rationale = "{rationale}"\ndebt = "TEST-DEBT-001"\n',
    )

    result = validate_test_governance(tmp_path, today=date(2026, 8, 16))

    assert not [item for item in result.diagnostics if item.severity == "error"]


def test_source_change_forces_reassessment_of_a_reviewed_candidate(
    tmp_path: Path,
) -> None:
    """A waiver cannot survive source changes without renewed human review."""

    _write_fixture(tmp_path)
    source_path = "tests/capability/test_candidate.py"
    _write(tmp_path / source_path, "import time\ntime.sleep(0.1)\n")
    policy = load_test_policy(tmp_path / "TEST_POLICY.toml")
    candidate = discover_test_candidates(tmp_path, policy)[0]
    fingerprint = reviewed_state_fingerprint(
        tmp_path,
        rule=candidate.rule,
        candidates=(candidate.key,),
        paths=(source_path,),
    )
    rationale = (
        "This deliberately long classification rationale establishes exact reviewed "
        "source identity for the fixture before a subsequent source edit invalidates "
        "the decision and requires another human assessment."
    )
    _write(
        tmp_path / "TEST_WAIVERS.toml",
        "schema_version = 1\n[[waivers]]\n"
        'id = "TEST-WAIVER-STALE"\nowner = "test infrastructure"\n'
        'kind = "classification"\ndisposition = "framework_infrastructure"\n'
        'rule = "WAIT001"\n'
        f'candidates = ["{candidate.key}"]\npaths = ["{source_path}"]\n'
        f'fingerprint = "{fingerprint}"\n'
        f'rationale = "{rationale}"\nissue = "chore:TEST-WAIVER-STALE"\n'
        "review_by = 2026-12-15\n",
    )
    _write(
        tmp_path / source_path,
        "import time\ntime.sleep(0.1)\nOTHER = 1\n",
    )

    result = validate_test_governance(tmp_path, today=date(2026, 8, 16))

    assert any(item.rule == "TWAIVER009" for item in result.diagnostics)


def test_current_repository_has_exact_reviewed_test_governance_state() -> None:
    """The committed policy must classify every exact current candidate."""

    repository_root = Path(__file__).resolve().parents[3]

    result = validate_test_governance(repository_root)

    assert not [item for item in result.diagnostics if item.severity == "error"]
