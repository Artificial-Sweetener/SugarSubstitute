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

"""Provide Comfy asset stagers for local and remote execution targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from substitute.domain.generation import ComfyStagedAsset
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import default_http_post
from sugarsubstitute_shared.windows_long_paths import operational_path, subprocess_path


@dataclass(frozen=True)
class LocalComfyAssetStager:
    """Authorize local files for no-copy execution by Substitute BackEnd."""

    endpoint: ComfyEndpoint
    timeout_seconds: float = 10.0
    post: Callable[..., Any] = default_http_post

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Authorize the existing file without copying or uploading its bytes."""

        del target_subfolder
        source_path = operational_path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(str(source_path))
        response = self.post(
            self.endpoint.substitute_local_asset_authorize_url(),
            json={
                "sourcePath": subprocess_path(source_path),
                "nodeClass": node_class,
                "contentHash": content_hash,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token") if isinstance(payload, dict) else None
        authorized_node_class = (
            payload.get("nodeClass") if isinstance(payload, dict) else None
        )
        execution_node_class = (
            payload.get("executionNodeClass") if isinstance(payload, dict) else None
        )
        authorized_content_hash = (
            payload.get("contentHash") if isinstance(payload, dict) else None
        )
        if not isinstance(token, str) or not token:
            raise RuntimeError(
                "Substitute BackEnd authorization did not include an asset token."
            )
        if (
            authorized_node_class != node_class
            or authorized_content_hash != content_hash
            or not isinstance(execution_node_class, str)
            or not execution_node_class
        ):
            raise RuntimeError(
                "Substitute BackEnd authorization did not match the requested asset."
            )
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=token,
            operation="authorized",
            execution_node_class=execution_node_class,
        )


@dataclass(frozen=True)
class RemoteUploadComfyAssetStager:
    """Upload source files to Comfy's input namespace for remote targets."""

    endpoint: ComfyEndpoint
    timeout_seconds: float = 30.0
    post: Callable[..., Any] = default_http_post

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
        node_class: str,
    ) -> ComfyStagedAsset:
        """Upload a source file and return the Comfy input namespace value."""

        del node_class
        source_path = operational_path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(str(source_path))
        with source_path.open("rb") as handle:
            response = self.post(
                self.endpoint.upload_image_url(),
                data={
                    "subfolder": target_subfolder,
                    "type": "input",
                    "overwrite": "true",
                },
                files={"image": (source_path.name, handle, "application/octet-stream")},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        payload = response.json()
        name = payload.get("name") if isinstance(payload, dict) else None
        subfolder = payload.get("subfolder") if isinstance(payload, dict) else None
        if not isinstance(name, str) or not name:
            raise RuntimeError("Comfy upload response did not include image name.")
        if not isinstance(subfolder, str):
            subfolder = ""
        execution_value = f"{subfolder}/{name}" if subfolder else name
        return ComfyStagedAsset(
            source_path=source_path,
            execution_value=execution_value,
            operation="uploaded",
        )


__all__ = ["LocalComfyAssetStager", "RemoteUploadComfyAssetStager"]
