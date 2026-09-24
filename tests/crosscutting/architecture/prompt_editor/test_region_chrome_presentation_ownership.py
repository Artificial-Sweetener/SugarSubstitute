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

"""Enforce focused ownership of regional chrome publication."""

from __future__ import annotations

from .inventory import PROJECT_ROOT, PROMPT_PRESENTATION_ROOT


def test_surface_delegates_regional_chrome_publication_to_focused_owner() -> None:
    """Keep regional interaction effects outside the mounted surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    owner_source = (projection_root / "region_chrome_presentation.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (projection_root / "surface_presentation_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "self._region_chrome =" not in surface_source
    assert "self._region_chrome.set_hovered_region(" not in surface_source
    assert "self._region_chrome.set_editing_region(" not in surface_source
    assert "self._region_chrome.set_editing_region_draft(" not in surface_source
    assert "class PromptRegionChromePresentationOwner" in owner_source
    assert "self._publish_render_frame()" in owner_source
    assert "self._request_update()" in owner_source
    assert "region_chrome = PromptRegionChromePresentationOwner(" in runtime_source
    assert "region_chrome=region_chrome" in runtime_source


def test_prompt_editor_diagnostics_follow_regional_chrome_owner() -> None:
    """Keep qualification probes aligned with the production owner boundary."""

    diagnostic_paths = (
        PROJECT_ROOT
        / "tests"
        / "support"
        / "prompt_editor"
        / "real_shell"
        / "projection_state.py",
        PROJECT_ROOT / "tools" / "prompt_editor_abuse" / "action_counter_probe.py",
        PROJECT_ROOT / "tools" / "prompt_editor_abuse" / "owner_state.py",
    )

    for path in diagnostic_paths:
        source = path.read_text(encoding="utf-8")
        assert 'getattr(surface, "_region_chrome", None)' not in source
        assert '"_presentation_runtime"' in source
        assert '"region_chrome"' in source
