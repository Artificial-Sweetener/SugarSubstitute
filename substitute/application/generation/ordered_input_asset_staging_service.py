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

"""Stage ordered asset values without changing compiler-owned graph topology."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sugarsubstitute_shared.localization import app_text

from substitute.application.generation.input_asset_source_resolver import (
    InputAssetSourceResolver,
)
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingTarget,
)
from substitute.application.ports.comfy_asset_stager import ComfyAssetStager
from substitute.domain.common import JsonObject
from substitute.domain.generation import AssetStagingFailure, ComfyStagedAsset
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("application.generation.ordered_input_asset_staging_service")
_COMFY_LITERAL_VALUE_KEY = "__value__"


@dataclass(frozen=True, slots=True)
class OrderedInputAssetStagingResult:
    """Return one staged literal-list value and its diagnostics."""

    execution_value: JsonObject | None
    staged_assets: tuple[ComfyStagedAsset, ...]
    failures: tuple[AssetStagingFailure, ...]


class OrderedInputAssetStagingService:
    """Translate ordered source values while preserving their compiled node."""

    def __init__(
        self,
        *,
        stager: ComfyAssetStager,
        source_resolver: InputAssetSourceResolver,
    ) -> None:
        """Capture the node-preserving target and source resolution boundaries."""

        self._stager = stager
        self._source_resolver = source_resolver

    def stage(
        self,
        *,
        node_id: str,
        node_class: str,
        values: object,
        target: InputAssetStagingTarget,
        target_subfolder: str,
        workflow_name: str,
    ) -> OrderedInputAssetStagingResult:
        """Stage every ordered value and retain the compiler's literal-list shape."""

        authored_values = _literal_list(values)
        if authored_values is None:
            return _failure_result(
                node_id=node_id,
                node_class=node_class,
                input_name=target.field_key,
                source_value="",
                message=app_text("Required image input has no selected image."),
            )
        sources = self._source_resolver.ordered_sources(
            values=authored_values,
            workflow_name=workflow_name,
        )
        if not sources:
            return _failure_result(
                node_id=node_id,
                node_class=node_class,
                input_name=target.field_key,
                source_value="",
                message=app_text("Required image input has no selected image."),
            )

        staged_assets: list[ComfyStagedAsset] = []
        failures: list[AssetStagingFailure] = []
        for index, source in enumerate(sources):
            source_path = source.path
            input_name = f"{target.field_key}[{index}]"
            if source_path is None or not source_path.exists():
                failures.append(
                    AssetStagingFailure(
                        node_id=node_id,
                        node_class=node_class,
                        input_name=input_name,
                        source_value=source.source_value,
                        message=app_text("Referenced local image file does not exist."),
                    )
                )
                continue
            try:
                staged_asset = self._stager.stage_file_for_load_image(
                    source_path=source_path,
                    target_subfolder=target_subfolder,
                    content_hash=_file_sha256(source_path),
                    node_class=node_class,
                )
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Failed to stage ordered input asset",
                    workflow_name=workflow_name,
                    node_id=node_id,
                    node_class=node_class,
                    input_index=index,
                    source_path=str(source_path),
                    error=error,
                )
                failures.append(
                    AssetStagingFailure(
                        node_id=node_id,
                        node_class=node_class,
                        input_name=input_name,
                        source_value=source.source_value,
                        message=str(error),
                    )
                )
                continue
            if staged_asset.execution_node_class is not None:
                failures.append(
                    AssetStagingFailure(
                        node_id=node_id,
                        node_class=node_class,
                        input_name=input_name,
                        source_value=source.source_value,
                        message=app_text("Generation preflight failed"),
                    )
                )
                continue
            staged_assets.append(staged_asset)

        if failures:
            return OrderedInputAssetStagingResult(
                execution_value=None,
                staged_assets=tuple(staged_assets),
                failures=tuple(failures),
            )
        return OrderedInputAssetStagingResult(
            execution_value={
                _COMFY_LITERAL_VALUE_KEY: [
                    asset.execution_value for asset in staged_assets
                ]
            },
            staged_assets=tuple(staged_assets),
            failures=(),
        )


def _literal_list(value: object) -> list[str] | None:
    """Return ordered string values from Comfy's literal-array representation."""

    candidate = (
        value.get(_COMFY_LITERAL_VALUE_KEY) if isinstance(value, dict) else value
    )
    if not isinstance(candidate, list) or not all(
        isinstance(item, str) and item for item in candidate
    ):
        return None
    return candidate


def _failure_result(
    *,
    node_id: str,
    node_class: str,
    input_name: str,
    source_value: str,
    message: str,
) -> OrderedInputAssetStagingResult:
    """Build one terminal ordered staging failure."""

    return OrderedInputAssetStagingResult(
        execution_value=None,
        staged_assets=(),
        failures=(
            AssetStagingFailure(
                node_id=node_id,
                node_class=node_class,
                input_name=input_name,
                source_value=source_value,
                message=message,
            ),
        ),
    )


def _file_sha256(path: Path) -> str:
    """Return the sha256 digest for one ordered source file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["OrderedInputAssetStagingResult", "OrderedInputAssetStagingService"]
