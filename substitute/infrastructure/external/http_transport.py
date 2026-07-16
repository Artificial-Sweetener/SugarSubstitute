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

"""Provide lazy default HTTP transports for external adapter modules."""

from __future__ import annotations

from typing import Any


def default_http_get(*args: Any, **kwargs: Any) -> Any:
    """Call `requests.get` without importing requests at adapter module load."""

    import requests

    return requests.get(*args, **kwargs)


def default_http_post(*args: Any, **kwargs: Any) -> Any:
    """Call `requests.post` without importing requests at adapter module load."""

    import requests

    return requests.post(*args, **kwargs)


def default_http_put(*args: Any, **kwargs: Any) -> Any:
    """Call `requests.put` without importing requests at adapter module load."""

    import requests

    return requests.put(*args, **kwargs)


def default_http_delete(*args: Any, **kwargs: Any) -> Any:
    """Call `requests.delete` without importing requests at adapter module load."""

    import requests

    return requests.delete(*args, **kwargs)


def is_request_exception(error: BaseException) -> bool:
    """Return whether an exception came from requests without eager imports."""

    import requests

    return isinstance(error, requests.RequestException)


__all__ = [
    "default_http_delete",
    "default_http_get",
    "default_http_post",
    "default_http_put",
    "is_request_exception",
]
