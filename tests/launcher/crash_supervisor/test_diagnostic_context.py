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

"""Verify supervisor diagnostics identify products and systems before launch."""

from __future__ import annotations

from pathlib import Path

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher import crash_diagnostic_context
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord


class _Memory:
    """Provide the physical-memory field used by the bounded collector."""

    total = 64 * 1024**3


def test_collector_reports_authoritative_versions_and_basic_system_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A supervisor snapshot must be actionable without application cooperation."""

    layout = InstallLayout.from_root(tmp_path / "install")
    version_path = layout.app_dir / "substitute" / "_version.py"
    version_path.parent.mkdir(parents=True)
    version_path.write_text('__version__ = "0.24.2"\n', encoding="utf-8")
    LauncherUpdateState(installed_app_version="0.24.2").save(layout.state_path)
    LauncherInstallationRecord(version="0.24.2", target_key="windows-x64").save(
        layout.launcher_installation_path
    )
    comfy_root = layout.root / "comfyui"
    comfy_root.mkdir()
    (comfy_root / "comfyui_version.py").write_text(
        '__version__ = "0.28.0"\n', encoding="utf-8"
    )
    git_dir = comfy_root / ".git"
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs" / "heads" / "main").write_text(
        "0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        crash_diagnostic_context, "_nvidia_gpu_names", lambda: "NVIDIA Test GPU"
    )
    monkeypatch.setattr(psutil, "virtual_memory", lambda: _Memory())

    context = crash_diagnostic_context.collect_crash_diagnostic_context(layout)

    assert context.substitute_version.value == "0.24.2"
    assert context.substitute_release_version.value == "0.24.2"
    assert context.supervising_launcher_version.value is not None
    assert context.installed_launcher_version.value == "0.24.2"
    assert context.comfyui_version.value == "0.28.0"
    assert context.comfyui_commit.value == "0123456789abcdef0123456789abcdef01234567"
    assert context.operating_system.value
    assert context.system_architecture.value
    assert context.python_version.value
    assert context.python_architecture.value in {"32-bit", "64-bit"}
    assert context.logical_processor_count.value
    assert context.physical_memory.value == "68719476736 bytes (64.0 GiB)"
    assert context.gpu.value == "NVIDIA Test GPU"
    assert context.readiness_schema.value == "5"


def test_collector_names_every_unavailable_product_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Damaged metadata must remain diagnostic evidence rather than abort startup."""

    layout = InstallLayout.from_root(tmp_path / "damaged-install")

    def unavailable_gpu() -> str:
        """Model a host with no bounded GPU provider."""

        raise ValueError("no GPU provider")

    monkeypatch.setattr(
        crash_diagnostic_context,
        "_nvidia_gpu_names",
        unavailable_gpu,
    )

    context = crash_diagnostic_context.collect_crash_diagnostic_context(layout)

    for value in (
        context.substitute_version,
        context.substitute_release_version,
        context.installed_launcher_version,
        context.comfyui_version,
        context.comfyui_commit,
        context.gpu,
    ):
        assert value.value is None
        assert value.unavailable_reason
        assert value.display_value.startswith("unavailable (")


def test_collector_resolves_linked_checkout_and_packed_comfyui_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ComfyUI identity must survive worktree and packed-reference layouts."""

    layout = InstallLayout.from_root(tmp_path / "install")
    comfy_root = layout.root / "comfyui"
    comfy_root.mkdir(parents=True)
    metadata = layout.root / "comfy-git-metadata"
    metadata.mkdir()
    (comfy_root / ".git").write_text(
        "gitdir: ../comfy-git-metadata\n",
        encoding="utf-8",
    )
    (metadata / "HEAD").write_text("ref: refs/heads/canary\n", encoding="utf-8")
    (metadata / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        "abcdef0123456789abcdef0123456789abcdef01 refs/heads/canary\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        crash_diagnostic_context, "_nvidia_gpu_names", lambda: "Test GPU"
    )

    context = crash_diagnostic_context.collect_crash_diagnostic_context(layout)

    assert context.comfyui_commit.value == ("abcdef0123456789abcdef0123456789abcdef01")
    assert context.comfyui_commit.unavailable_reason is None
