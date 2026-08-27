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

"""Reject competing input-asset policy and topology-gated transport."""

from __future__ import annotations

import ast
from pathlib import Path

from tools.architecture_governance.model import Diagnostic

_POLICY_OWNER = "substitute/application/workflows/input_asset_field_policy.py"
_TRANSPORT_METADATA_KEYS = frozenset(
    {"image_upload", "image_folder", "allow_batch", "multiselect"}
)
_REQUIRED_POLICY_IMPORTS = {
    "substitute/application/node_behavior/field_classification.py": (
        "InputAssetFieldPolicy"
    ),
    "substitute/application/recipes/runtime_asset_picker_policy.py": (
        "InputAssetFieldPolicy"
    ),
    "substitute/application/workflows/input_asset_endpoint_service.py": (
        "InputAssetFieldPolicy"
    ),
    "substitute/application/generation/input_asset_staging_plan_service.py": (
        "InputAssetFieldService"
    ),
    "substitute/application/generation/asset_staging_service.py": (
        "InputAssetFieldPolicy"
    ),
}


def validate_input_asset_governance(root: Path) -> list[Diagnostic]:
    """Return static diagnostics for external input-asset policy ownership."""

    diagnostics: list[Diagnostic] = []
    trees: dict[str, ast.Module] = {}
    source_root = root / "substitute"
    if not source_root.is_dir():
        return diagnostics
    for path in sorted(source_root.rglob("*.py")):
        relative_path = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except (OSError, UnicodeError, SyntaxError) as error:
            diagnostics.append(
                Diagnostic("ASSET001", relative_path, f"cannot inspect source: {error}")
            )
            continue
        trees[relative_path] = tree
        diagnostics.extend(_policy_ownership_diagnostics(relative_path, tree))

    diagnostics.extend(_required_consumer_diagnostics(trees))
    return diagnostics


def _policy_ownership_diagnostics(
    relative_path: str,
    tree: ast.Module,
) -> list[Diagnostic]:
    """Reject transport metadata interpretation and registries outside the owner."""

    diagnostics: list[Diagnostic] = []
    for node in ast.walk(tree):
        if (
            relative_path != _POLICY_OWNER
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in _TRANSPORT_METADATA_KEYS
        ):
            diagnostics.append(
                Diagnostic(
                    "ASSET002",
                    relative_path,
                    "input-asset transport metadata may be interpreted only by "
                    f"{_POLICY_OWNER} (line {node.lineno})",
                )
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target_names = _assignment_target_names(node)
            if any("LOAD_IMAGE_CLASSES" in name for name in target_names):
                diagnostics.append(
                    Diagnostic(
                        "ASSET003",
                        relative_path,
                        "class-name asset registries must be replaced by "
                        f"InputAssetFieldPolicy (line {node.lineno})",
                    )
                )
    return diagnostics


def _required_consumer_diagnostics(
    trees: dict[str, ast.Module],
) -> list[Diagnostic]:
    """Require each behavior-critical consumer to derive from the semantic owner."""

    diagnostics: list[Diagnostic] = []
    for relative_path, required_name in _REQUIRED_POLICY_IMPORTS.items():
        tree = trees.get(relative_path)
        if tree is None:
            continue
        imported_names = {
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        if required_name not in imported_names:
            diagnostics.append(
                Diagnostic(
                    "ASSET004",
                    relative_path,
                    f"consumer must derive asset behavior from {required_name}",
                )
            )

    endpoint_path = "substitute/application/workflows/input_asset_endpoint_service.py"
    endpoint_tree = trees.get(endpoint_path)
    if endpoint_tree is not None and not _calls_attribute(
        endpoint_tree,
        "used_output_indexes",
    ):
        diagnostics.append(
            Diagnostic(
                "ASSET005",
                endpoint_path,
                "endpoint roles must include internal and exported output usage",
            )
        )

    staging_path = (
        "substitute/application/generation/input_asset_staging_plan_service.py"
    )
    staging_tree = trees.get(staging_path)
    if staging_tree is not None and not _calls_attribute(
        staging_tree,
        "fields_for_graph",
    ):
        diagnostics.append(
            Diagnostic(
                "ASSET006",
                staging_path,
                "staging must enumerate compiled asset fields independently of topology",
            )
        )
    return diagnostics


def _assignment_target_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    """Return simple names assigned by one declaration."""

    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _calls_attribute(tree: ast.Module, attribute: str) -> bool:
    """Return whether source calls one named collaborator method."""

    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
        for node in ast.walk(tree)
    )


__all__ = ["validate_input_asset_governance"]
