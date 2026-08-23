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

"""Test architecture size, debt, and waiver governance."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tools.architecture_governance.metrics import source_fingerprint
from tools.architecture_governance.validation import validate_repository


def _write(path: Path, content: str) -> None:
    """Write one UTF-8 fixture after creating its parent."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_policy(root: Path) -> None:
    """Write a compact architecture policy and empty current state."""

    _write(
        root / "ARCHITECTURE_POLICY.toml",
        """schema_version = 2
[structure]
soft_lines = 4
hard_lines = 6
source_roots = ["product"]
source_files = ["entrypoint.py"]
source_extensions = [".cjs", ".js", ".mjs", ".py", ".pyi", ".spec"]
excluded_paths = ["product/generated.py"]
[registries]
debt = "ARCHITECTURE_DEBT.toml"
waivers = "ARCHITECTURE_WAIVERS.toml"
""",
    )
    _write(root / "entrypoint.py", "VALUE = 1\n")
    _write(root / "product/generated.py", "VALUE = 1\n")
    _write(root / "ARCHITECTURE_DEBT.toml", "schema_version = 1\ndebts = []\n")
    _write(root / "ARCHITECTURE_WAIVERS.toml", "schema_version = 1\nwaivers = []\n")


def _large_source() -> str:
    """Return source above the compact fixture's hard limit."""

    return "\n".join(f"VALUE_{index} = {index}" for index in range(8)) + "\n"


def test_unclassified_hard_overage_requires_ownership_judgment(tmp_path: Path) -> None:
    """A new large file fails with the required mixed-ownership response."""

    _write_policy(tmp_path)
    _write(tmp_path / "product/large.py", _large_source())

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))

    hard_error = next(item for item in diagnostics if item.rule == "STRUCT003")
    assert "adding behavior is prohibited" in hard_error.message
    assert "cannot authorize new behavior in mixed code" in hard_error.message


def test_policy_governs_declared_extensions_and_exact_source_files(
    tmp_path: Path,
) -> None:
    """Authored code is governed across roots, extensions, and exact entrypoints."""

    _write_policy(tmp_path)
    _write(tmp_path / "product/release.mjs", _large_source())
    _write(tmp_path / "product/package.spec", _large_source())
    _write(tmp_path / "product/data.json", _large_source())
    _write(tmp_path / "outside.py", _large_source())

    hard_paths = {
        item.path
        for item in validate_repository(tmp_path, today=date(2026, 8, 11))
        if item.rule == "STRUCT003"
    }

    assert hard_paths == {"product/package.spec", "product/release.mjs"}


def test_invalid_exact_source_files_report_policy_errors_without_being_scanned(
    tmp_path: Path,
) -> None:
    """Invalid exact files fail policy validation without crashing measurement."""

    _write_policy(tmp_path)
    policy_path = tmp_path / "ARCHITECTURE_POLICY.toml"
    policy_text = policy_path.read_text(encoding="utf-8").replace(
        'source_files = ["entrypoint.py"]',
        'source_files = ["missing.py", "entrypoint.json"]',
    )
    _write(policy_path, policy_text)
    _write(tmp_path / "entrypoint.json", _large_source())

    rules = {
        item.rule for item in validate_repository(tmp_path, today=date(2026, 8, 11))
    }

    assert {"POLICY004", "POLICY005"} <= rules


def test_javascript_measurement_excludes_standalone_comments(tmp_path: Path) -> None:
    """JavaScript comment blocks do not create false structural overages."""

    _write_policy(tmp_path)
    _write(
        tmp_path / "product/comments.cjs",
        "// heading\n/*\nblock comment\n*/ // trailing comment\n" + _large_source(),
    )

    hard_error = next(
        item
        for item in validate_repository(tmp_path, today=date(2026, 8, 11))
        if item.rule == "STRUCT003"
    )

    assert hard_error.path == "product/comments.cjs"
    assert hard_error.message.startswith("8 production lines")


def test_assessed_debt_requires_a_tightening_remediation_waiver(
    tmp_path: Path,
) -> None:
    """Mixed debt and its size exception remain exact, linked, and bounded."""

    _write_policy(tmp_path)
    source_path = "product/mixed.py"
    _write(tmp_path / source_path, _large_source())
    fingerprint = source_fingerprint(tmp_path, (source_path,))
    _write(
        tmp_path / "ARCHITECTURE_DEBT.toml",
        "schema_version = 1\n[[debts]]\n"
        'id = "SS-ARCH-TEST"\nowner = "fixture owner"\n'
        f'paths = ["{source_path}"]\n'
        f'fingerprint = "{fingerprint}"\n'
        'issue = "chore:SS-ARCH-TEST"\nreview_by = 2026-12-15\n'
        'responsibilities = ["state", "presentation"]\n'
        'next_extraction = "Extract presentation from state ownership."\n',
    )
    _write(
        tmp_path / "ARCHITECTURE_WAIVERS.toml",
        "schema_version = 1\n[[waivers]]\n"
        'id = "SS-WAIVER-TEST"\nowner = "fixture owner"\n'
        'rule = "STRUCT003"\n'
        f'path = "{source_path}"\nkind = "remediation"\n'
        'justification = "Current mixed ownership is queued for extraction."\n'
        'issue = "chore:SS-ARCH-TEST"\nreview_by = 2026-12-15\n'
        'max_lines = 8\nnext_limit = 5\ndebt = "SS-ARCH-TEST"\n',
    )

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))

    assert not any(item.severity == "error" for item in diagnostics)


def test_expired_and_unused_state_is_rejected(tmp_path: Path) -> None:
    """State records cannot silently become permanent or outlive findings."""

    _write_policy(tmp_path)
    source_path = "product/small.py"
    _write(tmp_path / source_path, "VALUE = 1\n")
    _write(
        tmp_path / "ARCHITECTURE_WAIVERS.toml",
        "schema_version = 1\n[[waivers]]\n"
        'id = "SS-WAIVER-STALE"\nowner = "fixture owner"\n'
        'rule = "STRUCT003"\n'
        f'path = "{source_path}"\nkind = "structural"\n'
        'justification = "Deliberately stale fixture waiver."\n'
        'issue = "chore:SS-WAIVER-STALE"\nreview_by = 2026-01-01\n'
        "max_lines = 8\n",
    )

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))
    rules = {item.rule for item in diagnostics}

    assert {"WAIVER003", "WAIVER005"} <= rules


def test_debt_requires_exactly_one_remediation_waiver(tmp_path: Path) -> None:
    """Assessed mixed ownership cannot exist without an exact remediation path."""

    _write_policy(tmp_path)
    source_path = "product/mixed.py"
    _write(tmp_path / source_path, _large_source())
    fingerprint = source_fingerprint(tmp_path, (source_path,))
    _write(
        tmp_path / "ARCHITECTURE_DEBT.toml",
        "schema_version = 1\n[[debts]]\n"
        'id = "SS-ARCH-UNLINKED"\nowner = "fixture owner"\n'
        f'paths = ["{source_path}"]\n'
        f'fingerprint = "{fingerprint}"\n'
        'issue = "chore:SS-ARCH-UNLINKED"\nreview_by = 2026-12-15\n'
        'responsibilities = ["state", "presentation"]\n'
        'next_extraction = "Extract presentation from state ownership."\n',
    )

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))

    assert any(item.rule == "DEBT004" for item in diagnostics)


def test_structural_waiver_requires_exact_current_cap_and_specific_rationale(
    tmp_path: Path,
) -> None:
    """A structural exception forces source review instead of allowing growth."""

    _write_policy(tmp_path)
    source_path = "product/cohesive.py"
    _write(tmp_path / source_path, _large_source())
    _write(
        tmp_path / "ARCHITECTURE_WAIVERS.toml",
        "schema_version = 1\n[[waivers]]\n"
        'id = "SS-WAIVER-STRUCTURAL"\nowner = "fixture owner"\n'
        'rule = "STRUCT003"\n'
        f'path = "{source_path}"\nkind = "structural"\n'
        'justification = "One broad module theme is sufficient."\n'
        'issue = "chore:SS-WAIVER-STRUCTURAL"\nreview_by = 2026-12-15\n'
        "max_lines = 9\n",
    )

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))
    rules = {item.rule for item in diagnostics}

    assert {"WAIVER008", "WAIVER010"} <= rules


def test_structural_waiver_rationales_must_be_unique(tmp_path: Path) -> None:
    """Copied structural rationales cannot stand in for two source reviews."""

    _write_policy(tmp_path)
    rationale = (
        "This fixture owns one concrete immutable state machine and every operation "
        "preserves the same transition invariant. Splitting its transitions would "
        "divide the authoritative lifecycle and duplicate its ordering constraints."
    )
    records: list[str] = []
    for index in range(2):
        source_path = f"product/cohesive_{index}.py"
        _write(tmp_path / source_path, _large_source())
        records.append(
            "[[waivers]]\n"
            f'id = "SS-WAIVER-{index}"\nowner = "fixture owner {index}"\n'
            'rule = "STRUCT003"\n'
            f'path = "{source_path}"\nkind = "structural"\n'
            f'justification = "{rationale}"\n'
            f'issue = "chore:SS-WAIVER-{index}"\nreview_by = 2026-12-15\n'
            "max_lines = 8\n"
        )
    _write(
        tmp_path / "ARCHITECTURE_WAIVERS.toml",
        "schema_version = 1\n" + "\n".join(records),
    )

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))

    assert any(item.rule == "WAIVER011" for item in diagnostics)


def test_registry_rejects_history_fields(tmp_path: Path) -> None:
    """Current architecture state cannot become an append-only history ledger."""

    _write_policy(tmp_path)
    _write(
        tmp_path / "ARCHITECTURE_DEBT.toml",
        "schema_version = 1\n[[debts]]\n"
        'id = "SS-ARCH-HISTORY"\nowner = "fixture owner"\n'
        'paths = ["product/generated.py"]\nfingerprint = "sha256:stale"\n'
        'issue = "chore:SS-ARCH-HISTORY"\nreview_by = 2026-12-15\n'
        'responsibilities = ["state", "presentation"]\n'
        'next_extraction = "Extract presentation."\nprevious_lines = 900\n',
    )

    diagnostics = validate_repository(tmp_path, today=date(2026, 8, 11))

    state_error = next(item for item in diagnostics if item.rule == "STATE001")
    assert "unsupported=['previous_lines']" in state_error.message


def test_current_repository_has_no_architecture_governance_errors() -> None:
    """The checked-in architectural state remains exact and enforceable."""

    root = Path(__file__).resolve().parents[3]
    errors = [item for item in validate_repository(root) if item.severity == "error"]

    assert errors == []
