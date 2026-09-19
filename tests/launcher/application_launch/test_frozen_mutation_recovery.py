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

"""Qualify native frozen-writer recovery primitives without installed UI or user processes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import secrets
import socket
import sys

import pytest

from launcher.sugarsubstitute_launcher.application_instance_recovery import (
    terminate_verified_process,
)
from launcher.sugarsubstitute_launcher.instance_process_control import (
    open_instance_process,
)
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationBusyError,
    installation_mutation,
)
from sugarsubstitute_shared.installation_mutation_record import (
    mutation_rendezvous_path,
    read_mutation_record,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared.windows_file_users import WindowsFileUsers

pytestmark = pytest.mark.platforms("windows")


@dataclass(frozen=True)
class FixtureInvocationScope:
    """Authorize only the launched fixture's image, arguments, and working directory."""

    image: Path
    arguments: tuple[str, ...]
    directory: Path

    def accepts_executable(self, executable: Path) -> bool:
        """Match the independently observed native fixture image."""
        return executable.resolve() == self.image.resolve()

    def accepts_invocation(
        self, executable: Path, arguments: Sequence[str], working_directory: Path
    ) -> bool:
        """Exclude every other invocation of the same Python interpreter."""
        return (
            self.accepts_executable(executable)
            and tuple(arguments[1:]) == self.arguments
            and working_directory.resolve() == self.directory.resolve()
        )


def test_frozen_writer_recovery_preserves_reader_and_reclaims_native_lock(
    tmp_path: Path,
) -> None:
    """End the exact nonservicing writer and reclaim without deleting its rendezvous."""
    nonce = secrets.token_hex(16)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(15)
        arguments = (
            "-m",
            "tests.launcher.application_launch.mutation_owner_process",
            str(tmp_path),
            str(listener.getsockname()[1]),
            nonce,
        )
        family, log = spawn_supervised_process(
            [sys.executable, *arguments], startup_log_path=tmp_path / "writer.log"
        )
        try:
            channel, _address = listener.accept()
            with channel:
                channel.settimeout(15)
                with channel.makefile("rb") as response:
                    ready = json.loads(response.readline(4096))
                assert ready["nonce"] == nonce
                candidate = read_mutation_record(tmp_path)
                assert candidate is not None
                assert candidate.process.pid == ready["pid"]
                with open_instance_process(candidate.process.pid) as process:
                    identity = ProcessIdentity(
                        candidate.process.pid, process.create_time()
                    )
                    scope = FixtureInvocationScope(
                        Path(process.exe()), arguments, Path.cwd()
                    )
                    assert scope.accepts_invocation(
                        Path(process.exe()), process.cmdline(), Path(process.cwd())
                    )
                    assert (
                        abs(identity.created_at - candidate.process.created_at)
                        < 0.000001
                    )
                rendezvous = mutation_rendezvous_path(tmp_path)
                inode = rendezvous.stat().st_ino
                with rendezvous.open("rb") as reader:
                    users = WindowsFileUsers().snapshot(rendezvous)
                    assert any(user.pid == os.getpid() for user in users)
                    assert identity in users
                    with pytest.raises(InstallationMutationBusyError) as busy:
                        with installation_mutation(tmp_path):
                            pass
                    assert busy.value.owner_record == candidate
                    assert not terminate_verified_process(
                        identity,
                        scope=replace(scope, arguments=(*arguments[:-1], "wrong")),
                    )
                    with pytest.raises(InstallationMutationBusyError):
                        with installation_mutation(tmp_path):
                            pass
                    assert terminate_verified_process(identity, scope=scope)
                    family.wait(timeout=10)
                    assert read_mutation_record(tmp_path) == candidate
                    assert not reader.closed
                    with installation_mutation(tmp_path):
                        successor = read_mutation_record(tmp_path)
                        assert successor is not None
                        assert successor.process.pid == os.getpid()
                        assert successor.operation_id != candidate.operation_id
                    assert read_mutation_record(tmp_path) is None
                    assert rendezvous.stat().st_ino == inode
        finally:
            if family.poll() is None:
                family.kill()
            family.wait(timeout=10)
            assert family.poll() is not None, log.read_text(encoding="utf-8")
