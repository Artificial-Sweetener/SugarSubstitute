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

"""Verify promotion of an upstream standalone environment layout."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.infrastructure.comfy.standalone_environment.layout import (
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.migration import (
    StandaloneWorkspaceMigrator,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)

from .support import _release_for_variant


def test_migrator_promotes_upstream_layout_without_mixing_runtime_roots(
    tmp_path: Path,
) -> None:
    """Promotion should keep master Python separate from the Comfy workspace."""

    extracted = tmp_path / "extracted"
    (extracted / "ComfyUI").mkdir(parents=True)
    (extracted / "ComfyUI" / "main.py").write_text("main", encoding="utf-8")
    (extracted / "standalone-env").mkdir()
    release = _release_for_variant(StandaloneVariantId.WINDOWS_CPU)
    (extracted / "manifest.json").write_text(
        json.dumps({"id": release.variant.value, "version": release.release_tag}),
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"

    layout = StandaloneWorkspaceMigrator().promote(extracted, workspace, release)

    assert isinstance(layout, ManagedStandaloneLayout)
    assert (workspace / "main.py").is_file()
    assert (workspace / ".standalone-env").is_dir()
    assert layout.manifest.is_file()
    assert not extracted.exists()
