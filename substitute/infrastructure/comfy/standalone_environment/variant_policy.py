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

"""Map managed install targets to published standalone environment variants."""

from __future__ import annotations

from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)


_VARIANT_BY_TARGET = {
    ManagedInstallTarget.WINDOWS_NVIDIA: StandaloneVariantId.WINDOWS_NVIDIA,
    ManagedInstallTarget.WINDOWS_AMD: StandaloneVariantId.WINDOWS_AMD,
    ManagedInstallTarget.WINDOWS_INTEL_XPU: StandaloneVariantId.WINDOWS_INTEL_XPU,
    ManagedInstallTarget.WINDOWS_CPU: StandaloneVariantId.WINDOWS_CPU,
    ManagedInstallTarget.LINUX_NVIDIA: StandaloneVariantId.LINUX_NVIDIA,
    ManagedInstallTarget.LINUX_AMD: StandaloneVariantId.LINUX_AMD,
    ManagedInstallTarget.LINUX_INTEL_XPU: StandaloneVariantId.LINUX_INTEL_XPU,
    ManagedInstallTarget.MACOS_APPLE_SILICON: StandaloneVariantId.MACOS_MPS,
}


def standalone_variant_for_target(
    target: ManagedInstallTarget,
) -> StandaloneVariantId:
    """Return the currently published environment variant for one target."""

    try:
        return _VARIANT_BY_TARGET[target]
    except KeyError as error:
        raise ValueError(
            f"Comfy Desktop does not publish a standalone environment for {target.value}."
        ) from error
