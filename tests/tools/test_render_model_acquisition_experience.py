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

"""Verify deterministic production model-acquisition render evidence."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtGui import QImage

from tools.render_model_acquisition_experience import run_headless_qualification


def test_headless_model_acquisition_matrix_uses_production_surfaces(
    tmp_path: Path,
) -> None:
    """Every material interaction state should produce readable evidence."""

    evidence = run_headless_qualification(artifact_root=tmp_path)

    assert evidence["result"] == "passed"
    assert evidence["headless"] is True
    states = {
        cast(str, state["state"]): state
        for state in cast(list[dict[str, object]], evidence["states"])
    }
    assert set(states) == {
        "multi-model-ready",
        "api-key-required",
        "api-key-satisfied",
        "unavailable-unsafe-model",
        "download-progress",
        "download-failure",
    }
    assert states["multi-model-ready"]["cards"] == 4
    assert states["multi-model-ready"]["download_enabled"] is True
    assert states["api-key-required"]["api_key_visible"] is True
    assert states["api-key-required"]["download_enabled"] is False
    assert states["api-key-satisfied"]["download_enabled"] is True
    assert states["unavailable-unsafe-model"]["download_enabled"] is False
    assert states["download-progress"]["progress_per_mille"] == 500
    for state in states.values():
        screenshot = Path(cast(str, state["screenshot"]))
        assert screenshot.is_file()
        image = QImage(str(screenshot))
        assert not image.isNull()
        assert image.width() == 1280
        assert image.height() == 800
    completion = cast(dict[str, object], evidence["completion"])
    assert completion["distinct_surface"] is False
    assert cast(dict[str, int], evidence["side_effects"]) == {
        "network_requests": 0,
        "downloads": 0,
        "credentials_persisted": 0,
        "external_urls_opened": 0,
    }
