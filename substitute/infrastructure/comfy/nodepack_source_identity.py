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

"""Validate trusted core nodepack source identity."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.nodepack_installation_inspector import (
    read_nodepack_project_identity,
)
from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    source_contains_sentinels,
)


def validate_nodepack_source_identity(
    source_path: Path,
    nodepack: CoreComfyNodepack,
    *,
    require_version: bool,
) -> None:
    """Reject source that is not the trusted project and requested release."""

    if not source_contains_sentinels(source_path, nodepack):
        raise RuntimeError(
            f"{nodepack.display_name} source did not contain required files."
        )
    name, version, repository_url = read_nodepack_project_identity(
        source_path / "pyproject.toml"
    )
    expected_repository = nodepack.fallback_repository_url.removesuffix(".git")
    observed_repository = (
        repository_url.removesuffix(".git") if repository_url is not None else None
    )
    if (
        name is None
        or name.casefold() != nodepack.registry_id.casefold()
        or (require_version and version != nodepack.required_version)
        or observed_repository is None
        or observed_repository.casefold() != expected_repository.casefold()
    ):
        raise RuntimeError(
            f"{nodepack.display_name} source identity did not match "
            f"{nodepack.registry_id}@{nodepack.required_version}."
        )


__all__ = ["validate_nodepack_source_identity"]
