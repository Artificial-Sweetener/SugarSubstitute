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

"""Own onboarding filesystem selection and default-path policy."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QLineEdit, QWidget

from sugarsubstitute_shared.presentation.localization import (
    translate_application_text,
)

from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingTargetMode,
)


DirectoryChooser = Callable[[QWidget, str, str], str]


class OnboardingPathSelector:
    """Own file dialogs, selected values, and derived onboarding defaults."""

    def __init__(
        self,
        *,
        parent: QWidget,
        draft_provider: Callable[[], OnboardingDraft],
        install_root_edit: QLineEdit,
        managed_workspace_edit: QLineEdit,
        attached_workspace_edit: QLineEdit,
        model_root_edit: QLineEdit,
        output_root_edit: QLineEdit,
        validate_attached_python: Callable[[Path], None],
        directory_chooser: DirectoryChooser | None = None,
    ) -> None:
        """Store the presentation fields and application-state boundary."""

        self._parent = parent
        self._draft_provider = draft_provider
        self._install_root_edit = install_root_edit
        self._managed_workspace_edit = managed_workspace_edit
        self._attached_workspace_edit = attached_workspace_edit
        self._model_root_edit = model_root_edit
        self._output_root_edit = output_root_edit
        self._validate_attached_python = validate_attached_python
        self._directory_chooser = directory_chooser or QFileDialog.getExistingDirectory

    def browse_install_root(self) -> None:
        """Prompt for the visible installation root directory."""

        self._choose_directory(
            "Choose Installation Root",
            self._install_root_edit,
        )

    def browse_managed_workspace(self) -> None:
        """Prompt for the managed-local ComfyUI workspace directory."""

        self._choose_directory(
            "Choose Managed ComfyUI Folder",
            self._managed_workspace_edit,
        )

    def browse_attached_workspace(self) -> None:
        """Prompt for the existing local ComfyUI folder."""

        self._choose_directory(
            "Choose Existing ComfyUI Folder",
            self._attached_workspace_edit,
        )

    def browse_attached_python(self) -> None:
        """Prompt for an unusual attached environment's Python executable."""

        draft = self._draft_provider()
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self._parent,
            translate_application_text("Choose ComfyUI Python Executable"),
            str(draft.attached_workspace_path or ""),
            translate_application_text(
                "Python executable (python.exe python);;All files (*)"
            ),
        )
        if selected and draft.attached_workspace_path is not None:
            self._validate_attached_python(Path(selected).resolve())

    def browse_model_root(self) -> bool:
        """Prompt for the ComfyUI models folder and report explicit confirmation."""

        return self._choose_directory("Choose Models Folder", self._model_root_edit)

    def browse_output_root(self) -> None:
        """Prompt for the Substitute output folder."""

        self._choose_directory("Choose Output Folder", self._output_root_edit)

    def use_default_model_root(self) -> None:
        """Reset the models field to the selected local ComfyUI default."""

        self._model_root_edit.setText(str(self.default_model_root()))

    def use_default_output_root(self) -> None:
        """Reset the output field to Substitute's default output folder."""

        self._output_root_edit.setText(str(self.default_output_root()))

    def selected_model_root(self) -> Path:
        """Return the selected models folder from the folders page."""

        text = self._model_root_edit.text().strip()
        return Path(text).resolve() if text else self.default_model_root()

    def selected_output_root(self) -> Path:
        """Return the selected output folder from the folders page."""

        text = self._output_root_edit.text().strip()
        return Path(text).resolve() if text else self.default_output_root()

    def default_model_root(self) -> Path:
        """Return the default models folder for the selected local ComfyUI."""

        draft = self._draft_provider()
        if (
            draft.target_mode is OnboardingTargetMode.ATTACHED_LOCAL
            and draft.attached_workspace_path is not None
        ):
            return draft.attached_workspace_path / "models"
        return draft.managed_workspace_path / "models"

    def default_output_root(self) -> Path:
        """Return Substitute's default output folder for the install root."""

        return self._draft_provider().installation_root / "user" / "outputs"

    def _choose_directory(self, title: str, target: QLineEdit) -> bool:
        """Choose a directory, update its field, and report confirmation."""

        selected = self._directory_chooser(
            self._parent,
            translate_application_text(title),
            target.text(),
        )
        if selected:
            target.setText(selected)
            return True
        return False


__all__ = ["OnboardingPathSelector"]
