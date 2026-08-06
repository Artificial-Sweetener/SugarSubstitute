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

"""Verify ordered asset staging fails closed without changing graph ownership."""

from __future__ import annotations

from pathlib import Path

from substitute.application.generation.input_asset_source_resolver import (
    InputAssetSourceResolver,
)
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingTarget,
)
from substitute.application.generation.ordered_input_asset_staging_service import (
    OrderedInputAssetStagingService,
)
from substitute.domain.generation import ComfyStagedAsset
from substitute.domain.workflow import InputAssetCardinality, InputAssetRole


class _NodeReplacingStager:
    """Expose a scalar-only staging result that ordered inputs must reject."""

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Return a result that would require forbidden node replacement."""

        del target_subfolder, content_hash, node_class
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value="token",
            operation="authorized",
            execution_node_class="ScalarOnlyLoader",
        )


def test_ordered_staging_rejects_malformed_literal_list() -> None:
    """Non-string list entries must fail instead of being silently discarded."""

    result = _service(Path.cwd()).stage(
        node_id="1",
        node_class="SimpleSyrup.LoadMaskBatch",
        values={"__value__": ["first.png", 0]},
        target=_target(),
        target_subfolder="substitute/workflow",
        workflow_name="Recipe",
    )

    assert result.execution_value is None
    assert result.staged_assets == ()
    assert len(result.failures) == 1
    assert result.failures[0].message == "Required image input has no selected image."


def test_ordered_staging_rejects_results_that_require_node_replacement(
    tmp_path: Path,
) -> None:
    """A scalar-only stager must not authorize topology changes as a fallback."""

    mask_root = tmp_path / "Recipe" / "masks"
    mask_root.mkdir(parents=True)
    (mask_root / "first.png").write_bytes(b"mask")

    result = _service(tmp_path).stage(
        node_id="1",
        node_class="SimpleSyrup.LoadMaskBatch",
        values={"__value__": ["first.png"]},
        target=_target(),
        target_subfolder="substitute/workflow",
        workflow_name="Recipe",
    )

    assert result.execution_value is None
    assert result.staged_assets == ()
    assert len(result.failures) == 1
    assert result.failures[0].message == "Generation preflight failed"


def _service(projects_dir: Path) -> OrderedInputAssetStagingService:
    """Build the focused owner with a deterministic scalar-only boundary."""

    return OrderedInputAssetStagingService(
        stager=_NodeReplacingStager(),
        source_resolver=InputAssetSourceResolver(projects_dir),
    )


def _target() -> InputAssetStagingTarget:
    """Return one ordered mask staging target."""

    return InputAssetStagingTarget(
        executable_node_id="1",
        section_key="Region",
        node_name="load_mask_batch",
        field_key="image",
        role=InputAssetRole.MASK,
        cardinality=InputAssetCardinality.ORDERED,
    )
