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

"""Verify Windows extended-length paths remain transparent to application code."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

import pytest
from PIL import Image
import pygit2

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.payload import safe_extract_zip
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_launcher import (
    _build_managed_launch_command,
)
from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    NativeSevenZipExtractionProcess,
)
from sugarsubstitute_shared.windows_long_paths import (
    ExternalLongPathCompatibilityError,
    WindowsPathComponentTooLongError,
    WindowsLongPath,
    external_long_path_error,
    extended_length_path,
    logical_path,
    operational_path,
)
from substitute.infrastructure.process.hidden_process_runner import run_command
from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control.clone_process import Pygit2CloneProcess


def test_extended_length_path_maps_drive_and_unc_paths() -> None:
    """Windows drive and UNC roots should use their required namespace forms."""

    assert extended_length_path(r"C:\deep\file.txt") == r"\\?\C:\deep\file.txt"
    assert (
        extended_length_path(r"\\server\share\deep\file.txt")
        == r"\\?\UNC\server\share\deep\file.txt"
    )


def test_extended_length_path_rejects_relative_paths() -> None:
    """Relative paths should fail before entering the minimally parsed namespace."""

    with pytest.raises(ValueError, match="must be absolute"):
        extended_length_path(Path("relative") / "file.txt")


def test_logical_path_removes_drive_and_unc_transport_prefixes() -> None:
    """Transport prefixes should never leak into user-visible path strings."""

    assert logical_path(r"\\?\C:\deep\file.txt") == r"C:\deep\file.txt"
    assert (
        logical_path(r"\\?\UNC\server\share\deep\file.txt")
        == r"\\server\share\deep\file.txt"
    )


@pytest.mark.platforms("windows")
def test_operational_path_preserves_logical_text_across_child_paths(
    tmp_path: Path,
) -> None:
    """Application text should stay normal while OS calls receive extended paths."""

    logical_root = tmp_path / "install"
    root = operational_path(logical_root)
    child = root / "user" / "projects"

    assert isinstance(root, WindowsLongPath)
    assert isinstance(child, WindowsLongPath)
    assert str(child) == str(logical_root / "user" / "projects")
    assert os.fspath(child) == extended_length_path(str(child))
    assert "\\\\?\\" not in str(child)


@pytest.mark.platforms("windows")
def test_operational_path_supports_owned_files_beyond_max_path(
    tmp_path: Path,
) -> None:
    """Owned filesystem operations should work beyond the legacy path limit."""

    root = operational_path(tmp_path / "long-path-root")
    deep_directory = root
    while len(str(deep_directory)) < 285:
        deep_directory /= "segment-0123456789abcdef"
    source = deep_directory / "source.txt"
    copied = deep_directory / "copied.txt"
    renamed = deep_directory / "renamed.txt"

    source.parent.mkdir(parents=True)
    source.write_text("long path", encoding="utf-8")
    shutil.copy2(source, copied)
    copied.replace(renamed)

    assert len(str(source)) > 260
    assert source.read_text(encoding="utf-8") == "long path"
    assert renamed.read_text(encoding="utf-8") == "long path"
    assert {path.name for path in deep_directory.iterdir()} == {
        "renamed.txt",
        "source.txt",
    }
    assert root.resolve() == root


@pytest.mark.platforms("windows")
def test_operational_path_rejects_an_unrepresentable_component(
    tmp_path: Path,
) -> None:
    """A single component beyond the filesystem limit should explain the limit."""

    with pytest.raises(WindowsPathComponentTooLongError, match="255 characters"):
        operational_path(tmp_path / ("x" * 256) / "file.txt")


@pytest.mark.platforms("windows")
def test_external_error_classifier_preserves_component_and_logical_path(
    tmp_path: Path,
) -> None:
    """Known third-party failures should retain actionable structured context."""

    long_path = tmp_path / ("segment" * 30) / ("nested" * 15)
    error = OSError("[WinError 206] The filename or extension is too long")

    classified = external_long_path_error(
        component="7-Zip",
        path=long_path,
        detail=error,
    )

    assert isinstance(classified, ExternalLongPathCompatibilityError)
    assert classified.component == "7-Zip"
    assert classified.path == long_path
    assert "WinError 206" in classified.detail


@pytest.mark.platforms("windows")
def test_hidden_python_process_runs_inside_long_working_directory(
    tmp_path: Path,
) -> None:
    """App-owned subprocess launches should receive extended executable and cwd paths."""

    working_directory = operational_path(tmp_path / "process")
    while len(str(working_directory)) < 285:
        working_directory /= "segment-0123456789abcdef"
    working_directory.mkdir(parents=True)
    proof_path = working_directory / "proof.txt"

    result = run_command(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('ok')",
            os.fspath(proof_path),
        ],
        cwd=working_directory,
        check=True,
    )

    assert result.returncode == 0
    assert proof_path.read_text(encoding="utf-8") == "ok"


@pytest.mark.platforms("windows")
def test_launcher_config_and_zip_payload_work_beyond_max_path(
    tmp_path: Path,
) -> None:
    """Installer-owned serialization and extraction should remain prefix-transparent."""

    install_root = operational_path(tmp_path / "install")
    while len(str(install_root)) < 285:
        install_root /= "segment-0123456789abcdef"
    layout = InstallLayout.from_root(install_root)
    config = LauncherConfig.from_layout(layout=layout)
    config.save(layout.config_path)
    archive_path = operational_path(tmp_path / "payload.zip")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/payload.txt", "payload")

    safe_extract_zip(zip_path=archive_path, destination_dir=layout.app_dir)

    config_text = layout.config_path.read_text(encoding="utf-8")
    assert "\\\\?\\" not in config_text
    assert json.loads(config_text)["install_root"] == str(layout.root)
    assert (layout.app_dir / "nested" / "payload.txt").read_text(
        encoding="utf-8"
    ) == "payload"


@pytest.mark.platforms("windows")
def test_pillow_round_trips_output_beyond_max_path(tmp_path: Path) -> None:
    """Pillow should honor the PathLike transport used by output persistence."""

    output_path = operational_path(tmp_path / "outputs")
    while len(str(output_path)) < 285:
        output_path /= "segment-0123456789abcdef"
    output_path /= "result.png"
    output_path.parent.mkdir(parents=True)

    Image.new("RGB", (11, 13), "purple").save(output_path)
    with Image.open(output_path) as image:
        assert image.size == (11, 13)


@pytest.mark.platforms("windows")
def test_managed_comfy_bootstrap_enters_long_workspace(tmp_path: Path) -> None:
    """The controlled Python bootstrap should restore Comfy's workspace semantics."""

    workspace = operational_path(tmp_path / "comfy")
    while len(str(workspace)) < 285:
        workspace /= "segment-0123456789abcdef"
    workspace.mkdir(parents=True)
    main_path = workspace / "main.py"
    main_path.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path('cwd-proof.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    command = _build_managed_launch_command(
        venv_python=Path(sys.executable),
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=workspace,
        manager_runtime=ComfyManagerRuntime(
            kind=ComfyManagerKind.LEGACY_CUSTOM_NODE,
            workspace=workspace,
            python_executable=Path(sys.executable),
        ),
    )

    result = run_command(command, cwd=workspace, check=True)

    assert result.returncode == 0
    assert (workspace / "cwd-proof.txt").read_text(encoding="utf-8") == (
        "--listen|127.0.0.1|--port|8188"
    )


@pytest.mark.platforms("windows")
def test_pygit2_clone_stages_and_promotes_to_long_destination(
    tmp_path: Path,
) -> None:
    """The libgit2 boundary should clone through a short app-controlled staging path."""

    source = tmp_path / "source-repository"
    source.mkdir()
    repository = pygit2.init_repository(source, initial_head="main")
    (source / "proof.txt").write_text("clone proof", encoding="utf-8")
    repository.index.add_all()
    repository.index.write()
    tree = repository.index.write_tree()
    signature = pygit2.Signature("SugarSubstitute Tests", "tests@example.invalid")
    repository.create_commit("HEAD", signature, signature, "proof", tree, [])
    target_root = operational_path(tmp_path / "clone-target")
    target = target_root
    while len(str(target)) < 285:
        target /= "segment-0123456789abcdef"
    target.parent.mkdir(parents=True)

    try:
        Pygit2CloneProcess(timeout_seconds=30).clone(str(source), target)

        assert (target / "proof.txt").read_text(encoding="utf-8") == "clone proof"
        assert (target / ".git").is_dir()
    finally:
        remove_app_owned_path(target_root)


@pytest.mark.platforms("windows")
def test_native_seven_zip_extracts_to_long_destination(tmp_path: Path) -> None:
    """Bundled 7-Zip should accept extended archive and destination arguments."""

    archive_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/proof.txt", "7zip proof")
    target_root = operational_path(tmp_path / "seven-zip-target")
    target = target_root
    while len(str(target)) < 285:
        target /= "segment-0123456789abcdef"
    target.mkdir(parents=True)

    try:
        process = NativeSevenZipExtractionProcess(timeout_seconds=30)
        process.extract(archive_path, target)

        assert (target / "nested" / "proof.txt").read_text(encoding="utf-8") == (
            "7zip proof"
        )
    finally:
        remove_app_owned_path(target_root)
