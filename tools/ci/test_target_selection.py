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

"""Select conservative focused test targets for clearly owned source changes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final
import tomllib


_DEFAULT_POLICY_PATH: Final[PurePosixPath] = PurePosixPath("TEST_TARGET_POLICY.toml")
_TEST_ROOT: Final[PurePosixPath] = PurePosixPath("tests")


@dataclass(frozen=True)
class TestTargetOwner:
    """Map one production ownership root to its focused test target."""

    source_prefix: PurePosixPath
    test_target: PurePosixPath


@dataclass(frozen=True)
class TestTargetPolicy:
    """Describe source roots eligible for targeted local feedback."""

    test_root: PurePosixPath
    owners: tuple[TestTargetOwner, ...]


@dataclass(frozen=True)
class TestTargetSelection:
    """Report either focused targets or the exact reason to run the full suite."""

    targets: tuple[PurePosixPath, ...]
    full_suite_reason: str | None

    @property
    def requires_full_suite(self) -> bool:
        """Return whether this change set must use complete verification."""

        return self.full_suite_reason is not None


def load_test_target_policy(policy_path: Path) -> TestTargetPolicy:
    """Load and validate the source-to-test ownership policy."""

    with policy_path.open("rb") as policy_file:
        payload = tomllib.load(policy_file)
    if payload.get("schema_version") != 1:
        raise ValueError("TEST_TARGET_POLICY.toml must use schema_version = 1.")

    scope = _mapping(payload.get("scope"), "scope")
    test_root = _relative_path(scope.get("test_root"), "scope.test_root")
    if test_root != _TEST_ROOT:
        raise ValueError("scope.test_root must be tests.")

    raw_owners = payload.get("owners")
    if not isinstance(raw_owners, list) or not raw_owners:
        raise ValueError("owners must contain at least one source-to-test mapping.")

    owners = tuple(
        TestTargetOwner(
            source_prefix=_relative_path(
                _mapping(entry, "owners entry").get("source_prefix"),
                "owners.source_prefix",
            ),
            test_target=_relative_path(
                _mapping(entry, "owners entry").get("test_target"),
                "owners.test_target",
            ),
        )
        for entry in raw_owners
    )
    _validate_owners(owners, test_root)
    return TestTargetPolicy(test_root=test_root, owners=owners)


def select_test_targets(
    project_root: Path,
    changed_paths: tuple[str, ...],
    *,
    policy_path: Path | None = None,
) -> TestTargetSelection:
    """Select owner targets or require full verification for an unsafe change set."""

    if not changed_paths:
        return TestTargetSelection((), "no changed paths were supplied")

    policy = load_test_target_policy(policy_path or project_root / _DEFAULT_POLICY_PATH)
    targets: set[PurePosixPath] = set()
    for raw_path in changed_paths:
        changed_path = _changed_path(raw_path)
        if changed_path is None:
            return TestTargetSelection((), f"invalid changed path: {raw_path}")
        if changed_path == _DEFAULT_POLICY_PATH:
            return TestTargetSelection((), "the target-selection policy changed")
        if _is_test_module_path(changed_path, policy.test_root):
            targets.add(changed_path)
            continue
        owner = _owner_for(changed_path, policy.owners)
        if owner is None:
            return TestTargetSelection(
                (),
                f"no focused owner target is registered for {changed_path}",
            )
        target_path = project_root / owner.test_target
        if not target_path.exists():
            return TestTargetSelection(
                (),
                f"registered target does not exist: {owner.test_target}",
            )
        targets.add(owner.test_target)
    return TestTargetSelection(tuple(sorted(targets)), None)


def main() -> int:
    """Print the conservative focused target selection for changed paths."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("changed_paths", nargs="+", help="Repository-relative paths")
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(_DEFAULT_POLICY_PATH),
        help="Path to the target-selection policy relative to the repository root.",
    )
    arguments = parser.parse_args()
    project_root = Path.cwd()
    selection = select_test_targets(
        project_root,
        tuple(arguments.changed_paths),
        policy_path=project_root / arguments.policy,
    )
    if selection.requires_full_suite:
        print(f"FULL_SUITE: {selection.full_suite_reason}")
        return 0
    print("FOCUSED_TARGETS:")
    for target in selection.targets:
        print(target.as_posix())
    return 0


def _mapping(value: object, label: str) -> dict[str, object]:
    """Return one TOML mapping or raise a precise policy error."""

    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table.")
    return value


def _relative_path(value: object, label: str) -> PurePosixPath:
    """Return one normalized, repository-relative POSIX path."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path string.")
    normalized = PurePosixPath(value.replace("\\", "/"))
    if (
        normalized.is_absolute()
        or ".." in normalized.parts
        or any(":" in part for part in normalized.parts)
    ):
        raise ValueError(f"{label} must be a repository-relative path.")
    return normalized


def _validate_owners(
    owners: tuple[TestTargetOwner, ...],
    test_root: PurePosixPath,
) -> None:
    """Reject duplicate or out-of-scope owner registrations."""

    source_prefixes = [owner.source_prefix for owner in owners]
    if len(source_prefixes) != len(set(source_prefixes)):
        raise ValueError("owners.source_prefix entries must be unique.")
    for owner in owners:
        if owner.source_prefix.parts[0] != "substitute":
            raise ValueError("owners.source_prefix must begin with substitute.")
        if owner.test_target.parts[:1] != test_root.parts:
            raise ValueError("owners.test_target must be inside tests.")


def _changed_path(raw_path: str) -> PurePosixPath | None:
    """Normalize one changed repository path without accepting traversal."""

    try:
        return _relative_path(raw_path, "changed path")
    except ValueError:
        return None


def _is_test_module_path(path: PurePosixPath, test_root: PurePosixPath) -> bool:
    """Return whether a path is one directly runnable focused test module."""

    return (
        path.parts[:1] == test_root.parts
        and path.suffix == ".py"
        and path.name.startswith("test_")
    )


def _owner_for(
    path: PurePosixPath,
    owners: tuple[TestTargetOwner, ...],
) -> TestTargetOwner | None:
    """Return the longest registered source owner containing a changed path."""

    matching = tuple(
        owner
        for owner in owners
        if path.parts[: len(owner.source_prefix.parts)] == owner.source_prefix.parts
    )
    if not matching:
        return None
    return max(matching, key=lambda owner: len(owner.source_prefix.parts))


if __name__ == "__main__":
    raise SystemExit(main())
