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

"""Capture the production shell with a native Qt platform backend."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import platform
import sys
from typing import Sequence

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap import composition
from substitute.app.bootstrap.runtime import ApplicationRuntimeServices
from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.domain.appearance import (
    AppearanceThemeMode,
    default_appearance_preferences,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.persistence import (
    FileAppearancePreferenceRepository,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)


@dataclass(frozen=True, slots=True)
class NativeAppearanceCaptureRequest:
    """Describe one deterministic native shell capture."""

    install_root: Path
    output_path: Path
    theme: AppearanceThemeMode
    width: int = 1440
    height: int = 900
    settle_ms: int = 1500


def build_capture_context(install_root: Path) -> InstallationContext:
    """Build an isolated attached-local context for visual shell capture."""

    installation = InstallationConfiguration.create_default(install_root.resolve())
    for directory in (
        installation.user_settings_dir,
        installation.projects_dir,
        installation.outputs_dir,
        installation.wildcards_dir,
        installation.session_dir,
        installation.cache_dir,
        installation.diagnostics_dir,
        installation.logs_dir,
        installation.runtime_state_dir,
        installation.model_metadata_dir,
        installation.runtime_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    attached_workspace = install_root / "visual-fixture-comfyui"
    attached_workspace.mkdir(parents=True, exist_ok=True)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=Path(sys.executable),
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=attached_workspace,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def capture_native_appearance(request: NativeAppearanceCaptureRequest) -> Path:
    """Render and save one complete production shell appearance."""

    context = build_capture_context(request.install_root)
    preferences = default_appearance_preferences().with_theme_mode(request.theme)
    FileAppearancePreferenceRepository(context.user_settings_dir).save(preferences)

    app = composition.create_application(["capture_native_appearance"])
    appearance_runtime = composition.build_appearance_runtime(context)
    resolved_appearance = composition.configure_theme(appearance_runtime)
    output_stream = TerminalOutputStream()
    localization_runtime = composition.build_application_localization_runtime(
        app,
        context,
        None,
    )
    runtime_services = composition.build_application_runtime_services(
        context=context,
        comfy_output_stream=output_stream,
        localization_manager=localization_runtime.manager,
        appearance_runtime=appearance_runtime,
    )
    frame = composition.show_main_window(
        context,
        comfy_output_stream=output_stream,
        runtime_services=runtime_services,
    )
    frame.resize(request.width, request.height)

    capture_errors: list[str] = []

    def save_capture() -> None:
        """Save the settled shell and terminate its disposable event loop."""

        try:
            frame.resize(request.width, request.height)
            app.processEvents()
            _save_frame_capture(
                frame=frame,
                request=request,
                resolved_theme=resolved_appearance.effective_theme_mode.value,
                system_probe=appearance_runtime.active_system_probe(),
            )
        except (OSError, RuntimeError, ValueError) as error:
            capture_errors.append(str(error))
        finally:
            _shutdown_capture_surface(app, frame, runtime_services)

    QTimer.singleShot(request.settle_ms, save_capture)
    app.exec()
    if capture_errors:
        raise RuntimeError(capture_errors[0])
    if not request.output_path.is_file():
        raise RuntimeError(
            f"Native appearance capture was not written: {request.output_path}"
        )
    return request.output_path


def _save_frame_capture(
    *,
    frame: QWidget,
    request: NativeAppearanceCaptureRequest,
    resolved_theme: str,
    system_probe: SystemAppearanceProbe | None,
) -> None:
    """Write one shell PNG and its platform metadata sidecar."""

    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = frame.grab()
    if pixmap.isNull():
        raise RuntimeError("Qt returned an empty shell capture.")
    if not pixmap.save(str(request.output_path), "PNG"):
        raise RuntimeError(
            f"Qt could not save the shell capture: {request.output_path}"
        )
    metadata = {
        "platform": platform.platform(),
        "python_platform": sys.platform,
        "qt_platform": QApplication.platformName(),
        "requested_theme": request.theme.value,
        "resolved_theme": resolved_theme,
        "logical_width": frame.width(),
        "logical_height": frame.height(),
        "pixel_width": pixmap.width(),
        "pixel_height": pixmap.height(),
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "window_title": frame.windowTitle(),
        "appearance_adapter": (
            system_probe.adapter_name if system_probe is not None else None
        ),
        "detected_color_scheme": (
            system_probe.snapshot.color_scheme.value
            if system_probe is not None
            and system_probe.snapshot.color_scheme is not None
            else None
        ),
        "detected_accent_color": (
            system_probe.snapshot.accent_color.to_hex()
            if system_probe is not None
            and system_probe.snapshot.accent_color is not None
            else None
        ),
        "color_scheme_source": (
            system_probe.color_scheme_source if system_probe is not None else None
        ),
        "accent_color_source": (
            system_probe.accent_color_source if system_probe is not None else None
        ),
    }
    request.output_path.with_suffix(".json").write_text(
        f"{json.dumps(metadata, indent=2)}\n",
        encoding="utf-8",
    )


def _shutdown_capture_runtime(runtime_services: ApplicationRuntimeServices) -> None:
    """Stop process-lifetime workers created for the disposable shell."""

    runtime_services.execution_runtime.shutdown()


def _shutdown_capture_surface(
    app: QApplication,
    frame: QWidget,
    runtime_services: ApplicationRuntimeServices,
) -> None:
    """Destroy the shell while translators and its cleanup dependencies are alive."""

    _shutdown_capture_runtime(runtime_services)
    frame.close()
    frame.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.quit()


def parse_args(argv: Sequence[str] | None = None) -> NativeAppearanceCaptureRequest:
    """Parse one native appearance capture request."""

    parser = argparse.ArgumentParser(
        description="Capture the production Substitute shell through native Qt."
    )
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--theme",
        choices=(AppearanceThemeMode.LIGHT.value, AppearanceThemeMode.DARK.value),
        required=True,
    )
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--settle-ms", type=int, default=1500)
    args = parser.parse_args(argv)
    if args.width <= 0 or args.height <= 0:
        parser.error("capture dimensions must be positive")
    if args.settle_ms < 0:
        parser.error("settle time must not be negative")
    return NativeAppearanceCaptureRequest(
        install_root=args.install_root,
        output_path=args.output,
        theme=AppearanceThemeMode(args.theme),
        width=args.width,
        height=args.height,
        settle_ms=args.settle_ms,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Capture one requested platform appearance and report its path."""

    output_path = capture_native_appearance(parse_args(argv))
    print(f"NATIVE_APPEARANCE_CAPTURE_OK {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
