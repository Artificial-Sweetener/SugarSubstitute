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

"""Enforce focused projection history ownership."""

from __future__ import annotations

from .inventory import PROJECT_ROOT, PROMPT_PRESENTATION_ROOT


def test_projection_history_bypasses_surface_protocol_routing() -> None:
    """Keep payload, clipboard cursor, and availability routing in one owner."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    history_source = (projection_root / "history_owner.py").read_text(encoding="utf-8")
    runtime_factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "editing_runtime_factory.py"
    ).read_text(encoding="utf-8")
    surface_factory_source = (
        PROJECT_ROOT
        / "tests"
        / "support"
        / "prompt_editor"
        / "projection_surface_factory.py"
    ).read_text(encoding="utf-8")

    removed_surface_methods = (
        "can_undo",
        "can_redo",
        "clipboard_history_actions",
        "set_clipboard_history_cursor_state",
        "undo_restoration_payload",
        "undo_comparison_payload",
        "emit_undo_available_changed",
        "emit_redo_available_changed",
    )
    for method_name in removed_surface_methods:
        assert f"def {method_name}(" not in surface_source
    assert "class PromptProjectionHistoryOwner" in history_source
    assert "undo_payload_provider=surface.history" in runtime_factory_source
    assert "availability_signal_sink=surface.history" in runtime_factory_source
    assert "cursor_sink=surface.history" in runtime_factory_source
    assert "undo_payload_provider=surface.history" in surface_factory_source
    assert "availability_signal_sink=surface.history" in surface_factory_source
