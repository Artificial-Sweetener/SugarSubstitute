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

"""Own durable per-node advanced-input disclosure state."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.node_behavior.advanced_input_state")
_ADVANCED_INPUT_VISIBILITY_UI_KEY = "advanced_input_visibility"


class AdvancedInputStateService:
    """Read and mutate advanced-input disclosure without touching field values."""

    def is_shown(self, editor_state: object, node_name: str) -> bool:
        """Return the stored state or the imported Comfy disclosure default."""

        ui_payload = getattr(editor_state, "ui", None)
        if isinstance(ui_payload, Mapping):
            visibility = ui_payload.get(_ADVANCED_INPUT_VISIBILITY_UI_KEY)
            if isinstance(visibility, Mapping) and node_name in visibility:
                stored = visibility[node_name]
                if type(stored) is bool:
                    return stored
                log_warning(
                    _LOGGER,
                    "Ignored invalid advanced-input visibility state",
                    node_name=node_name,
                    cube_alias=str(getattr(editor_state, "alias", "")),
                    stored_type=type(stored).__name__,
                )
        return self._imported_comfy_state(editor_state, node_name)

    def set_shown(
        self,
        editor_state: object,
        node_name: str,
        shown: bool,
    ) -> bool:
        """Persist one card disclosure change and report whether state changed."""

        if self.is_shown(editor_state, node_name) is shown:
            return False
        ui_payload = self._mutable_ui_payload(editor_state)
        visibility = ui_payload.get(_ADVANCED_INPUT_VISIBILITY_UI_KEY)
        if not isinstance(visibility, dict):
            visibility = {}
            ui_payload[_ADVANCED_INPUT_VISIBILITY_UI_KEY] = visibility
        visibility[node_name] = shown
        if hasattr(editor_state, "dirty"):
            setattr(editor_state, "dirty", True)
        log_debug(
            _LOGGER,
            "Changed node-card advanced-input visibility",
            node_name=node_name,
            cube_alias=str(getattr(editor_state, "alias", "")),
            shown=shown,
        )
        return True

    @staticmethod
    def _mutable_ui_payload(editor_state: object) -> dict[str, object]:
        """Return mutable durable UI metadata, creating it when absent."""

        ui_payload = getattr(editor_state, "ui", None)
        if not isinstance(ui_payload, dict):
            ui_payload = {}
            setattr(editor_state, "ui", ui_payload)
        return ui_payload

    @staticmethod
    def _imported_comfy_state(editor_state: object, node_name: str) -> bool:
        """Return a Comfy workflow node's serialized disclosure state when present."""

        buffer = getattr(editor_state, "buffer", None)
        if not isinstance(buffer, Mapping):
            return False
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            return False
        node = nodes.get(node_name)
        if not isinstance(node, Mapping):
            return False
        workflow_metadata = node.get("_workflow")
        if not isinstance(workflow_metadata, Mapping):
            return False
        return workflow_metadata.get("show_advanced_inputs") is True


__all__ = ["AdvancedInputStateService"]
