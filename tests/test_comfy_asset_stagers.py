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
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def test_local_asset_stager_authorizes_source_without_copying(tmp_path: Path) -> None:
    """Local targets should authorize the existing source without duplicating it."""

    source = tmp_path / "input.png"
    source.write_bytes(b"image")
    before = tuple(tmp_path.iterdir())
    calls: list[tuple[str, dict[str, str], float]] = []

    def _post(
        url: str,
        *,
        json: dict[str, str],
        timeout: float,
    ) -> SimpleNamespace:
        calls.append((url, json, timeout))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "token": "opaque-token",
                "nodeClass": "LoadImage",
                "executionNodeClass": "SubstituteBackendLoadImage",
                "contentHash": "a" * 64,
            },
        )

    staged = LocalComfyAssetStager(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        timeout_seconds=7.0,
        post=_post,
    ).stage_file_for_load_image(
        source_path=source,
        target_subfolder="substitute/wf",
        content_hash="a" * 64,
        node_class="LoadImage",
    )

    assert staged.source_path == source
    assert staged.execution_value == "opaque-token"
    assert staged.operation == "authorized"
    assert staged.execution_node_class == "SubstituteBackendLoadImage"
    assert calls == [
        (
            "http://127.0.0.1:8188/substitute/v1/local-assets/authorize",
            {
                "sourcePath": subprocess_path(source),
                "nodeClass": "LoadImage",
                "contentHash": "a" * 64,
            },
            7.0,
        )
    ]
    assert tuple(tmp_path.iterdir()) == before
    assert source.read_bytes() == b"image"


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
        node_class="LoadImage",
    )

    assert calls[0][0] == "http://10.0.0.2:8189/upload/image"
    assert calls[0][1]["subfolder"] == "substitute/wf"
    assert calls[0][1]["type"] == "input"
    assert calls[0][2] == "input.png"
    assert calls[0][3] == 12.0
    assert staged.execution_value == "substitute/wf/input.png"
    assert staged.operation == "uploaded"


def test_local_asset_stager_rejects_mismatched_authorization(
    tmp_path: Path,
) -> None:
    """The desktop client must not accept a token for a different source request."""

    source = tmp_path / "input.png"
    source.write_bytes(b"image")

    def _post(
        _url: str,
        *,
        json: dict[str, str],
        timeout: float,
    ) -> SimpleNamespace:
        del json, timeout
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "token": "opaque-token",
                "nodeClass": "LoadImageMask",
                "executionNodeClass": "SubstituteBackendLoadImageMask",
                "contentHash": "a" * 64,
            },
        )

    with pytest.raises(RuntimeError, match="did not match"):
        LocalComfyAssetStager(
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            post=_post,
        ).stage_file_for_load_image(
            source_path=source,
            target_subfolder="substitute/wf",
            content_hash="a" * 64,
            node_class="LoadImage",
        )


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
            node_class="LoadImageMask",
        )
