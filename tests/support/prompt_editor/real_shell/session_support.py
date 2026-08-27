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

"""Mount the production shell composition used by real prompt-editor scenarios."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


from substitute.application.ports import (
    NodeDefinitionHydrationResult,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile


class _StaticPromptFeatureProfileService:
    """Return one explicit feature profile through the production panel seam."""

    def __init__(self, profile: PromptEditorFeatureProfile) -> None:
        """Store the immutable profile used by every mounted harness field."""

        self._profile = profile

    def build_profile(
        self,
        *,
        field_style: Mapping[str, object],
        workflow_context: object,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptEditorFeatureProfile:
        """Return the configured profile without deriving external preferences."""

        _ = (
            field_style,
            workflow_context,
            cube_alias,
            prompt_node_name,
            prompt_field_key,
        )
        return self._profile


class _PromptNodeDefinitionGateway:
    """Return deterministic live node definitions for the prompt fixture."""

    _SUPPORTED_NODE_CLASSES = frozenset(
        {"CLIPTextEncode", "SimpleSyrup.SimpleLoadAnima", "UNETLoader"}
    )

    def __init__(self) -> None:
        """Initialize optional recorded definitions for broader shell scenarios."""

        self._recorded_definitions: dict[str, dict[str, object]] = {}

    def install_recorded_definitions(
        self,
        definitions: Mapping[str, Mapping[str, object]],
    ) -> None:
        """Install deterministic Comfy definitions used by a headless scenario."""

        self._recorded_definitions = {
            class_type: dict(definition)
            for class_type, definition in definitions.items()
        }

    def ensure_node_definitions(
        self,
        node_classes: Sequence[str],
    ) -> NodeDefinitionHydrationResult:
        """Report requested prompt fixture definitions as foreground-hydrated."""

        requested = tuple(node_classes)
        available = tuple(
            node_class
            for node_class in requested
            if node_class in self._SUPPORTED_NODE_CLASSES
            or node_class in self._recorded_definitions
        )
        unavailable = tuple(
            node_class
            for node_class in requested
            if node_class not in self._SUPPORTED_NODE_CLASSES
            and node_class not in self._recorded_definitions
        )
        return NodeDefinitionHydrationResult(
            requested=requested,
            available=available,
            unavailable=unavailable,
        )

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one class definition in the gateway payload shape."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required class definition in the gateway payload shape."""

        definitions: dict[str, dict[str, object]] = {
            "CLIPTextEncode": {
                "input": {
                    "required": {
                        "text": ["STRING", {"multiline": True, "dynamicPrompts": True}]
                    }
                },
                "output": ["CONDITIONING"],
                "output_name": ["CONDITIONING"],
            },
            "SimpleSyrup.SimpleLoadAnima": {
                "input": {
                    "required": {
                        "diffusion_model": [["Anima/hassakuAnima_v11.safetensors"]]
                    }
                },
                "output": ["MODEL", "CLIP", "VAE"],
                "output_name": ["model", "clip", "vae"],
            },
            "UNETLoader": {
                "input": {"required": {"unet_name": [["flux.safetensors"]]}},
                "output": ["MODEL"],
                "output_name": ["MODEL"],
            },
        }
        definition = self._recorded_definitions.get(node_class)
        if definition is None:
            definition = definitions.get(node_class)
        return {} if definition is None else {node_class: definition}


class _GenerationJobQueueService:
    """Provide queue timing APIs touched by shell collaborators."""

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Return no timing data for generated output metadata."""

        _ = (workflow_id, source_key, cube_alias)
        return None


class _ProgressBar:
    """Store progress-bar calls made by shell controllers."""

    def __init__(self) -> None:
        """Initialize deterministic progress state."""

        self.value = 0
        self.use_animation = True

    def setValue(self, value: int) -> None:
        """Store the latest projected progress value."""

        self.value = value

    def setUseAni(self, enabled: bool) -> None:
        """Store the requested animation state."""

        self.use_animation = enabled

    def isUseAni(self) -> bool:
        """Return the current animation state."""

        return self.use_animation


class _PromptInteractionTracker:
    """Provide inactive prompt-interaction scheduling state."""

    def is_prompt_interaction_active(self) -> bool:
        """Return that prompt interaction is inactive."""

        return False

    def ms_since_last_prompt_interaction(self) -> int:
        """Return a stable elapsed interaction value."""

        return 0


class _ErrorPresenter:
    """Record structured error reports without opening modal dialogs."""

    def __init__(self, reports: list[object]) -> None:
        """Store the shared report list."""

        self._reports = reports

    def show_error_report(self, report: object) -> None:
        """Record one report for harness assertions."""

        self._reports.append(report)
