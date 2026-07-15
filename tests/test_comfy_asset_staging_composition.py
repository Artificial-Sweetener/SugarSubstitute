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

"""Contract tests for Comfy asset staging composition."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from substitute.app.bootstrap.composition import _build_comfy_asset_staging_service
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy import (
    LocalComfyAssetStager,
    RemoteUploadComfyAssetStager,
)


def _context(mode: ComfyTargetMode) -> InstallationContext:
    """Build a minimal installation context carrying target configuration."""

    installation = InstallationConfiguration.create_default(Path("E:/substitute"))
    return InstallationContext(
        installation=installation,
        runtime=RuntimeConfiguration.create_default(installation),
        comfy_target=ComfyTargetConfiguration(
            mode=mode,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=None,
            install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
            launch_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        ),
    )


def test_managed_local_composition_uses_local_asset_stager() -> None:
    """Managed local targets should use direct local path staging."""

    service = _build_comfy_asset_staging_service(
        _context(ComfyTargetMode.MANAGED_LOCAL)
    )

    assert isinstance(service.stager, LocalComfyAssetStager)


def test_attached_local_composition_uses_local_asset_stager() -> None:
    """Attached local targets should use direct local path staging."""

    service = _build_comfy_asset_staging_service(
        _context(ComfyTargetMode.ATTACHED_LOCAL)
    )

    assert isinstance(service.stager, LocalComfyAssetStager)


def test_remote_composition_uses_remote_upload_asset_stager() -> None:
    """Remote targets should upload source files through Comfy."""

    service = _build_comfy_asset_staging_service(_context(ComfyTargetMode.REMOTE))

    assert isinstance(service.stager, RemoteUploadComfyAssetStager)


def test_managed_local_composition_does_not_import_requests() -> None:
    """Managed-local staging composition should not pay remote HTTP imports."""

    code = textwrap.dedent(
        """
        import json
        import sys
        from pathlib import Path

        from substitute.app.bootstrap.composition import (
            _build_comfy_asset_staging_service,
        )
        from substitute.domain.onboarding import (
            ComfyEndpoint,
            ComfyTargetConfiguration,
            ComfyTargetMode,
            InstallationConfiguration,
            InstallationContext,
            RuntimeConfiguration,
        )

        installation = InstallationConfiguration.create_default(Path("E:/substitute"))
        context = InstallationContext(
            installation=installation,
            runtime=RuntimeConfiguration.create_default(installation),
            comfy_target=ComfyTargetConfiguration(
                mode=ComfyTargetMode.MANAGED_LOCAL,
                endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
                workspace_path=None,
                install_owned=True,
                launch_owned=True,
            ),
        )
        _build_comfy_asset_staging_service(context)
        print(json.dumps({"requests_loaded": "requests" in sys.modules}))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout.strip()) == {"requests_loaded": False}
