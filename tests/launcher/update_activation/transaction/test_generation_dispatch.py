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

"""Verify baseline-owned generation dispatch and recovery routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.generation_supervision import (
    GenerationStartupError,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE

from .support import _write_bundle_tree, _write_installed_layout


@pytest.mark.parametrize(
    "outcome", ["closed", "restart", "restart-zero", "failed-closed", "spawn-error"]
)
def test_dispatch_retains_baseline_authority_and_routes_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Keep one broker while recovering a selected process through existing actions."""
    from launcher.sugarsubstitute_launcher.generation_dispatch import (
        dispatch_selected_launcher,
    )

    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(staged, marker="candidate")
    assets = staged / "launcher-bin" / "launcher_assets"
    assets.mkdir()
    (assets / "launcher-contract.json").write_text(
        '{"schema_version": 1, "delegation_protocol": 1}'
    )
    selection = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)
    candidate = selection.publish(staged, version="1")
    selection.activate(candidate)
    layout = InstallLayout.from_root(root, target=WINDOWS_X64)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    owner = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None

    class GenerationProcess:
        """Replace the external process boundary while exercising native delegation."""

        def supervise(
            self,
            *,
            layout: InstallLayout,
            command: Sequence[str],
            environment: Mapping[str, str],
        ) -> int:
            """Verify selected image and credentials before simulating its terminal action."""
            assert Path(command[0]) == candidate.root / "SugarSubstitute.exe"
            assert f"--install-root={root}" in command
            assert environment["SUGAR_SUBSTITUTE_DELEGATED_LAUNCHER"] == "1"
            if outcome == "spawn-error":
                raise GenerationStartupError("selected executable unavailable")
            client = ApplicationSupervisorClient.connect_from_environment(
                dict(environment)
            )
            assert client is not None
            try:
                if outcome in {"restart", "restart-zero"}:
                    assert client.request_restart()
                    return 0 if outcome == "restart-zero" else 1
                return 1 if outcome == "failed-closed" else 0
            finally:
                client.close()

    fallbacks: list[bool] = []
    with owner:
        result = dispatch_selected_launcher(
            layout=layout,
            broker=owner,
            arguments=(),
            supervisor=GenerationProcess(),
            on_baseline_fallback=lambda: fallbacks.append(True),
        )
        expected = {"closed": 0, "failed-closed": 1}.get(outcome)
        assert result == expected
        assert fallbacks == (
            [True] if outcome in {"restart", "restart-zero", "spawn-error"} else []
        )
        assert selection.resolve().root == (
            candidate.root if outcome == "closed" else root
        )
        owner.bind_startup_presenter(lambda _: "baseline")
        assert (
            ApplicationInstanceBroker.elect(
                install_root=root,
                invocation=ApplicationInvocation.capture(["launcher"]),
            )
            is None
        )


@pytest.mark.parametrize(
    "contract",
    [None, "{}", "{bad", '{"schema_version": 1, "delegation_protocol": 999}'],
)
@pytest.mark.parametrize("rejection_writable", [True, False])
def test_incompatible_generation_keeps_working_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contract: str | None,
    rejection_writable: bool,
) -> None:
    """Never start a selected launcher that cannot share the elected owner."""
    from launcher.sugarsubstitute_launcher.generation_dispatch import (
        dispatch_selected_launcher,
    )

    root = _write_installed_layout(tmp_path / "installation")
    staged = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(staged, marker="historical")
    if contract is not None:
        assets = staged / "launcher-bin" / "launcher_assets"
        assets.mkdir()
        (assets / "launcher-contract.json").write_text(contract)
    selection = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE)
    candidate = selection.publish(staged, version="1")
    selection.activate(candidate)
    layout = InstallLayout.from_root(root, target=WINDOWS_X64)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    owner = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None

    if not rejection_writable:

        def reject_unwritable(self: LauncherBundleSelection, candidate: object) -> None:
            """Model a read-only rejection record without weakening read validation."""
            raise PermissionError("rejection record is read-only")

        monkeypatch.setattr(LauncherBundleSelection, "reject", reject_unwritable)

    class IncompatibleProcess:
        """Fail if an incompatible external executable is admitted."""

        def supervise(
            self,
            *,
            layout: InstallLayout,
            command: Sequence[str],
            environment: Mapping[str, str],
        ) -> int:
            """Require compatibility resolution before process creation."""
            pytest.fail("Incompatible generation was launched under the elected owner")

    with owner:
        assert (
            dispatch_selected_launcher(
                layout=layout,
                broker=owner,
                arguments=(),
                supervisor=IncompatibleProcess(),
            )
            is None
        )
        assert selection.resolve().root == (
            root if rejection_writable else candidate.root
        )
        owner.bind_startup_presenter(lambda _: "baseline")
        assert (
            ApplicationInstanceBroker.elect(
                install_root=root,
                invocation=ApplicationInvocation.capture(["launcher"]),
            )
            is None
        )
