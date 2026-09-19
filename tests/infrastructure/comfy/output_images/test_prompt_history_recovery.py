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

"""Prove terminal Comfy history recovers final artifacts without disabling cache."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.infrastructure.comfy.final_image_event import FinalImageEvent
from substitute.infrastructure.comfy.prompt_history_output_recovery import (
    PromptHistoryOutputRecovery,
    PromptHistoryRecoveryContext,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)


class _HistoryReader:
    """Return one configured Comfy history payload."""

    def __init__(self, payload: Mapping[str, object]) -> None:
        """Store the payload returned for every prompt read."""

        self.payload = payload
        self.prompt_ids: list[str] = []

    def read(self, prompt_id: str) -> Mapping[str, object]:
        """Record the prompt and return its history payload."""

        self.prompt_ids.append(prompt_id)
        return self.payload


class _FinalHandler:
    """Record recovered neutral final-image events."""

    def __init__(self) -> None:
        """Initialize recorded events."""

        self.events: list[FinalImageEvent] = []

    def handle(self, event: FinalImageEvent) -> None:
        """Record one recovered event."""

        self.events.append(event)


def test_history_recovery_replays_only_declared_output_nodes() -> None:
    """Recover every cached batch artifact through declared source identity."""

    reader = _HistoryReader(
        {
            "prompt-2": {
                "outputs": {
                    "cube-output": {
                        "images": [
                            {
                                "filename": "first.png",
                                "subfolder": "cached",
                                "type": "temp",
                            },
                            {
                                "filename": "second.png",
                                "subfolder": "cached",
                                "type": "temp",
                            },
                        ]
                    },
                    "unrelated": {
                        "images": [
                            {
                                "filename": "ignored.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    },
                }
            }
        }
    )
    final_handler = _FinalHandler()
    recovery = PromptHistoryOutputRecovery(
        history_reader=reader,
        context=PromptHistoryRecoveryContext(
            workflow_id="workflow-1",
            generation_run_id="run-2",
            prompt_id="prompt-2",
            client_id="client-3",
            workflow_payload={"cube-output": {"class_type": "SugarCubes.CubeOutput"}},
            output_session_id="session-4",
        ),
        output_node_ids=frozenset({"cube-output"}),
        source_resolver=lambda node_id: OutputSourceIdentity(
            node_id=node_id,
            source_key="source-key",
            source_label="Diffusion Upscale",
            cube_alias="Diffusion Upscale",
        ),
        final_image_handler=final_handler,
    )

    recovery.recover()

    assert reader.prompt_ids == ["prompt-2"]
    assert len(final_handler.events) == 1
    event = final_handler.events[0]
    assert event.prompt_id == "prompt-2"
    assert event.generation_run_id == "run-2"
    assert event.source.node_id == "cube-output"
    assert [artifact.filename for artifact in event.artifacts] == [
        "first.png",
        "second.png",
    ]
    assert event.output_session_id == "session-4"


def test_history_recovery_treats_absent_prompt_as_no_outputs() -> None:
    """A missing history entry must not fabricate or misroute an old result."""

    final_handler = _FinalHandler()
    recovery = PromptHistoryOutputRecovery(
        history_reader=_HistoryReader({"another-prompt": {"outputs": {}}}),
        context=PromptHistoryRecoveryContext(
            workflow_id="workflow-1",
            generation_run_id="run-2",
            prompt_id="prompt-2",
            client_id="client-3",
            workflow_payload={},
        ),
        output_node_ids=frozenset({"cube-output"}),
        source_resolver=lambda node_id: OutputSourceIdentity(
            node_id=node_id,
            source_key=node_id,
            source_label=node_id,
            cube_alias=node_id,
        ),
        final_image_handler=final_handler,
    )

    recovery.recover()

    assert final_handler.events == []
