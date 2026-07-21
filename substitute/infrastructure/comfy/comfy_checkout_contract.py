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

"""Capture immutable dependency contracts from a ComfyUI checkout."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from substitute.domain.comfy_compatibility import COMFY_COMPATIBILITY_POLICY


@dataclass(frozen=True, slots=True)
class ComfyCheckoutSnapshot:
    """Describe the authoritative version and dependency content of a checkout."""

    version: str
    comfy_requirements_digest: str
    manager_requirements_digest: str


@dataclass(frozen=True, slots=True)
class ComfyCheckoutContract:
    """Read supported ComfyUI contract files without importing checkout code."""

    workspace: Path

    @property
    def version_path(self) -> Path:
        """Return the generated upstream version module path."""

        return self.workspace / "comfyui_version.py"

    @property
    def requirements_path(self) -> Path:
        """Return the checkout-owned ComfyUI requirements path."""

        return self.workspace / "requirements.txt"

    @property
    def manager_requirements_path(self) -> Path:
        """Return the checkout-owned Manager requirements path."""

        return self.workspace / "manager_requirements.txt"

    def capture(self) -> ComfyCheckoutSnapshot:
        """Return validated content evidence for the current checkout."""

        version = self._read_literal_version()
        COMFY_COMPATIBILITY_POLICY.require_supported_comfyui(version)
        return ComfyCheckoutSnapshot(
            version=version,
            comfy_requirements_digest=_content_digest(self.requirements_path),
            manager_requirements_digest=_content_digest(self.manager_requirements_path),
        )

    def _read_literal_version(self) -> str:
        """Read the generated literal version without executing checkout code."""

        try:
            source = self.version_path.read_text(encoding="utf-8")
            module = ast.parse(source, filename=str(self.version_path))
        except (OSError, SyntaxError) as error:
            raise RuntimeError(
                f"Could not read ComfyUI version contract: {self.version_path}"
            ) from error
        versions: list[str] = []
        for statement in module.body:
            if not isinstance(statement, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in statement.targets
            ):
                continue
            if isinstance(statement.value, ast.Constant) and isinstance(
                statement.value.value, str
            ):
                versions.append(statement.value.value)
        if len(versions) != 1:
            raise RuntimeError(
                "ComfyUI version contract must contain exactly one literal "
                "__version__ assignment."
            )
        return versions[0]


def _content_digest(path: Path) -> str:
    """Return a stable SHA-256 digest for one required contract file."""

    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise RuntimeError(f"Could not read ComfyUI contract file: {path}") from error


__all__ = ["ComfyCheckoutContract", "ComfyCheckoutSnapshot"]
