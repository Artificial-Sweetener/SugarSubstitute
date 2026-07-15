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

"""Resolve the output path seed token from prepared generation inputs."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.domain.common import JsonObject
from substitute.domain.recipes import parse_sugar_script_document
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.generation.output_seed_resolver")


def resolve_output_seed(
    *,
    sugar_script_text: str,
    workflow_payload: JsonObject,
) -> str:
    """Return the preferred output seed token value for one generation."""

    global_seed = _global_override_seed(sugar_script_text)
    if global_seed:
        return global_seed
    return _first_workflow_seed(workflow_payload)


def _global_override_seed(sugar_script_text: str) -> str:
    """Return the global override seed from Sugar text, if present."""

    try:
        parsed_script = parse_sugar_script_document(sugar_script_text)
    except Exception as error:
        log_warning(
            _LOGGER,
            "Failed to parse Sugar script while resolving output seed.",
            error=repr(error),
        )
        return ""
    override = parsed_script.global_overrides.get("seed")
    if not isinstance(override, Mapping) or "value" not in override:
        return ""
    return _seed_value_text(override.get("value"))


def _first_workflow_seed(workflow_payload: JsonObject) -> str:
    """Return the first exact workflow input seed, if present."""

    for node in executable_prompt_nodes(workflow_payload).values():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping) or "seed" not in inputs:
            continue
        seed_text = _seed_value_text(inputs.get("seed"))
        if seed_text:
            return seed_text
    return ""


def _seed_value_text(value: object) -> str:
    """Return filename-token text for supported scalar seed values."""

    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


__all__ = ["resolve_output_seed"]
