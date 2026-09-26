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

"""Prove runtime timers cannot queue callbacks without a Qt lifetime owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.architecture_governance.model import ArchitecturePolicy
from tools.architecture_governance.qt_lifetime_policy import (
    validate_qt_lifetime_policy,
)


def _fixture_policy() -> ArchitecturePolicy:
    """Return a minimal policy governing synthetic runtime source."""

    return ArchitecturePolicy(
        soft_lines=350,
        hard_lines=500,
        source_roots=(Path("substitute"),),
        source_files=(),
        source_extensions=frozenset({".py"}),
        excluded_paths=frozenset(),
        debt_registry=Path("governance/architecture/debt.toml"),
        waiver_registry=Path("governance/architecture/waivers.toml"),
    )


@pytest.mark.parametrize(
    "source",
    [
        (
            "from PySide6.QtCore import QTimer\n"
            "def queue(callback):\n    QTimer.singleShot(0, callback)\n"
        ),
        (
            "from PySide6.QtCore import QTimer as Timer\n"
            "def queue(callback):\n    Timer.singleShot(0, callback)\n"
        ),
        (
            "from PySide6 import QtCore\n"
            "def queue(callback):\n    QtCore.QTimer.singleShot(0, callback)\n"
        ),
        (
            "class TimerPort:\n"
            "    def singleShot(self, delay, callback): ...\n"
            "def queue(timer, callback):\n    timer.singleShot(0, callback)\n"
        ),
    ],
)
def test_context_free_single_shots_are_rejected(
    tmp_path: Path,
    source: str,
) -> None:
    """Every supported QTimer spelling must require an explicit context."""

    runtime = tmp_path / "substitute" / "feature.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(source, encoding="utf-8")

    diagnostics = validate_qt_lifetime_policy(tmp_path, _fixture_policy())

    assert [diagnostic.rule for diagnostic in diagnostics] == ["QT_LIFETIME001"]


def test_context_bound_single_shot_is_accepted(tmp_path: Path) -> None:
    """The QObject-context overload owns callback cancellation safely."""

    runtime = tmp_path / "substitute" / "feature.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        "from PySide6.QtCore import QTimer\n"
        "def queue(owner, callback):\n"
        "    QTimer.singleShot(0, owner, callback)\n",
        encoding="utf-8",
    )

    assert validate_qt_lifetime_policy(tmp_path, _fixture_policy()) == []


def test_raw_qtimer_scheduler_reference_is_rejected(tmp_path: Path) -> None:
    """A raw Qt scheduler must not escape without a bound lifetime owner."""

    runtime = tmp_path / "substitute" / "feature.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        "from PySide6.QtCore import QTimer\n"
        "def connect(single_shot): ...\n"
        "connect(QTimer.singleShot)\n",
        encoding="utf-8",
    )

    diagnostics = validate_qt_lifetime_policy(tmp_path, _fixture_policy())

    assert [diagnostic.rule for diagnostic in diagnostics] == ["QT_LIFETIME002"]
