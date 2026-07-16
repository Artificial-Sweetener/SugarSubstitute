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

"""Tests for attached Comfy Python discovery, probing, and persistence."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonCandidate,
    ComfyPythonResolutionError,
    ComfyPythonResolutionFailure,
    ComfyPythonSelectionSource,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
)
from substitute.infrastructure.comfy.workspace_python_discovery import (
    discover_attached_comfy_python,
    probe_comfy_python,
    resolve_attached_comfy_python,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    attached_comfy_python_candidates,
)
from substitute.infrastructure.onboarding.file_comfy_target_repository import (
    FileComfyTargetConfigurationRepository,
)


def test_candidates_cover_portable_sibling_runtime(tmp_path: Path) -> None:
    """Portable Comfy layouts should find Python beside the ComfyUI folder."""

    workspace = tmp_path / "ComfyUI_windows_portable" / "ComfyUI"
    expected = workspace.parent / "python_embeded" / "python.exe"

    candidates = attached_comfy_python_candidates(
        workspace,
        environment={},
        platform_name="nt",
    )

    assert expected in {candidate.executable for candidate in candidates}


def test_candidates_cover_posix_virtualenv_layouts(tmp_path: Path) -> None:
    """Linux and macOS source layouts should expose workspace and parent venvs."""

    workspace = tmp_path / "portable" / "ComfyUI"

    candidates = attached_comfy_python_candidates(
        workspace,
        environment={},
        platform_name="posix",
    )

    paths = {candidate.executable for candidate in candidates}
    assert workspace / ".venv" / "bin" / "python" in paths
    assert workspace / "venv" / "bin" / "python" in paths
    assert workspace.parent / ".venv" / "bin" / "python" in paths


def test_candidates_ignore_unrelated_active_environment(tmp_path: Path) -> None:
    """Substitute's own environment must not become attached Comfy Python."""

    workspace = tmp_path / "ComfyUI"
    unrelated = tmp_path / "Substitute" / ".venv"

    candidates = attached_comfy_python_candidates(
        workspace,
        environment={"VIRTUAL_ENV": str(unrelated)},
        platform_name="nt",
    )

    assert unrelated / "Scripts" / "python.exe" not in {
        candidate.executable for candidate in candidates
    }


def test_probe_records_verified_interpreter_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A successful read-only probe should produce complete persisted evidence."""

    workspace = _workspace(tmp_path)
    executable = _file(tmp_path / "external" / "python.exe")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "executable": str(executable),
                    "prefix": str(executable.parent),
                    "base_prefix": str(executable.parent.parent),
                    "version": "3.13.7",
                    "architecture": "AMD64",
                    "modules": {"comfy": True, "torch": True, "aiohttp": True},
                }
            ),
            stderr="",
        ),
    )

    result = probe_comfy_python(
        workspace,
        executable,
        source=ComfyPythonSelectionSource.USER_SELECTED,
    )

    assert result.binding is not None
    assert result.binding.executable == executable
    assert result.binding.source is ComfyPythonSelectionSource.USER_SELECTED


def test_probe_classifies_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A stuck interpreter should time out without blocking setup indefinitely."""

    workspace = _workspace(tmp_path)
    executable = _file(workspace / ".venv" / "Scripts" / "python.exe")

    def raise_timeout(*_args: object, **_kwargs: object) -> object:
        """Simulate a Python process that never answers."""

        raise subprocess.TimeoutExpired(cmd=str(executable), timeout=0.01)

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = probe_comfy_python(workspace, executable, timeout_seconds=0.01)

    assert result.binding is None
    assert result.failure == "Python probe timed out after 0.01 seconds."


def test_discovery_requires_choice_for_equally_credible_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Two equally strong verified candidates should never be chosen arbitrarily."""

    workspace = _workspace(tmp_path)
    first = _file(tmp_path / "first" / "python.exe")
    second = _file(tmp_path / "second" / "python.exe")
    candidates = (
        ComfyPythonCandidate(first, "first", 10),
        ComfyPythonCandidate(second, "second", 10),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.workspace_python_discovery.attached_comfy_python_candidates",
        lambda *_args, **_kwargs: candidates,
    )

    def fake_probe(
        _workspace_path: Path,
        candidate: ComfyPythonCandidate,
        **_kwargs: object,
    ) -> object:
        """Return verified evidence for each supplied candidate."""

        from substitute.domain.onboarding import ComfyPythonProbeResult

        binding = ComfyPythonBinding(
            executable=candidate.executable,
            version="3.13",
            architecture="AMD64",
            prefix=candidate.executable.parent,
            base_prefix=candidate.executable.parent,
            source=ComfyPythonSelectionSource.DISCOVERED,
        )
        return ComfyPythonProbeResult(candidate, binding, None)

    monkeypatch.setattr(
        "substitute.infrastructure.comfy.workspace_python_discovery.probe_comfy_python",
        fake_probe,
    )

    result = discover_attached_comfy_python(workspace)

    assert result.binding is None
    assert tuple(item.executable for item in result.ambiguous_bindings) == (
        first,
        second,
    )


def test_explicit_selection_failure_requests_browse(
    tmp_path: Path,
) -> None:
    """Missing automatic candidates should give the user a direct escape hatch."""

    workspace = _workspace(tmp_path)

    with pytest.raises(ComfyPythonResolutionError, match="Browse") as error:
        resolve_attached_comfy_python(workspace)

    assert error.value.reason is ComfyPythonResolutionFailure.AUTOMATIC_DISCOVERY_FAILED


def test_explicit_invalid_selection_has_typed_failure(tmp_path: Path) -> None:
    """A rejected Browse selection should preserve its distinct recovery reason."""

    workspace = _workspace(tmp_path)
    missing = tmp_path / "unusual" / "python.exe"

    with pytest.raises(ComfyPythonResolutionError) as error:
        resolve_attached_comfy_python(
            workspace,
            explicit_executable=missing,
        )

    assert error.value.reason is ComfyPythonResolutionFailure.EXPLICIT_SELECTION_INVALID
    assert "does not exist" in error.value.detail


def test_missing_main_has_typed_workspace_failure(tmp_path: Path) -> None:
    """A non-Comfy folder should be distinguished from interpreter discovery."""

    workspace = tmp_path / "not-comfy"

    with pytest.raises(ComfyPythonResolutionError) as error:
        resolve_attached_comfy_python(workspace)

    assert error.value.reason is ComfyPythonResolutionFailure.WORKSPACE_INVALID
    assert "main.py" in error.value.detail


def test_target_repository_round_trips_verified_binding(tmp_path: Path) -> None:
    """The exact verified interpreter should survive application restarts."""

    installation = InstallationConfiguration.create_default(tmp_path / "install")
    repository = FileComfyTargetConfigurationRepository(installation)
    binding = ComfyPythonBinding(
        executable=tmp_path / "python.exe",
        version="3.13.7",
        architecture="AMD64",
        prefix=tmp_path,
        base_prefix=tmp_path,
        source=ComfyPythonSelectionSource.USER_SELECTED,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=False,
        launch_owned=True,
        python_binding=binding,
    )

    repository.save(target)

    assert repository.load() == target


def _workspace(root: Path) -> Path:
    """Create the minimum stopped Comfy source layout needed by a probe."""

    workspace = root / "ComfyUI"
    _file(workspace / "main.py")
    return workspace


def _file(path: Path) -> Path:
    """Create and return one fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path.resolve()
