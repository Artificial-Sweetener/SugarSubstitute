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

"""Verify generation listener dispatch ownership in application composition."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap import composition


def test_generation_listener_dispatcher_is_constructed_before_worker_factory() -> None:
    """Listener factories should capture an owner-thread-created dispatcher."""

    source = Path(composition.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    listener_dispatcher = assignments["generation_listener_dispatcher"]
    assert isinstance(listener_dispatcher, ast.Call)
    assert isinstance(listener_dispatcher.func, ast.Name)
    assert listener_dispatcher.func.id == "QtOwnerThreadDispatcher"

    listener_factory = assignments["comfy_gateway"]
    assert isinstance(listener_factory, ast.Call)
    listener_task_factory = next(
        keyword.value
        for keyword in listener_factory.keywords
        if keyword.arg == "listener_task_factory"
    )
    assert isinstance(listener_task_factory, ast.Lambda)
    dispatcher_keywords = [
        keyword
        for node in ast.walk(listener_task_factory.body)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "dispatcher"
    ]

    assert len(dispatcher_keywords) == 1
    dispatcher_value = dispatcher_keywords[0].value
    assert isinstance(dispatcher_value, ast.Name)
    assert dispatcher_value.id == "generation_listener_dispatcher"
