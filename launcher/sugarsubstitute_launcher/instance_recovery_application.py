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

"""Own the Qt application lifetime for explicit instance recovery."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


def run_instance_recovery_window(
    *,
    layout: InstallLayout,
    request_path: Path,
    locale_override: str | None,
) -> int:
    """Present one supervisor-requested recovery modal in the Qt child."""

    from PySide6.QtWidgets import QApplication

    from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
        InstanceRecoveryRequest,
    )
    from launcher.sugarsubstitute_launcher.localization import (
        build_launcher_localization_runtime,
    )
    from launcher.sugarsubstitute_launcher.ui.instance_recovery_dialog import (
        present_instance_recovery_dialog,
    )

    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(sys.argv[:1])
    request = InstanceRecoveryRequest.read(request_path.resolve())
    localization = build_launcher_localization_runtime(
        cast(Any, application),
        layout=layout,
        locale_override=locale_override,
    )
    try:
        action = present_instance_recovery_dialog(
            layout=layout,
            reason=request.reason,
        )
        request.write_response(action)
        return 0
    finally:
        localization.manager.close()
        if owns_application:
            cast(Any, application).quit()
