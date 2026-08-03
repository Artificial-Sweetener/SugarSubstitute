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

"""Characterize long-path failures reported by external processes."""

from __future__ import annotations

from pathlib import Path

import pytest

from sugarsubstitute_shared.external_path_failure import (
    ExternalLongPathCompatibilityError,
    external_long_path_error,
)


@pytest.mark.platforms("windows")
def test_classifier_recognizes_errno_two_with_embedded_long_path() -> None:
    """Pip's missing-file diagnostic should expose its actual overlong output path."""

    failing_path = (
        "E:\\Documents\\Everything\\Artificial Sweetener\\runtime\\installer-temp"
        "\\managed-comfy\\401c2092-bb13-4f3b-a377-997f1fab4ccd\\temp"
        "\\pip-ephem-wheel-cache-pmo9xg0b\\wheels\\59\\1d\\00"
        "\\729d4b9dcecc8342dac49bcf6ab1415de9f48be12e466feb73"
        "\\tmpzx280yzl\\.tmp-by7a27ea"
        "\\sugarcubes-0.11.0-py3-none-any.whl"
    )
    detail = f"error: [Errno 2] No such file or directory: '{failing_path}'"

    classified = external_long_path_error(
        component="pip",
        path=Path(r"E:\Documents\Everything\Artificial Sweetener\comfyui\.venv"),
        detail=detail,
    )

    assert isinstance(classified, ExternalLongPathCompatibilityError)
    assert classified.path == Path(failing_path)
    assert classified.component == "pip"


@pytest.mark.platforms("windows")
def test_classifier_recognizes_overlong_unc_path() -> None:
    """Network installations should retain pip's failing UNC wheel path."""

    failing_path = (
        r"\\server\managed-install\temp\pip-ephem-wheel-cache\wheels"
        + "\\deep-wheel-segment" * 12
        + r"\sugarcubes-0.11.0-py3-none-any.whl"
    )

    classified = external_long_path_error(
        component="pip",
        path=Path(r"\\server\managed-install\comfyui"),
        detail=f"[Errno 2] No such file or directory: '{failing_path}'",
    )

    assert isinstance(classified, ExternalLongPathCompatibilityError)
    assert classified.path == Path(failing_path)
