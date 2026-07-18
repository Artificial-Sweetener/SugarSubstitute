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

"""Define the typed graph contract used for prompt-role analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from .models import PromptRole


@dataclass(frozen=True, slots=True, order=True)
class PromptFieldLocator:
    """Identify one editable field within an editor graph section."""

    node_name: str
    field_key: str


@dataclass(frozen=True, slots=True)
class PromptGraphField:
    """Describe one editable string field that may own prompt behavior."""

    locator: PromptFieldLocator
    node_title: str
    label: str
    multiline: bool


@dataclass(frozen=True, slots=True)
class PromptGraphSource:
    """Identify one typed output connected to a node input."""

    node_name: str
    output_slot: int


@dataclass(frozen=True, slots=True)
class PromptGraphInput:
    """Describe one typed input and either its link or editable field owner."""

    name: str
    type_name: str
    source: PromptGraphSource | None = None
    field: PromptGraphField | None = None


@dataclass(frozen=True, slots=True)
class PromptGraphOutput:
    """Describe one typed output slot."""

    slot: int
    name: str
    type_name: str


@dataclass(frozen=True, slots=True)
class PromptGraphNode:
    """Describe the graph-facing prompt semantics of one editor node."""

    name: str
    title: str
    inputs: tuple[PromptGraphInput, ...]
    outputs: tuple[PromptGraphOutput, ...]
    fields: tuple[PromptGraphField, ...]

    def output(self, slot: int) -> PromptGraphOutput | None:
        """Return output metadata for one slot when declared."""

        return next((output for output in self.outputs if output.slot == slot), None)


@dataclass(frozen=True, slots=True)
class PromptSemanticGraph:
    """Carry one isolated cube or direct-workflow graph for analysis."""

    nodes: Mapping[str, PromptGraphNode]


class PromptEvidenceKind(StrEnum):
    """Enumerate explainable facts supporting a prompt-role decision."""

    AUTHORED_FIELD_ROLE = "authored_field_role"
    AUTHORED_NODE_ROLE = "authored_node_role"
    MULTILINE_STRING = "multiline_string"
    PROMPT_NAMING = "prompt_naming"
    SEMANTIC_SINK = "semantic_sink"
    CONDITIONING_FLOW = "conditioning_flow"
    TEXT_ENCODER_INTERFACE = "text_encoder_interface"
    SHARED_MODEL_LINEAGE = "shared_model_lineage"


@dataclass(frozen=True, slots=True)
class PromptEvidence:
    """Record one inspectable fact used by prompt-role inference."""

    kind: PromptEvidenceKind
    detail: str


@dataclass(frozen=True, slots=True, order=True)
class PromptSinkLocator:
    """Identify the typed conditioning input that established prompt polarity."""

    node_name: str
    input_name: str


@dataclass(frozen=True, slots=True)
class PromptRoleDetection:
    """Assign one unambiguous prompt role to an editable field."""

    locator: PromptFieldLocator
    role: PromptRole
    evidence: tuple[PromptEvidence, ...]
    semantic_sinks: tuple[PromptSinkLocator, ...] = ()


class PromptAmbiguityReason(StrEnum):
    """Enumerate conservative reasons for withholding prompt behavior."""

    CONFLICTING_ROLES = "conflicting_roles"
    INDETERMINATE_FIELD = "indeterminate_field"
    MIXED_NODE_ROLES = "mixed_node_roles"


@dataclass(frozen=True, slots=True)
class PromptRoleAmbiguity:
    """Describe fields intentionally left as ordinary strings."""

    locators: tuple[PromptFieldLocator, ...]
    reason: PromptAmbiguityReason
    detail: str


@dataclass(frozen=True, slots=True)
class PromptGraphContext:
    """Group prompt fields whose roles converge at one semantic graph anchor."""

    anchor_node_name: str
    positive_fields: tuple[PromptFieldLocator, ...]
    negative_fields: tuple[PromptFieldLocator, ...]

    @property
    def field_locators(self) -> tuple[PromptFieldLocator, ...]:
        """Return positive then negative field owners for exact-pair ordering."""

        return self.positive_fields + self.negative_fields


@dataclass(frozen=True, slots=True)
class PromptDetectionResult:
    """Return resolved roles and fail-closed ambiguities for one graph section."""

    detections: tuple[PromptRoleDetection, ...] = ()
    ambiguities: tuple[PromptRoleAmbiguity, ...] = ()


__all__ = [
    "PromptAmbiguityReason",
    "PromptDetectionResult",
    "PromptEvidence",
    "PromptEvidenceKind",
    "PromptFieldLocator",
    "PromptGraphField",
    "PromptGraphContext",
    "PromptGraphInput",
    "PromptGraphNode",
    "PromptGraphOutput",
    "PromptGraphSource",
    "PromptRoleAmbiguity",
    "PromptRoleDetection",
    "PromptSemanticGraph",
    "PromptSinkLocator",
]
