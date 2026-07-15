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

"""Verify the external Comfy automation fixture helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from tests.onboarding_automation import external_comfy_fixture


def test_reset_external_comfy_root_recreates_empty_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reset should delete existing contents and recreate an empty fixture root."""

    fixture = external_comfy_fixture.ExternalComfyFixture(
        workspace_root=tmp_path / "external",
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
    )
    monkeypatch.setattr(
        external_comfy_fixture,
        "build_external_fixture",
        lambda: fixture,
    )
    fixture.workspace_root.mkdir(parents=True)
    (fixture.workspace_root / "old.txt").write_text("stale", encoding="utf-8")

    result = external_comfy_fixture.reset_external_comfy_root()

    assert result == fixture.workspace_root
    assert fixture.workspace_root.exists() is True
    assert list(fixture.workspace_root.iterdir()) == []
