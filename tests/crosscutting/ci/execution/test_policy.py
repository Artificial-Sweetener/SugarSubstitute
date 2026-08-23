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

"""Verify authoritative CI test execution and applicability policy."""

from __future__ import annotations

import ast
import configparser
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import pytest_ignore_collect
from tests.ci_test_policy import (
    ISOLATED_TEST_MODULES,
    PLATFORM_TEST_MODULES,
    CiPlatform,
    SERIAL_TEST_MODULES,
    current_test_platform,
    isolated_test_worker_count,
    marker_test_platforms,
    parallel_test_worker_count,
    platform_skip_reason,
)
from tools.test_governance.discovery import XDIST_RULE, discover_test_candidates
from tools.test_governance.loading import load_test_policy


PROJECT_ROOT = Path(__file__).resolve().parents[4]
TESTS_ROOT = PROJECT_ROOT / "tests"
OUTPUT_NAVIGATION_CONTRACT_MODULE = (
    "tests/presentation/canvas/output/navigation/test_cross_layer_contract.py"
)
PROJECTION_LAYOUT_CONTRACT_MODULES = frozenset(
    {
        "tests/presentation/editor/prompt_editor/layout/contracts/test_canonical_wrapping.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_incremental_policy.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_incremental_reuse.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_trailing_incremental.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_newline_incremental.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_token_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_selection_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_reorder_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_scene_geometry.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_token_paint.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_separator_navigation.py",
        "tests/presentation/editor/prompt_editor/layout/contracts/test_region_chrome.py",
    }
)


@pytest.mark.parametrize(
    ("available_workers", "expected"),
    [(None, 1), (0, 1), (1, 1), (4, 4), (32, 4)],
)
def test_parallel_test_worker_count_bounds_native_qt_concurrency(
    available_workers: int | None,
    expected: int,
) -> None:
    """Keep `-n auto` stable on low-core CI and high-core workstations."""

    assert parallel_test_worker_count(available_workers) == expected


@pytest.mark.parametrize(
    ("available_workers", "expected"),
    [(None, 1), (0, 1), (1, 1), (4, 4), (32, 4)],
)
def test_isolated_test_worker_count_bounds_fresh_process_concurrency(
    available_workers: int | None,
    expected: int,
) -> None:
    """Keep overlapping fresh Qt processes inside the qualified envelope."""

    assert isolated_test_worker_count(available_workers) == expected


def test_repository_pytest_config_does_not_share_a_session_temp_root() -> None:
    """Let pytest allocate a unique system-temp owner for each top-level run."""

    parser = configparser.ConfigParser()
    parser.read(PROJECT_ROOT / "pytest.ini", encoding="utf-8")

    assert "--basetemp" not in parser["pytest"]["addopts"]


@pytest.mark.parametrize(
    ("sys_platform", "expected"),
    [
        ("win32", CiPlatform.WINDOWS),
        ("linux", CiPlatform.LINUX),
        ("linux2", CiPlatform.LINUX),
        ("darwin", CiPlatform.MACOS),
    ],
)
def test_current_test_platform_normalizes_supported_runtime_values(
    sys_platform: str,
    expected: CiPlatform,
) -> None:
    """Map runtime platform values to the names used by test markers."""

    assert current_test_platform(sys_platform) is expected


def test_current_test_platform_rejects_unsupported_runtime() -> None:
    """Fail collection rather than silently running an unclassified platform."""

    with pytest.raises(ValueError, match="Unsupported test platform"):
        current_test_platform("plan9")


def test_marker_test_platforms_validates_declared_names() -> None:
    """Accept supported marker names and reject misspelled platform policy."""

    assert marker_test_platforms(("linux", "macos")) == frozenset(
        {CiPlatform.LINUX, CiPlatform.MACOS}
    )
    with pytest.raises(ValueError, match="Unsupported platforms marker value"):
        marker_test_platforms(("linus",))


def test_platform_skip_reason_reports_applicability() -> None:
    """Skip only when the current operating system is outside the declared set."""

    supported = frozenset({CiPlatform.LINUX, CiPlatform.MACOS})

    assert platform_skip_reason(supported=supported, current=CiPlatform.LINUX) is None
    assert (
        platform_skip_reason(
            supported=supported,
            current=CiPlatform.WINDOWS,
        )
        == "Test applies only to: linux, macos; current platform: windows."
    )


def test_constrained_inventory_covers_existing_xdist_sensitive_modules() -> None:
    """Keep actual xdist environment readers out of the xdist partition."""

    policy = load_test_policy(PROJECT_ROOT / "TEST_POLICY.toml")
    discovered = frozenset(
        candidate.path
        for candidate in discover_test_candidates(PROJECT_ROOT, policy)
        if candidate.rule == XDIST_RULE
        and Path(candidate.path).name.startswith("test_")
    )

    assert discovered <= ISOLATED_TEST_MODULES | SERIAL_TEST_MODULES
    assert ISOLATED_TEST_MODULES.isdisjoint(SERIAL_TEST_MODULES)
    assert {
        relative_path
        for relative_path in ISOLATED_TEST_MODULES | SERIAL_TEST_MODULES
        if not (PROJECT_ROOT / relative_path).is_file()
    } == set()


def test_projection_layout_contracts_use_bounded_fresh_process_lane() -> None:
    """Run native text layout outside xdist without serializing unrelated work."""

    assert PROJECTION_LAYOUT_CONTRACT_MODULES <= ISOLATED_TEST_MODULES
    assert PROJECTION_LAYOUT_CONTRACT_MODULES.isdisjoint(SERIAL_TEST_MODULES)


def test_output_navigation_contract_remains_in_ordinary_parallel_ci() -> None:
    """Keep the canvas navigation truth matrix in the always-run partition."""

    contract_path = PROJECT_ROOT / OUTPUT_NAVIGATION_CONTRACT_MODULE
    worker_environment_name = "PYTEST_" + "XDIST_WORKER"

    assert contract_path.is_file()
    assert OUTPUT_NAVIGATION_CONTRACT_MODULE not in ISOLATED_TEST_MODULES
    assert OUTPUT_NAVIGATION_CONTRACT_MODULE not in SERIAL_TEST_MODULES
    assert OUTPUT_NAVIGATION_CONTRACT_MODULE not in PLATFORM_TEST_MODULES
    assert worker_environment_name not in contract_path.read_text(encoding="utf-8")


def test_platform_module_inventory_references_existing_test_modules() -> None:
    """Keep pre-import platform applicability explicit and free of stale paths."""

    assert PLATFORM_TEST_MODULES == {}
    assert all(
        (PROJECT_ROOT / relative_path).is_file()
        for relative_path in PLATFORM_TEST_MODULES
    )


def test_empty_platform_inventory_bypasses_path_resolution() -> None:
    """Avoid path work when no module needs pre-import platform filtering."""

    assert PLATFORM_TEST_MODULES == {}
    assert (
        pytest_ignore_collect(
            cast(Path, object()),
            cast(pytest.Config, object()),
        )
        is None
    )


def test_platform_applicability_uses_auditable_markers() -> None:
    """Prevent direct OS skip conditions from bypassing platform inventory."""

    findings: list[str] = []
    for path in TESTS_ROOT.rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            if _call_name(node.func) != "pytest.mark.skipif":
                continue
            condition = ast.unparse(node.args[0])
            if "sys.platform" in condition or "os.name" in condition:
                findings.append(
                    f"{path.relative_to(PROJECT_ROOT).as_posix()}:{node.lineno}"
                )

    assert findings == []


def _call_name(node: ast.AST) -> str:
    """Return a dotted call name for one AST expression."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""
