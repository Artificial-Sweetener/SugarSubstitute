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

"""Verify an unreachable Windows launcher belongs to the failed installation."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from pathlib import Path
import sys

from launcher.sugarsubstitute_launcher.cli import (
    LauncherArgumentError,
    parse_launcher_args,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime_paths import (
    current_frozen_executable_path,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceEndpoint,
)
from sugarsubstitute_shared.application_instance_transport import (
    instance_endpoint,
    instance_identity,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity

_LOGGER = logging.getLogger(__name__)


def discover_previous_installed_instance(
    layout: InstallLayout,
    endpoint: ApplicationInstanceEndpoint | None,
) -> ProcessIdentity | None:
    """Discover an earlier owner only within the current packaged installation."""
    if sys.platform != "win32":
        return None
    executable = current_frozen_executable_path()
    if executable is None or executable.resolve() != layout.executable_path.resolve():
        return None
    if endpoint != instance_endpoint(instance_identity(layout.root)):
        return None
    from sugarsubstitute_shared.windows_application_processes import (
        find_previous_application_process,
    )

    scope = InstalledInvocationScope(layout)
    return find_previous_application_process(
        layout.executable_path, accepts_invocation=scope.accepts
    )


class InstalledInvocationScope:
    """Apply the launcher's authoritative argument grammar to its installation scope."""

    def __init__(self, layout: InstallLayout) -> None:
        """Keep the installation that the user's recovery action may affect."""
        self._root = layout.root.resolve()

    def accepts(self, arguments: Sequence[str], working_directory: Path) -> bool:
        """Exclude helpers, unrelated operations, and explicit alternative roots."""
        if not arguments:
            return False
        try:
            parsed = parse_launcher_args(arguments[1:], report_errors=False)
        except LauncherArgumentError:
            _LOGGER.warning("Could not verify an earlier launcher's invocation scope")
            return False
        if (
            parsed.headless_install
            or parsed.verify_release_connectivity
            or parsed.launcher_ui_child
            or parsed.crash_report_incident_id is not None
        ):
            return False
        if parsed.install_root is None:
            return True
        root = parsed.install_root
        if not root.is_absolute():
            root = working_directory / root
        return root.resolve() == self._root
