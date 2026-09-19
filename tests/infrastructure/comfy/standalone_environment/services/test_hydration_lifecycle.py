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

"""Keep interrupted standalone hydration outside the usable-workspace contract."""

from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
from collections.abc import Sequence

import pytest

from substitute.infrastructure.comfy.standalone_environment.directory_copy import (
    DirectoryCopyProgress,
)
from substitute.infrastructure.comfy.standalone_environment.environment_builder import (
    StandaloneVirtualEnvironmentBuilder,
)
from substitute.infrastructure.comfy.standalone_environment.layout import (
    ManagedStandaloneLayout,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.managed_validation import (
    is_workspace_installed,
    is_workspace_launchable,
)
from substitute.infrastructure.comfy.standalone_environment.hydration_state import (
    StandaloneHydrationState,
)
from substitute.infrastructure.comfy.standalone_environment.recovery import (
    StandaloneEnvironmentRecovery,
)


def _master_layout(tmp_path: Path) -> ManagedStandaloneLayout:
    """Create a tiny verified-master shape without a real Python dependency."""

    variant = (
        StandaloneVariantId.WINDOWS_CPU
        if os.name == "nt"
        else StandaloneVariantId.LINUX_NVIDIA
    )
    layout = ManagedStandaloneLayout(tmp_path / "workspace", variant)
    layout.workspace.mkdir()
    layout.manifest.parent.mkdir()
    layout.manifest.write_text(json.dumps({"id": variant.value}), encoding="utf-8")
    (layout.workspace / "main.py").write_text("# Comfy entrypoint", encoding="utf-8")
    for tool in (layout.master_python, layout.uv_executable):
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.write_bytes(b"runtime fixture")
    packages = (
        layout.master_environment / "Lib" / "site-packages"
        if os.name == "nt"
        else layout.master_environment / "lib" / "python3.13" / "site-packages"
    )
    packages.mkdir(parents=True)
    (packages / "required_package.py").write_text("VALUE = 1", encoding="utf-8")
    return layout


def _install_venv_boundary(
    monkeypatch: pytest.MonkeyPatch,
    layout: ManagedStandaloneLayout,
    *,
    legacy_probe_succeeds: bool = True,
) -> None:
    """Fake only bundled uv while exercising real hydration and filesystem state."""

    def create_venv(
        args: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Materialize the interpreter before its packages, as uv does."""

        if "-c" in args:
            return subprocess.CompletedProcess(
                args, 0 if legacy_probe_succeeds else 1, "", "bootstrap probe"
            )
        layout.virtual_python.parent.mkdir(parents=True, exist_ok=True)
        layout.virtual_python.write_bytes(b"runtime fixture")
        if os.name != "nt":
            (layout.virtual_python.parent / "python").write_bytes(b"runtime fixture")
        packages = (
            layout.virtual_environment / "Lib" / "site-packages"
            if os.name == "nt"
            else layout.virtual_environment / "lib" / "python3.13" / "site-packages"
        )
        packages.mkdir(parents=True)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", create_venv)


def test_workspace_is_not_usable_until_hydration_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interpreter must not publish readiness while package copying is active."""

    layout = _master_layout(tmp_path)
    _install_venv_boundary(monkeypatch, layout)
    observations: list[tuple[bool, bool]] = []

    def observe(_progress: DirectoryCopyProgress) -> None:
        """Observe the same readiness contract used by managed startup."""

        observations.append(
            (
                is_workspace_installed(layout.workspace),
                is_workspace_launchable(layout.workspace),
            )
        )

    StandaloneVirtualEnvironmentBuilder().build(layout, on_progress=observe)

    assert observations and all(state == (False, False) for state in observations)
    assert is_workspace_installed(layout.workspace)
    assert is_workspace_launchable(layout.workspace)
    assert (layout.virtual_site_packages() / "required_package.py").is_file()


def test_missing_master_packages_preserve_the_existing_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate the complete copy source before discarding a recoverable active venv."""

    layout = _master_layout(tmp_path)
    _install_venv_boundary(monkeypatch, layout)
    StandaloneVirtualEnvironmentBuilder().build(layout)
    StandaloneHydrationState(layout.workspace).begin()
    packages = layout.master_site_packages()
    (packages / "required_package.py").unlink()
    packages.rmdir()

    with pytest.raises(RuntimeError, match="site-packages"):
        StandaloneEnvironmentRecovery().resume(layout.workspace)

    assert (layout.virtual_site_packages() / "required_package.py").is_file()


def test_interrupted_hydration_remains_unusable_and_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unexpected interruption must preserve the master and prevent partial reuse."""

    layout = _master_layout(tmp_path)
    _install_venv_boundary(monkeypatch, layout)
    user_output = layout.workspace / "output" / "keep.png"
    user_output.parent.mkdir()
    user_output.write_bytes(b"user output")

    def interrupt(_progress: DirectoryCopyProgress) -> None:
        """Model shutdown arriving after the interpreter has been created."""

        raise RuntimeError("hydration interrupted")

    with pytest.raises(RuntimeError, match="hydration interrupted"):
        StandaloneVirtualEnvironmentBuilder().build(layout, on_progress=interrupt)

    assert not is_workspace_installed(layout.workspace)
    assert not is_workspace_launchable(layout.workspace)
    assert layout.master_python.is_file()
    assert user_output.read_bytes() == b"user output"

    StandaloneVirtualEnvironmentBuilder().build(layout)

    assert is_workspace_launchable(layout.workspace)
    assert user_output.read_bytes() == b"user output"


def test_recovery_resumes_a_durable_interrupted_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reopening must resume a promoted workspace even before uv created Python."""

    layout = _master_layout(tmp_path)
    _install_venv_boundary(monkeypatch, layout)
    StandaloneHydrationState(layout.workspace).begin()
    user_file = layout.workspace / "saved-work.json"
    user_file.write_text("keep", encoding="utf-8")

    assert StandaloneEnvironmentRecovery().resume(layout.workspace)
    assert is_workspace_launchable(layout.workspace)
    assert user_file.read_text(encoding="utf-8") == "keep"
    assert not StandaloneEnvironmentRecovery().resume(layout.workspace)


@pytest.mark.parametrize("legacy_probe_succeeds", [False, True])
def test_recovery_preserves_usable_legacy_and_repairs_interrupted_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_probe_succeeds: bool,
) -> None:
    """Pre-transaction installations must recover without replacing healthy venvs."""

    layout = _master_layout(tmp_path)
    layout.virtual_python.parent.mkdir(parents=True)
    layout.virtual_python.write_bytes(b"legacy Python")
    _install_venv_boundary(
        monkeypatch, layout, legacy_probe_succeeds=legacy_probe_succeeds
    )

    repaired = StandaloneEnvironmentRecovery().resume(layout.workspace)

    assert repaired is not legacy_probe_succeeds
    if legacy_probe_succeeds:
        assert layout.virtual_python.read_bytes() == b"legacy Python"
    else:
        assert (layout.virtual_site_packages() / "required_package.py").is_file()
        assert is_workspace_launchable(layout.workspace)


def test_recovery_leaves_unowned_workspace_untouched(tmp_path: Path) -> None:
    """A similar directory shape does not authorize standalone recovery."""

    sentinel = tmp_path / "notes.txt"
    sentinel.write_text("keep", encoding="utf-8")

    assert not StandaloneEnvironmentRecovery().resume(tmp_path)
    assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("record", ["{", '{"schema_version": 1, "phase": "hydrating"}'])
def test_unfinished_or_unreadable_transaction_recovers_before_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record: str
) -> None:
    """Invalid transaction evidence cannot authorize an otherwise present runtime."""

    layout = _master_layout(tmp_path)
    _install_venv_boundary(monkeypatch, layout)
    StandaloneVirtualEnvironmentBuilder().build(layout)
    transaction_path = layout.manifest.with_name("standalone-hydration.json")
    transaction_path.write_text(record, encoding="utf-8")

    assert not is_workspace_launchable(layout.workspace)
    assert StandaloneEnvironmentRecovery().resume(layout.workspace)
    assert is_workspace_launchable(layout.workspace)


def test_missing_master_cannot_destroy_the_existing_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recovery must validate its retained source before replacing the active venv."""

    layout = _master_layout(tmp_path)
    _install_venv_boundary(monkeypatch, layout)
    StandaloneVirtualEnvironmentBuilder().build(layout)
    StandaloneHydrationState(layout.workspace).begin()
    layout.master_python.unlink()

    with pytest.raises(RuntimeError, match="incomplete"):
        StandaloneEnvironmentRecovery().resume(layout.workspace)

    assert layout.virtual_python.read_bytes() == b"runtime fixture"
    assert (layout.virtual_site_packages() / "required_package.py").is_file()
