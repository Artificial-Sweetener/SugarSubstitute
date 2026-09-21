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

"""Enforce single ownership of prompt-editor external text input."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_and_shell_delegate_external_text_policy_to_interaction_owner() -> None:
    """Keep MIME policy, command identity, and drop acceptance out of both hosts."""
    owner_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "external_text_input.py"
    ).read_text(encoding="utf-8")
    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )
    input_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_input_runtime.py"
    ).read_text(encoding="utf-8")
    shell_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")

    assert "mime_data_has_prompt_plain_text" in owner_source
    assert "prompt_plain_text_from_mime_data" in owner_source
    assert '"drop_plain_text"' in owner_source
    assert '"mime_plain_text"' in owner_source
    assert "PromptExternalTextInputOwner(" in input_runtime_source
    assert "PromptExternalTextInputOwner(" not in surface_source
    assert "PromptExternalTextInputOwner(" in shell_source
    for host_source in (surface_source, shell_source, input_runtime_source):
        assert "mime_data_has_prompt_plain_text" not in host_source
        assert "prompt_plain_text_from_mime_data" not in host_source
        assert "_accept_or_ignore_prompt_mime_event" not in host_source
        assert "_drop_prompt_mime_text" not in host_source
        assert "_insert_dropped_prompt_text" not in host_source
