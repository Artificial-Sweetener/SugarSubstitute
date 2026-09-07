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

"""Verify installer visual-resource resolution in every application layout."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from sugarsubstitute_shared.presentation import installer_resources


def test_installed_app_resolves_payload_wordmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installed onboarding must resolve the wordmark shipped in the app ZIP."""

    app_root = tmp_path / "app"
    module_path = (
        app_root / "sugarsubstitute_shared" / "presentation" / "installer_resources.py"
    )
    wordmark_path = (
        app_root / installer_resources.INSTALLER_WORDMARK_RUNTIME_RELATIVE_PATH
    )
    wordmark_path.parent.mkdir(parents=True)
    wordmark_path.write_text("<svg/>\n", encoding="utf-8")
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(installer_resources, "__file__", str(module_path))
    monkeypatch.chdir(tmp_path)

    assert installer_resources.installer_wordmark_path() == wordmark_path
