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

"""Host independently supervised repair without entering ordinary installer routing."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys


def run_repair_ui_invocation(arguments: Sequence[str]) -> int | None:
    """Accept only one dedicated repair UI request and require native supervision."""
    prefix = "--repair-ui-request="
    values = [
        argument.removeprefix(prefix)
        for argument in arguments
        if argument.startswith(prefix)
    ]
    if not values:
        return None
    if len(arguments) != 1 or len(values) != 1 or not values[0]:
        raise ValueError("Repair UI requires exactly one non-empty request path.")
    return _run_repair_window(Path(values[0]))


def _run_repair_window(request_path: Path) -> int:
    """Paint the recovery surface before starting any filesystem mutation."""
    from PySide6.QtWidgets import QApplication
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.localization import (
        build_launcher_localization_runtime,
    )
    from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
    from launcher.sugarsubstitute_launcher.repair_helper import (
        load_prepared_repair_request,
    )
    from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface
    from sugarsubstitute_shared.qt_application_instance_control import (
        start_application_instance_control,
        stop_application_instance_control,
    )
    from sugarsubstitute_shared.qt_surface_presentation import run_after_surface_paint
    from sugarsubstitute_shared.qt_surface_readiness import (
        schedule_surface_readiness_receipt,
    )

    request = load_prepared_repair_request(request_path)
    application = QApplication(sys.argv[:1])
    layout = InstallLayout.from_root(
        request.install_root, target=launcher_target_for_key(request.target_key)
    )
    localization = build_launcher_localization_runtime(
        application, layout=layout, locale_override=None
    )
    try:
        control = start_application_instance_control()
        if control is None:
            raise RuntimeError("Repair UI requires an active application supervisor.")
        from launcher.sugarsubstitute_launcher.ui.repair_controller import (
            RepairController,
        )
        from launcher.sugarsubstitute_launcher.ui.repair_window import RepairWindow

        window = RepairWindow()
        controller = RepairController(window, request)
        schedule_surface_readiness_receipt(
            surface=ApplicationReadinessSurface.LAUNCHER_WINDOW, window=window
        )
        run_after_surface_paint(window, controller.start)
        window.show()
        return int(application.exec())
    finally:
        stop_application_instance_control()
        localization.manager.close()
