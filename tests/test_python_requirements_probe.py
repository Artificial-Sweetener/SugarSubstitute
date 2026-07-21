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

"""Tests for target-Python requirement satisfaction probes."""

from __future__ import annotations

from pathlib import Path
import sys

from substitute.infrastructure.comfy.python_requirements_probe import (
    PythonRequirementsProbe,
)


def test_probe_reports_satisfied_and_missing_requirements(tmp_path: Path) -> None:
    """The target interpreter should own version and marker evaluation."""

    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "pip>=1\n"
        "definitely-missing-sugarsubstitute-fixture==9876\n"
        'ignored-on-this-python==1; python_version < "2"\n',
        encoding="utf-8",
    )

    assessment = PythonRequirementsProbe().assess(
        requirements_path=requirements,
        python_executable=Path(sys.executable),
        workspace=tmp_path,
    )

    assert assessment.satisfied is False
    assert len(assessment.issues) == 1
    assert (
        "definitely-missing-sugarsubstitute-fixture" in assessment.issues[0].requirement
    )
    assert assessment.issues[0].reason == "missing"


def test_probe_fails_closed_for_unresolved_include_directives(tmp_path: Path) -> None:
    """Unsupported requirement-file composition should be explicit evidence."""

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("-r nested.txt\n", encoding="utf-8")

    assessment = PythonRequirementsProbe().assess(
        requirements_path=requirements,
        python_executable=Path(sys.executable),
        workspace=tmp_path,
    )

    assert assessment.satisfied is False
    assert assessment.issues[0].reason == "unsupported_directive"
