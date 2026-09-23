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

"""Enforce focused ownership of mounted scene-context publication."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_scene_facade_owns_identity_and_dependent_refresh() -> None:
    """Keep scene publication sequencing out of the QFluent adapter."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    facade_source = (PROMPT_PRESENTATION_ROOT / "scene_facade.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        'metadata.get("cube_alias")',
        'metadata.get("node_name")',
        'metadata.get("key")',
        "bindings.set_context_identity(",
        "bindings.set_autocomplete_titles(titles)",
        "bindings.refresh_active_autocomplete_session()",
        "bindings.set_queueable_keys(scene_keys)",
    ):
        assert ownership_marker in facade_source
        assert ownership_marker not in widget_source

    assert "self._runtime.core.scene.set_autocomplete_titles(titles)" in widget_source
    assert "self._runtime.core.scene.set_queueable_keys(scene_keys)" in widget_source
