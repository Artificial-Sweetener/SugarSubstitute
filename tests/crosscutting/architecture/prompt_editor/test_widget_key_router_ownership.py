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

"""Enforce focused ownership of prompt-editor keyboard routing."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_key_router_owns_feature_and_projection_precedence() -> None:
    """Keep keyboard policy out of the mounted QFluent adapter."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    router_source = (PROMPT_PRESENTATION_ROOT / "key_router.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "bindings.handle_feature_key_press(event)",
        "bindings.handle_surface_key_press(event)",
        "bindings.publish_emphasis_shortcut()",
        "bindings.clear_autocomplete_for_non_text_key()",
        "bindings.publish_post_key_press(event)",
        "bindings.handle_feature_key_release(event)",
        "bindings.handle_surface_key_release(event)",
    ):
        assert ownership_marker in router_source
        assert ownership_marker not in widget_source

    assert "self._runtime.core.key_router.handle_key_press(event)" in widget_source
    assert "self._runtime.core.key_router.handle_key_release(event)" in widget_source


def test_key_router_owns_post_key_classification() -> None:
    """Keep emphasis and non-text key classification beside routing policy."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    router_source = (PROMPT_PRESENTATION_ROOT / "key_router.py").read_text(
        encoding="utf-8"
    )

    for helper in (
        "_emphasis_shortcut_should_mute_autocomplete",
        "_accepted_key_should_skip_autocomplete_post_refresh",
    ):
        assert f"def {helper}(" in router_source
        assert f"def {helper}(" not in widget_source
