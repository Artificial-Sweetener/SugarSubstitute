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

"""Cover main-window dependency composition."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap import composition
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION


def _build_ready_context(tmp_path: Path) -> InstallationContext:
    """Build a ready installation context for startup routing tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def test_main_window_dependencies_include_user_preset_service(tmp_path: Path) -> None:
    """Bootstrap composition should wire presets to the user-owned preset file."""

    context = _build_ready_context(tmp_path)
    application = cast(
        QApplication,
        QApplication.instance() or QApplication([]),
    )
    localization = composition.build_application_localization_runtime(
        application,
        context,
        None,
    )

    runtime_services = composition.build_application_runtime_services(
        context=context,
        comfy_output_stream=cast(Any, object()),
        localization_manager=localization.manager,
        appearance_runtime=composition.build_appearance_runtime(context),
    )
    dependencies = composition._build_main_window_dependencies(
        runtime_services,
    )
    preset = dependencies.user_preset_service.save_dimension_preset(
        width=1536,
        height=1024,
        association=GLOBAL_PRESET_ASSOCIATION,
    )

    assert preset.payload.short_edge == 1024
    assert (context.user_dir / "presets.json").exists()
    assert dependencies.session_snapshot_repository is (
        runtime_services.session_snapshot_repository
    )
    assert dependencies.session_autosave_service is (
        runtime_services.session_autosave_service
    )
    assert dependencies.generation_result_snapshot_service is not None
    dependencies.shell_resource_lifecycle.shutdown()
    runtime_services.execution_runtime.shutdown()
    localization.manager.close()
