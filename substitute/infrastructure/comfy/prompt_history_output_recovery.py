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

"""Recover final image artifacts from Comfy's authoritative prompt history."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

import requests

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.comfy_image_artifact_parser import (
    parse_comfy_image_artifacts,
)
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageScene,
    FinalImageSource,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.prompt_history_output_recovery")


class PromptHistoryReader(Protocol):
    """Read one prompt's authoritative Comfy history envelope."""

    def read(self, prompt_id: str) -> Mapping[str, object]:
        """Return the history response for ``prompt_id``."""


class FinalImageEventSink(Protocol):
    """Consume transport-neutral final image events."""

    def handle(self, event: FinalImageEvent) -> None:
        """Handle one final image event."""


@dataclass(frozen=True, slots=True)
class ComfyPromptHistoryReader:
    """Fetch prompt history from the configured Comfy server."""

    endpoint: ComfyEndpoint
    timeout_seconds: float = 5.0

    def read(self, prompt_id: str) -> Mapping[str, object]:
        """Fetch and validate one prompt-specific history object."""

        response = requests.get(
            self.endpoint.history_url(prompt_id),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("Comfy history response was not a JSON object.")
        return payload


@dataclass(frozen=True, slots=True)
class PromptHistoryRecoveryContext:
    """Carry stable listener identity into recovered final image events."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    workflow_payload: dict[str, object]
    output_session_id: str | None = None
    scene: FinalImageScene = FinalImageScene()


@dataclass(frozen=True, slots=True)
class PromptHistoryOutputRecovery:
    """Replay declared output artifacts after live or cached execution completes."""

    history_reader: PromptHistoryReader
    context: PromptHistoryRecoveryContext
    output_node_ids: frozenset[str]
    source_resolver: Callable[[str], OutputSourceIdentity]
    final_image_handler: FinalImageEventSink

    def recover(self) -> None:
        """Replay history artifacts through the ordinary final-image owner."""

        payload = self.history_reader.read(self.context.prompt_id)
        entry = payload.get(self.context.prompt_id)
        if not isinstance(entry, Mapping):
            return
        outputs = entry.get("outputs")
        if not isinstance(outputs, Mapping):
            return
        for node_id in sorted(self.output_node_ids):
            output = outputs.get(node_id)
            if output is None:
                continue
            artifacts = parse_comfy_image_artifacts(output)
            if artifacts is None:
                log_warning(
                    _LOGGER,
                    "Ignored malformed image artifacts in Comfy prompt history",
                    workflow_id=self.context.workflow_id,
                    generation_run_id=self.context.generation_run_id,
                    prompt_id=self.context.prompt_id,
                    node_id=node_id,
                )
                continue
            if not artifacts:
                continue
            source = self.source_resolver(node_id)
            self.final_image_handler.handle(
                FinalImageEvent(
                    workflow_id=self.context.workflow_id,
                    generation_run_id=self.context.generation_run_id,
                    prompt_id=self.context.prompt_id,
                    client_id=self.context.client_id,
                    workflow_payload=self.context.workflow_payload,
                    source=FinalImageSource(
                        node_id=source.node_id,
                        source_key=source.source_key,
                        source_label=source.source_label,
                        cube_alias=source.cube_alias,
                    ),
                    artifacts=artifacts,
                    list_index=0,
                    output_session_id=self.context.output_session_id,
                    scene=self.context.scene,
                )
            )


__all__ = [
    "ComfyPromptHistoryReader",
    "PromptHistoryOutputRecovery",
    "PromptHistoryReader",
    "PromptHistoryRecoveryContext",
]
