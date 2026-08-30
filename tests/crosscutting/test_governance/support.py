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

"""Build isolated repositories for test-governance checker contracts."""

from __future__ import annotations

from pathlib import Path


def write(path: Path, content: str) -> None:
    """Write one UTF-8 fixture after creating its parent."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_fixture(root: Path) -> None:
    """Write a minimal valid test-governance repository."""

    write(
        root / "TEST_POLICY.toml",
        """schema_version = 1
[scope]
test_root = "tests"
semantic_support_roots = ["tools/test_support"]
root_source_extensions = [".py", ".pyi"]
allowed_root_source_paths = [
  "tests/__init__.py",
  "tests/ci_test_policy.py",
  "tests/conftest.py",
]
[discovery]
serial_policy = "tests/ci_test_policy.py"
wait_calls = ["QTest.qWait", "time.sleep"]
wall_clock_calls = ["monotonic", "perf_counter", "time.monotonic", "time.perf_counter"]
xdist_environment_name = "PYTEST_XDIST_WORKER"
repository_scratch_name = ".pytest-tmp"
[registries]
debt = "TEST_DEBT.toml"
waivers = "TEST_WAIVERS.toml"
""",
    )
    write(root / "tests/__init__.py", "\n")
    write(root / "tests/conftest.py", "\n")
    write(root / "tools/test_support/__init__.py", "\n")
    write(
        root / "tests/ci_test_policy.py",
        "ISOLATED_TEST_MODULES = frozenset()\nSERIAL_TEST_MODULES = frozenset()\n",
    )
    write(root / "TEST_DEBT.toml", "schema_version = 1\ndebts = []\n")
    write(root / "TEST_WAIVERS.toml", "schema_version = 1\nwaivers = []\n")


__all__ = ["write", "write_fixture"]
