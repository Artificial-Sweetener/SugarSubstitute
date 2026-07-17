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
from pathlib import Path

import pytest

from tests.ci_test_policy import (
    CiPlatform,
    SERIAL_TEST_MODULES,
    current_test_platform,
    marker_test_platforms,
    parallel_test_worker_count,
    platform_skip_reason,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = PROJECT_ROOT / "tests"


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


def test_serial_inventory_covers_existing_xdist_sensitive_modules() -> None:
    """Require every xdist-sensitive module to belong to the serial partition."""

    worker_environment_name = "PYTEST_" + "XDIST_WORKER"
    discovered = frozenset(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in TESTS_ROOT.rglob("test_*.py")
        if worker_environment_name in path.read_text(encoding="utf-8")
    )

    assert discovered <= SERIAL_TEST_MODULES
    assert {
        relative_path
        for relative_path in SERIAL_TEST_MODULES
        if not (PROJECT_ROOT / relative_path).is_file()
    } == set()


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
