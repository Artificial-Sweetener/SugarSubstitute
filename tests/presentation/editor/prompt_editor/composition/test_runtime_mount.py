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

"""Verify ordered, single-publication prompt-editor runtime mounting."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from substitute.presentation.editor.prompt_editor.composition.core_runtime import (
    PromptEditorCoreRuntime,
)
from substitute.presentation.editor.prompt_editor.composition.feature_runtime import (
    PromptEditorFeatureRuntime,
)
from substitute.presentation.editor.prompt_editor.composition.host_runtime import (
    PromptEditorHostRuntime,
)
from substitute.presentation.editor.prompt_editor.composition.projection_factory import (
    PromptEditorProjectionCollaborators,
)
from substitute.presentation.editor.prompt_editor.runtime_mount import (
    PromptEditorRuntimeMount,
)
from substitute.presentation.editor.prompt_editor.shell import PromptEditorShellRuntime


def _runtime_graph() -> tuple[
    PromptEditorShellRuntime,
    PromptEditorProjectionCollaborators,
    PromptEditorCoreRuntime,
    PromptEditorFeatureRuntime,
    PromptEditorHostRuntime,
]:
    """Return identity-stable runtime doubles for mount lifecycle tests."""

    shell = cast(PromptEditorShellRuntime, object())
    projection = cast(PromptEditorProjectionCollaborators, object())
    core = cast(PromptEditorCoreRuntime, SimpleNamespace(projection=projection))
    features = cast(PromptEditorFeatureRuntime, object())
    host = cast(PromptEditorHostRuntime, object())
    return shell, projection, core, features, host


def test_runtime_phases_require_ordered_publication() -> None:
    """Reject access and publication before each prerequisite phase exists."""

    mount = PromptEditorRuntimeMount()
    shell, projection, core, features, host = _runtime_graph()

    with pytest.raises(RuntimeError, match="shell runtime is not mounted"):
        _ = mount.shell
    with pytest.raises(RuntimeError, match="shell runtime is not mounted"):
        mount.mount_projection(projection)

    mount.mount_shell(shell)
    mount.mount_projection(projection)
    mount.mount_core(core)
    mount.mount_features(features)
    mount.mount_host(host)

    assert mount.shell is shell
    assert mount.projection is projection
    assert mount.core is core
    assert mount.features is features
    assert mount.host is host


def test_runtime_phases_reject_duplicate_publication() -> None:
    """Preserve one authoritative identity for every mounted phase."""

    mount = PromptEditorRuntimeMount()
    shell, projection, core, features, host = _runtime_graph()
    mount.mount_shell(shell)
    mount.mount_projection(projection)
    mount.mount_core(core)
    mount.mount_features(features)
    mount.mount_host(host)

    with pytest.raises(RuntimeError, match="shell runtime is already mounted"):
        mount.mount_shell(shell)
    with pytest.raises(RuntimeError, match="projection runtime is already mounted"):
        mount.mount_projection(projection)
    with pytest.raises(RuntimeError, match="core runtime is already mounted"):
        mount.mount_core(core)
    with pytest.raises(RuntimeError, match="features runtime is already mounted"):
        mount.mount_features(features)
    with pytest.raises(RuntimeError, match="host runtime is already mounted"):
        mount.mount_host(host)


def test_core_runtime_must_own_the_published_projection() -> None:
    """Reject a split graph whose core and early projection identities differ."""

    mount = PromptEditorRuntimeMount()
    shell, projection, _, _, _ = _runtime_graph()
    different_projection = cast(PromptEditorProjectionCollaborators, object())
    mismatched_core = cast(
        PromptEditorCoreRuntime,
        SimpleNamespace(projection=different_projection),
    )
    mount.mount_shell(shell)
    mount.mount_projection(projection)

    with pytest.raises(RuntimeError, match="does not own the mounted projection"):
        mount.mount_core(mismatched_core)
