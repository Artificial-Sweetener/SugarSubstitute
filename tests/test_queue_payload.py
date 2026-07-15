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

"""Tests for authoritative Comfy queue payload normalization."""

from __future__ import annotations

from substitute.infrastructure.comfy.queue_payload import (
    extract_prompt_ids,
    queue_prompt_ids,
)


def test_extract_prompt_ids_supports_native_and_facade_queue_shapes() -> None:
    """Priority-first native tuples and facade shapes should normalize equally."""

    assert extract_prompt_ids(
        [
            [0.0, "native-prompt", {}, {}],
            ["facade-prompt", 1],
            {"prompt_id": "mapping-prompt"},
        ]
    ) == ("native-prompt", "facade-prompt", "mapping-prompt")


def test_queue_prompt_ids_combines_running_and_pending_entries() -> None:
    """Queue membership should include both execution states."""

    assert queue_prompt_ids(
        {
            "queue_running": [[0.0, "running"]],
            "queue_pending": [{"prompt_id": "pending"}],
        }
    ) == {"running", "pending"}
