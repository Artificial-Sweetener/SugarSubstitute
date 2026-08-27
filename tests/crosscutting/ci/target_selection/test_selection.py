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

"""Test conservative source-change target selection."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from tools.ci.test_target_selection import select_test_targets


def test_selects_the_registered_owner_target_for_one_application_change() -> None:
    """Return the focused application owner for a production-owned change."""

    selection = select_test_targets(
        Path.cwd(),
        ("substitute/application/cubes/cube_load_service.py",),
    )

    assert selection.targets == (PurePosixPath("tests/application"),)
    assert selection.full_suite_reason is None


def test_prefers_the_more_specific_bootstrap_owner() -> None:
    """Choose the most specific registered source prefix when roots overlap."""

    selection = select_test_targets(
        Path.cwd(),
        ("substitute/app/bootstrap/launch_splash.py",),
    )

    assert selection.targets == (PurePosixPath("tests/app/bootstrap"),)
    assert selection.full_suite_reason is None


def test_keeps_direct_test_edits_as_their_precise_focused_target() -> None:
    """Return a changed test path directly instead of widening its owner suite."""

    selection = select_test_targets(
        Path.cwd(),
        ("tests/application/cubes/load_service/test_service.py",),
    )

    assert selection.targets == (
        PurePosixPath("tests/application/cubes/load_service/test_service.py"),
    )
    assert selection.full_suite_reason is None


def test_requires_the_full_suite_for_shared_or_unknown_changes() -> None:
    """Fail closed when a change has no exact registered test owner."""

    selection = select_test_targets(
        Path.cwd(),
        ("sugarsubstitute_shared/presentation/localization/bindings.py",),
    )

    assert selection.targets == ()
    assert selection.full_suite_reason == (
        "no focused owner target is registered for "
        "sugarsubstitute_shared/presentation/localization/bindings.py"
    )


def test_requires_the_full_suite_for_shared_test_support() -> None:
    """Prevent support or fixture edits from claiming a narrow test target."""

    selection = select_test_targets(
        Path.cwd(),
        ("tests/support/qt/lifecycle.py",),
    )

    assert selection.targets == ()
    assert selection.full_suite_reason == (
        "no focused owner target is registered for tests/support/qt/lifecycle.py"
    )


def test_requires_the_full_suite_for_a_mixed_change_set() -> None:
    """Let one unmapped path widen an otherwise owner-local change set."""

    selection = select_test_targets(
        Path.cwd(),
        (
            "substitute/application/cubes/cube_load_service.py",
            "pytest.ini",
        ),
    )

    assert selection.targets == ()
    assert selection.full_suite_reason == (
        "no focused owner target is registered for pytest.ini"
    )


def test_rejects_path_traversal_in_change_input() -> None:
    """Fail closed instead of allowing a caller to escape the repository root."""

    selection = select_test_targets(Path.cwd(), ("tests/../outside.py",))

    assert selection.targets == ()
    assert selection.full_suite_reason == "invalid changed path: tests/../outside.py"
