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

"""Own the staged collaborator graph mounted on one prompt-editor widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from .composition.core_runtime import PromptEditorCoreRuntime
    from .composition.feature_runtime import PromptEditorFeatureRuntime
    from .composition.host_runtime import PromptEditorHostRuntime
    from .composition.projection_factory import PromptEditorProjectionCollaborators
    from .shell import PromptEditorShellRuntime

_MountedRuntime = TypeVar("_MountedRuntime")


class PromptEditorRuntimeMount:
    """Publish each runtime phase once while preserving construction invariants."""

    def __init__(self) -> None:
        """Create an empty mount awaiting ordered runtime publication."""

        self._shell: PromptEditorShellRuntime | None = None
        self._projection: PromptEditorProjectionCollaborators | None = None
        self._core: PromptEditorCoreRuntime | None = None
        self._features: PromptEditorFeatureRuntime | None = None
        self._host: PromptEditorHostRuntime | None = None

    @property
    def shell(self) -> PromptEditorShellRuntime:
        """Return the mounted QFluent shell runtime."""

        return _require_mounted(self._shell, phase="shell")

    @property
    def projection(self) -> PromptEditorProjectionCollaborators:
        """Return the mounted projection collaborators."""

        return _require_mounted(self._projection, phase="projection")

    @property
    def projection_or_none(self) -> PromptEditorProjectionCollaborators | None:
        """Return projection collaborators when their construction phase has mounted."""

        return self._projection

    @property
    def core(self) -> PromptEditorCoreRuntime:
        """Return the mounted core runtime."""

        return _require_mounted(self._core, phase="core")

    @property
    def core_or_none(self) -> PromptEditorCoreRuntime | None:
        """Return the core runtime when its construction phase has mounted."""

        return self._core

    @property
    def features(self) -> PromptEditorFeatureRuntime:
        """Return the mounted feature runtime."""

        return _require_mounted(self._features, phase="features")

    @property
    def host(self) -> PromptEditorHostRuntime:
        """Return the mounted host-integration runtime."""

        return _require_mounted(self._host, phase="host")

    @property
    def host_or_none(self) -> PromptEditorHostRuntime | None:
        """Return host integration when its construction phase has mounted."""

        return self._host

    def mount_shell(self, shell: PromptEditorShellRuntime) -> None:
        """Publish the shell as the first mounted runtime phase."""

        self._require_unmounted(self._shell, phase="shell")
        self._shell = shell

    def mount_projection(
        self,
        projection: PromptEditorProjectionCollaborators,
    ) -> None:
        """Publish projection collaborators after shell construction."""

        _require_mounted(self._shell, phase="shell")
        self._require_unmounted(self._projection, phase="projection")
        self._projection = projection

    def mount_core(self, core: PromptEditorCoreRuntime) -> None:
        """Publish the core runtime that owns the mounted projection graph."""

        projection = _require_mounted(self._projection, phase="projection")
        self._require_unmounted(self._core, phase="core")
        if core.projection is not projection:
            raise RuntimeError(
                "Prompt-editor core runtime does not own the mounted projection"
            )
        self._core = core

    def mount_features(self, features: PromptEditorFeatureRuntime) -> None:
        """Publish feature presentation after core composition."""

        _require_mounted(self._core, phase="core")
        self._require_unmounted(self._features, phase="features")
        self._features = features

    def mount_host(self, host: PromptEditorHostRuntime) -> None:
        """Publish host integration after every collaborator owner exists."""

        _require_mounted(self._features, phase="features")
        self._require_unmounted(self._host, phase="host")
        self._host = host

    @staticmethod
    def _require_unmounted(value: object | None, *, phase: str) -> None:
        """Reject duplicate publication of one runtime phase."""

        if value is not None:
            raise RuntimeError(f"Prompt-editor {phase} runtime is already mounted")


def _require_mounted(
    value: _MountedRuntime | None,
    *,
    phase: str,
) -> _MountedRuntime:
    """Return one mounted runtime phase or report invalid lifecycle access."""

    if value is None:
        raise RuntimeError(f"Prompt-editor {phase} runtime is not mounted")
    return value


__all__ = ["PromptEditorRuntimeMount"]
