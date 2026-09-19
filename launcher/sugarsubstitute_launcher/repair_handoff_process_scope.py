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

"""Constrain repair handoff termination to installed supervisor and caller roles."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from launcher.sugarsubstitute_launcher.application_process_discovery import (
    InstalledInvocationScope,
)
from launcher.sugarsubstitute_launcher.cli import (
    LauncherArgumentError,
    parse_launcher_args,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


class RepairHandoffProcessScope:
    """Verify the launch intent of an exact caller recorded before repair handoff."""

    def __init__(self, layout: InstallLayout) -> None:
        """Bind the installation's process roles without retaining process state."""
        self._layout = layout
        self._owners = InstalledInvocationScope(layout)
        self._interpreters = {
            layout.runtime_python.resolve(),
            layout.runtime_gui_python.resolve(),
        }
        self._python_root = (layout.runtime_dir / "python").resolve()
        ui = layout.launcher_ui_executable_path
        self._ui = ui.resolve() if ui is not None else None

    def accepts_executable(self, executable: Path) -> bool:
        """Accept only managed runtime images and installed launcher roles."""
        image = executable.resolve()
        return (
            self._owners.accepts_executable(image)
            or image == self._ui
            or image in self._interpreters
            or (
                image.is_relative_to(self._python_root)
                and image.name.lower()
                in {"python", "python3", "python.exe", "pythonw.exe"}
            )
        )

    def accepts_invocation(
        self, executable: Path, arguments: Sequence[str], working_directory: Path
    ) -> bool:
        """Require the recorded caller's image, entrypoint and explicit installation."""
        if self._owners.accepts_invocation(executable, arguments, working_directory):
            return True
        if not arguments or not self.accepts_executable(executable):
            return False
        if self._owners.accepts_executable(executable):
            return False
        root_arguments = [
            argument.removeprefix("--install-root=")
            for argument in arguments[1:]
            if argument.startswith("--install-root=")
        ]
        if len(root_arguments) != 1 or not root_arguments[0]:
            return False
        root = Path(root_arguments[0])
        if not root.is_absolute():
            root = working_directory / root
        if root.resolve() != self._layout.root.resolve():
            return False
        if executable.resolve() == self._ui:
            try:
                parsed = parse_launcher_args(arguments[1:], report_errors=False)
            except LauncherArgumentError:
                return False
            return (
                parsed.launcher_ui_child
                and parsed.crash_report_incident_id is None
                and parsed.instance_recovery_request is None
            )
        if len(arguments) < 3:
            return False
        entrypoint = Path(arguments[1])
        if not entrypoint.is_absolute():
            entrypoint = working_directory / entrypoint
        return entrypoint.resolve() == self._layout.app_entrypoint.resolve()
