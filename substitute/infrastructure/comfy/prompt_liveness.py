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

"""Verify prompt liveness after an idle Comfy websocket interval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import requests

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.queue_payload import queue_prompt_ids
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.prompt_liveness")

PromptLivenessState = Literal[
    "active",
    "succeeded",
    "failed",
    "missing",
    "unavailable",
]


@dataclass(frozen=True, slots=True)
class PromptLivenessObservation:
    """Describe Comfy's authoritative state for one queued prompt."""

    state: PromptLivenessState
    detail: str


class PromptLivenessProbe(Protocol):
    """Inspect Comfy HTTP state without owning listener retry policy."""

    def observe(self, prompt_id: str) -> PromptLivenessObservation:
        """Return the current authoritative state for ``prompt_id``."""


@dataclass(frozen=True, slots=True)
class ComfyPromptLivenessProbe:
    """Resolve prompt state through Comfy's queue and history endpoints."""

    endpoint: ComfyEndpoint
    timeout_seconds: float = 5.0

    def observe(self, prompt_id: str) -> PromptLivenessObservation:
        """Return queue activity or terminal history for one prompt."""

        try:
            queue_payload = self._read_json(self.endpoint.queue_url())
        except Exception as error:
            log_warning(
                _LOGGER,
                "Comfy prompt liveness queue probe failed",
                prompt_id=prompt_id,
                endpoint=self.endpoint.queue_url(),
                error=error,
            )
            return PromptLivenessObservation(
                state="unavailable",
                detail=f"queue probe failed: {error}",
            )

        if prompt_id in queue_prompt_ids(queue_payload):
            return PromptLivenessObservation(
                state="active",
                detail="prompt remains present in Comfy's queue",
            )

        try:
            history_payload = self._read_json(self.endpoint.history_url(prompt_id))
        except Exception as error:
            log_warning(
                _LOGGER,
                "Comfy prompt liveness history probe failed",
                prompt_id=prompt_id,
                endpoint=self.endpoint.history_url(prompt_id),
                error=error,
            )
            return PromptLivenessObservation(
                state="unavailable",
                detail=f"history probe failed: {error}",
            )

        history_entry = history_payload.get(prompt_id)
        if not isinstance(history_entry, dict):
            return PromptLivenessObservation(
                state="missing",
                detail="prompt is absent from both Comfy queue and history",
            )
        status = history_entry.get("status")
        status_payload = status if isinstance(status, dict) else {}
        status_text = str(status_payload.get("status_str", "")).casefold()
        completed = status_payload.get("completed") is True
        if status_text in {"error", "failed"}:
            return PromptLivenessObservation(
                state="failed",
                detail=f"Comfy history reported terminal status {status_text!r}",
            )
        if completed or status_text in {"success", "completed"}:
            return PromptLivenessObservation(
                state="succeeded",
                detail="Comfy history reported successful completion",
            )
        return PromptLivenessObservation(
            state="missing",
            detail=f"Comfy history has no terminal state (status={status_text!r})",
        )

    def _read_json(self, url: str) -> dict[str, object]:
        """Fetch and validate one Comfy JSON object response."""

        response = requests.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Comfy response was not a JSON object.")
        return payload


__all__ = [
    "ComfyPromptLivenessProbe",
    "PromptLivenessObservation",
    "PromptLivenessProbe",
    "PromptLivenessState",
]
