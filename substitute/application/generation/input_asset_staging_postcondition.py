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

"""Enforce that execution payloads retain no unresolved local asset path."""

from __future__ import annotations

from collections.abc import Mapping

from sugarsubstitute_shared.localization import app_text

from substitute.application.generation.input_asset_source_resolver import (
    InputAssetSourceResolver,
)
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingTarget,
)
from substitute.domain.common import WorkflowId
from substitute.domain.generation import AssetStagingFailure
from substitute.domain.workflow import InputAssetCardinality
from substitute.shared.logging.logger import get_logger, log_error

_LOGGER = get_logger("application.generation.input_asset_staging_postcondition")


def enforce_input_asset_staging_postcondition(
    *,
    prompt: Mapping[str, object],
    targets: tuple[InputAssetStagingTarget, ...],
    staged_target_keys: set[tuple[str, str]],
    failures: list[AssetStagingFailure],
    source_resolver: InputAssetSourceResolver,
    workflow_id: WorkflowId,
    workflow_name: str,
    workflow: object | None,
) -> None:
    """Remove and diagnose any scalar local path left after staging."""

    failed_target_keys = {
        (failure.node_id, failure.input_name.partition("[")[0]) for failure in failures
    }
    for target in targets:
        target_key = (target.executable_node_id, target.field_key)
        if (
            target.cardinality is InputAssetCardinality.ORDERED
            or target_key in staged_target_keys
        ):
            continue
        node_data = prompt.get(target.executable_node_id)
        if not isinstance(node_data, Mapping):
            continue
        inputs = node_data.get("inputs")
        if not isinstance(inputs, dict):
            continue
        value = inputs.get(target.field_key)
        if not isinstance(value, str) or not value:
            continue
        source_path = source_resolver.scalar_source(
            image_value=value,
            target=target,
            workflow_name=workflow_name,
            workflow=workflow,
        )
        if source_path is None:
            continue
        inputs[target.field_key] = ""
        log_error(
            _LOGGER,
            "Removed unresolved local asset path after staging",
            workflow_id=workflow_id,
            node_id=target.executable_node_id,
            field_key=target.field_key,
            source_path=str(source_path),
            postcondition="no_local_asset_path",
        )
        if target_key not in failed_target_keys:
            node_class = node_data.get("class_type")
            failures.append(
                AssetStagingFailure(
                    node_id=target.executable_node_id,
                    node_class=str(node_class),
                    input_name=target.field_key,
                    source_value=value,
                    message=app_text("Generation preflight failed"),
                )
            )


__all__ = ["enforce_input_asset_staging_postcondition"]
