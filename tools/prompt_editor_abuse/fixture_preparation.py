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

"""Prepare requested asynchronous fixtures before measured editor actions."""

from __future__ import annotations

from typing import Any, cast

from tests.real_shell_prompt_editor_harness import (
    PromptFieldHandle,
    RealShellPromptEditorHarness,
)

from .models import PromptAbuseScenario


def prepare_prompt_abuse_fixture_state(
    harness: RealShellPromptEditorHarness,
    field: PromptFieldHandle,
    scenario: PromptAbuseScenario,
) -> None:
    """Wait only for explicitly requested fixture state outside measurements."""

    if "scheduled_lora" not in scenario.fixture_features:
        return
    controller = cast(Any, field.editor)._lora_trigger_word_controller
    harness.wait_until(
        lambda: (
            controller.cached_scheduled_loras(field.editor.toPlainText()) is not None
        )
    )


__all__ = ["prepare_prompt_abuse_fixture_state"]
