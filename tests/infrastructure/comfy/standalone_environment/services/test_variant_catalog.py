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

"""Verify standalone environment variant policy and release catalog ownership."""

from __future__ import annotations

import hashlib
from typing import cast

import pytest
import requests

from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.standalone_environment.catalog_client import (
    GITHUB_RELEASE_API_TEMPLATE,
    LATEST_CATALOG_URL,
    LiveStandaloneEnvironmentCatalogClient,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneCatalogError,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.variant_policy import (
    standalone_variant_for_target,
)

from .support import _CatalogSession


def test_variant_policy_matches_current_comfy_desktop_catalog() -> None:
    """Every supported managed target should map to its published catalog ID."""

    assert (
        standalone_variant_for_target(ManagedInstallTarget.WINDOWS_NVIDIA)
        is StandaloneVariantId.WINDOWS_NVIDIA
    )
    assert (
        standalone_variant_for_target(ManagedInstallTarget.LINUX_AMD)
        is StandaloneVariantId.LINUX_AMD
    )
    assert (
        standalone_variant_for_target(ManagedInstallTarget.MACOS_APPLE_SILICON)
        is StandaloneVariantId.MACOS_MPS
    )
    assert (
        standalone_variant_for_target(ManagedInstallTarget.LINUX_CPU)
        is StandaloneVariantId.LINUX_NVIDIA
    )


def test_catalog_joins_live_variant_metadata_to_github_sha256() -> None:
    """Catalog resolution should require GitHub's digest-bearing release asset."""

    content = b"abc"
    filename = "comfyui-standalone-mac-mps-v1-env1.tar.gz"
    tag = "v1-env1"
    session = _CatalogSession(
        {
            LATEST_CATALOG_URL: {
                "mac-mps": {
                    "tag": tag,
                    "file": filename,
                    "size": len(content),
                    "comfyui_version": "v1.0.0",
                    "comfyui_commit": "a" * 40,
                    "python_version": "3.13.12",
                    "torch_version": "2.10.0",
                }
            },
            GITHUB_RELEASE_API_TEMPLATE.format(tag=tag): {
                "assets": [
                    {
                        "name": filename,
                        "size": len(content),
                        "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
                        "browser_download_url": f"https://example.invalid/{filename}",
                    }
                ]
            },
        }
    )

    release = LiveStandaloneEnvironmentCatalogClient(
        session=cast(requests.Session, session)
    ).resolve(StandaloneVariantId.MACOS_MPS)

    assert release.archive_kind is StandaloneArchiveKind.TAR_GZIP
    assert release.artifacts[0].sha256 == hashlib.sha256(content).hexdigest()
    assert release.python_version == "3.13.12"
    assert release.torch_version == "2.10.0"


def test_catalog_rejects_assets_without_sha256_digest() -> None:
    """Catalog resolution should fail closed when GitHub omits a digest."""

    filename = "comfyui-standalone-win-cpu-v1-env1.7z"
    tag = "v1-env1"
    session = _CatalogSession(
        {
            LATEST_CATALOG_URL: {
                "win-cpu": {
                    "tag": tag,
                    "file": filename,
                    "size": 3,
                    "comfyui_version": "v1.0.0",
                    "comfyui_commit": "a" * 40,
                    "python_version": "3.13.12",
                    "torch_version": "2.10.0+cpu",
                }
            },
            GITHUB_RELEASE_API_TEMPLATE.format(tag=tag): {
                "assets": [
                    {
                        "name": filename,
                        "size": 3,
                        "digest": None,
                        "browser_download_url": "https://example.invalid/file",
                    }
                ]
            },
        }
    )

    with pytest.raises(StandaloneCatalogError, match="SHA256"):
        LiveStandaloneEnvironmentCatalogClient(
            session=cast(requests.Session, session)
        ).resolve(StandaloneVariantId.WINDOWS_CPU)
