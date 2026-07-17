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

"""Tests for attached Comfy preparation ownership and interpreter handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
)
from substitute.infrastructure.comfy import attached_install


def test_attached_preparation_passes_one_verified_python_to_every_consumer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manager, nodepacks, and SugarCubes should share the selected binding."""

    workspace = tmp_path / "ComfyUI"
    executable = tmp_path / "outside" / "python.exe"
    binding = ComfyPythonBinding(
        executable=executable,
        version="3.13",
        architecture="AMD64",
        prefix=executable.parent,
        base_prefix=executable.parent,
        source=ComfyPythonSelectionSource.USER_SELECTED,
    )
    calls: list[tuple[str, Path | None]] = []
    monkeypatch.setattr(
        attached_install,
        "resolve_attached_comfy_python",
        lambda *_args, **_kwargs: binding,
    )

    def record(name: str) -> Any:
        """Build one dependency consumer that records its explicit Python."""

        def operation(_workspace: Path, **kwargs: object) -> None:
            calls.append((name, cast(Path | None, kwargs.get("python_executable"))))

        return operation

    monkeypatch.setattr(
        attached_install, "ensure_attached_workspace_manager", record("manager")
    )
    monkeypatch.setattr(
        attached_install, "ensure_core_comfy_nodepacks", record("nodepacks")
    )
    monkeypatch.setattr(
        attached_install,
        "run_sugarcubes_baseline_maintenance",
        record("sugarcubes"),
    )
    monkeypatch.setattr(attached_install, "detect_hardware", lambda: object())
    monkeypatch.setattr(
        attached_install,
        "reconcile_managed_acceleration_stack",
        lambda **kwargs: calls.append(
            ("acceleration", cast(Path, kwargs["python_executable"]))
        ),
    )

    result = attached_install.prepare_attached_comfy_setup(
        workspace=workspace,
        python_executable=executable,
    )

    assert result is binding
    assert calls == [
        ("manager", executable),
        ("nodepacks", executable),
        ("sugarcubes", executable),
        ("acceleration", executable),
    ]


def test_manager_provisioner_has_no_private_python_resolver() -> None:
    """Manager must use the shared resolver rather than owning candidate policy."""

    source = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "manager_provisioner.py"
    ).read_text(encoding="utf-8")

    assert "def _resolve_workspace_python" not in source


def test_attached_preparation_applies_model_root_after_backend_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached setup should configure models after required nodepacks exist."""

    workspace = tmp_path / "ComfyUI"
    executable = tmp_path / "python.exe"
    model_root = tmp_path / "SharedModels"
    binding = ComfyPythonBinding(
        executable=executable,
        version="3.13",
        architecture="AMD64",
        prefix=executable.parent,
        base_prefix=executable.parent,
        source=ComfyPythonSelectionSource.USER_SELECTED,
    )
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        attached_install,
        "resolve_attached_comfy_python",
        lambda *_args, **_kwargs: binding,
    )
    monkeypatch.setattr(
        attached_install,
        "ensure_attached_workspace_manager",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        attached_install,
        "ensure_core_comfy_nodepacks",
        lambda *_args, **_kwargs: calls.append(("nodepacks", None)),
    )
    monkeypatch.setattr(
        attached_install,
        "configure_backend_model_root",
        lambda **kwargs: calls.append(("model-root", kwargs)),
    )
    monkeypatch.setattr(
        attached_install,
        "run_sugarcubes_baseline_maintenance",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(attached_install, "detect_hardware", lambda: object())
    monkeypatch.setattr(
        attached_install,
        "reconcile_managed_acceleration_stack",
        lambda **_kwargs: None,
    )

    attached_install.prepare_attached_comfy_setup(
        workspace=workspace,
        python_executable=executable,
        model_root=model_root,
        configure_model_root=True,
    )

    assert calls == [
        ("nodepacks", None),
        (
            "model-root",
            {
                "workspace": workspace,
                "python_executable": executable,
                "model_root": model_root,
            },
        ),
    ]
