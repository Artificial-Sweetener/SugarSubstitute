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

"""Enforce direct LoRA viewport feature ownership."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_lora_feature_delegate_owns_tooltip_and_context_publication() -> None:
    """Keep LoRA feature routing out of the mounted projection surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    feature_source = (projection_root / "lora_surface_features.py").read_text(
        encoding="utf-8"
    )
    mouse_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "mouse_selection_controller.py"
    ).read_text(encoding="utf-8")

    assert "def _install_lora_tooltip_filter(" not in surface_source
    assert "def _lora_tooltip_for_hover_event(" not in surface_source
    assert "def _request_lora_context_menu(" not in surface_source
    assert "def _emit_lora_context_menu_request(" not in surface_source
    assert "publish_context_menu: Callable" in feature_source
    assert "self._publish_context_menu(token, global_pos)" in feature_source
    assert "request_lora_context_menu: Callable" in mouse_source
    assert "host._request_lora_context_menu(" not in mouse_source
