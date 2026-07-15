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

"""Contract tests for infrastructure Comfy asset stagers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy import (
    LocalComfyAssetStager,
    RemoteUploadComfyAssetStager,
)


def test_local_asset_stager_returns_direct_filesystem_path(tmp_path: Path) -> None:
    """Local targets should not duplicate readable source files."""

    source = tmp_path / "input.png"
    source.write_bytes(b"image")

    staged = LocalComfyAssetStager().stage_file_for_load_image(
        source_path=source,
        target_subfolder="substitute/wf",
        content_hash="abc",
    )

    assert staged.source_path == source
    assert staged.execution_value == str(source)
    assert staged.operation == "direct"


def test_remote_asset_stager_uploads_to_comfy_input_namespace(
    tmp_path: Path,
) -> None:
    """Remote targets should use Comfy's native upload image endpoint."""

    source = tmp_path / "input.png"
    source.write_bytes(b"image")
    calls: list[tuple[str, dict[str, str], str, float]] = []

    def _post(
        url: str,
        *,
        data: dict[str, str],
        files: dict[str, tuple[str, object, str]],
        timeout: float,
    ) -> SimpleNamespace:
        calls.append((url, data, files["image"][0], timeout))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"name": "input.png", "subfolder": "substitute/wf"},
        )

    staged = RemoteUploadComfyAssetStager(
        endpoint=ComfyEndpoint(host="10.0.0.2", port=8189),
        timeout_seconds=12.0,
        post=_post,
    ).stage_file_for_load_image(
        source_path=source,
        target_subfolder="substitute/wf",
        content_hash="abc",
    )

    assert calls[0][0] == "http://10.0.0.2:8189/upload/image"
    assert calls[0][1]["subfolder"] == "substitute/wf"
    assert calls[0][1]["type"] == "input"
    assert calls[0][2] == "input.png"
    assert calls[0][3] == 12.0
    assert staged.execution_value == "substitute/wf/input.png"
    assert staged.operation == "uploaded"


def test_remote_asset_stager_raises_when_upload_fails(
    tmp_path: Path,
) -> None:
    """Remote upload failures should surface before prompt queueing."""

    source = tmp_path / "input.png"
    source.write_bytes(b"image")

    def _post(
        _url: str,
        *,
        data: dict[str, str],
        files: dict[str, tuple[str, object, str]],
        timeout: float,
    ) -> SimpleNamespace:
        del data, files, timeout
        return SimpleNamespace(
            raise_for_status=lambda: (_ for _ in ()).throw(
                RuntimeError("upload failed")
            ),
            json=lambda: {},
        )

    with pytest.raises(RuntimeError, match="upload failed"):
        RemoteUploadComfyAssetStager(
            endpoint=ComfyEndpoint(host="10.0.0.2", port=8189),
            post=_post,
        ).stage_file_for_load_image(
            source_path=source,
            target_subfolder="substitute/wf",
            content_hash="abc",
        )
