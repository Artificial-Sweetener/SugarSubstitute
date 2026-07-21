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

"""Define the supported ComfyUI and attached-Python compatibility floor."""

from __future__ import annotations

from dataclasses import dataclass
import re

from sugarsubstitute_shared.localization import app_text, render_source_application_text


class UnsupportedComfyPythonError(RuntimeError):
    """Report an attached Python below the mandatory node-pack floor."""


class UnsupportedComfyVersionError(RuntimeError):
    """Report a ComfyUI checkout below the supported release floor."""


@dataclass(frozen=True, slots=True)
class ComfyCompatibilityPolicy:
    """Own the explicit runtime floors promised by the installer."""

    minimum_comfyui_version: tuple[int, int, int] = (0, 15, 0)
    minimum_python_version: tuple[int, int] = (3, 12)

    @property
    def minimum_comfyui_label(self) -> str:
        """Return the public minimum ComfyUI version label."""

        return ".".join(str(part) for part in self.minimum_comfyui_version)

    @property
    def minimum_python_label(self) -> str:
        """Return the mandatory node-pack Python version label."""

        return ".".join(str(part) for part in self.minimum_python_version)

    def supports_comfyui(self, version: str) -> bool:
        """Return whether a ComfyUI version satisfies the checkout floor."""

        parsed = _semantic_triplet(version)
        return parsed is not None and parsed >= self.minimum_comfyui_version

    def require_supported_comfyui(self, version: str) -> None:
        """Reject a checkout below the supported ComfyUI release floor."""

        if self.supports_comfyui(version):
            return
        raise UnsupportedComfyVersionError(
            render_source_application_text(
                app_text(
                    "SugarSubstitute requires ComfyUI %1 or newer. "
                    "The selected checkout is ComfyUI %2.",
                    self.minimum_comfyui_label,
                    version,
                )
            )
        )

    def supports_python(self, version: str) -> bool:
        """Return whether a Python version satisfies mandatory node packs."""

        parsed = _major_minor(version)
        return parsed is not None and parsed >= self.minimum_python_version

    def require_supported_python(self, version: str) -> None:
        """Reject an attached runtime before any dependency mutation."""

        if self.supports_python(version):
            return
        raise UnsupportedComfyPythonError(
            render_source_application_text(
                app_text(
                    "SugarSubstitute requires Python %1 or newer for ComfyUI node packs. "
                    "The selected environment uses Python %2.",
                    self.minimum_python_label,
                    version,
                )
            )
        )


COMFY_COMPATIBILITY_POLICY = ComfyCompatibilityPolicy()


def _major_minor(version: str) -> tuple[int, int] | None:
    """Return a normalized major/minor tuple from a Python version string."""

    parts = version.split(".", maxsplit=2)
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _semantic_triplet(version: str) -> tuple[int, int, int] | None:
    """Return a leading semantic-version triplet with an optional `v` prefix."""

    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", version.strip())
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


__all__ = [
    "COMFY_COMPATIBILITY_POLICY",
    "ComfyCompatibilityPolicy",
    "UnsupportedComfyVersionError",
    "UnsupportedComfyPythonError",
]
