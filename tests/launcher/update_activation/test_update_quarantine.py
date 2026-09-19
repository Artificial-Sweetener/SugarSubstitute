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

"""Tests for exact failed-target update quarantine."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.update_quarantine import UpdateQuarantine


def test_quarantine_is_bound_to_version_and_digest(tmp_path: Path) -> None:
    """A rebuilt target may retry while the exact failed bytes remain blocked."""

    quarantine = UpdateQuarantine(tmp_path)
    quarantine.add(version="0.23.0", sha256="1" * 64, reason="readiness_failed")

    assert quarantine.contains(version="0.23.0", sha256="1" * 64)
    assert not quarantine.contains(version="0.23.0", sha256="2" * 64)
    assert not quarantine.contains(version="0.23.1", sha256="1" * 64)


def test_quarantine_can_clear_only_the_accepted_target(tmp_path: Path) -> None:
    """Acceptance should retain unrelated failure evidence."""

    quarantine = UpdateQuarantine(tmp_path)
    quarantine.add(version="0.23.0", sha256="1" * 64, reason="failed")
    quarantine.add(version="0.23.1", sha256="2" * 64, reason="failed")

    quarantine.remove(version="0.23.0", sha256="1" * 64)

    assert not quarantine.contains(version="0.23.0", sha256="1" * 64)
    assert quarantine.contains(version="0.23.1", sha256="2" * 64)


def test_interrupted_activation_remains_retryable(tmp_path: Path) -> None:
    """Do not suppress valid bytes merely because startup was interrupted."""

    quarantine = UpdateQuarantine(tmp_path)
    quarantine.add(
        version="0.23.0",
        sha256="1" * 64,
        reason="interrupted_activation",
    )

    assert not quarantine.contains(version="0.23.0", sha256="1" * 64)
