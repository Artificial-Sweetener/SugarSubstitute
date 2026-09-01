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

"""Prove splash-first diagnostics distinguish startup control-flow paths."""

from __future__ import annotations

from pathlib import Path
import textwrap

from tools.splash_first_governance import (
    SplashDependencyContract,
    SplashFirstContract,
    validate_contract_source,
    validate_dependency_source,
)


_PATH = Path("launcher.py")
_CONTRACT = SplashFirstContract(
    relative_path=_PATH,
    function_name="main",
    boundary_call="show_splash",
    allowed_module_import_roots=frozenset({"__future__", "sys"}),
    allowed_pre_boundary_imports=frozenset({"safe.routing", "safe.splash"}),
    allowed_pre_boundary_calls=frozenset(
        {"parse_route", "resolve_layout", "show_splash"}
    ),
)


def test_checker_accepts_only_reviewed_work_before_splash() -> None:
    """Reviewed routing may precede visibility while application work follows it."""

    source = _source(
        """
        import sys

        def main():
            from safe.routing import parse_route, resolve_layout
            route = parse_route(sys.argv)
            if route.headless:
                from application.headless import run_headless
                return run_headless()
            layout = resolve_layout(route)
            from safe.splash import show_splash
            splash = show_splash(layout=layout)
            from application.startup import perform_heavy_work
            perform_heavy_work(splash)
        """
    )

    assert validate_contract_source(source, contract=_CONTRACT, path=_PATH) == ()


def test_checker_rejects_eager_project_imports() -> None:
    """Module imports cannot silently move application composition before splash."""

    source = _source(
        """
        from application.startup import perform_heavy_work

        def main():
            from safe.splash import show_splash
            show_splash()
            perform_heavy_work()
        """
    )

    diagnostics = validate_contract_source(source, contract=_CONTRACT, path=_PATH)

    assert [(item.code, item.line) for item in diagnostics] == [("SPLASH002", 2)]


def test_checker_rejects_import_time_work() -> None:
    """Module-level calls cannot bypass the protected entrypoint boundary."""

    source = _source(
        """
        warm_application_cache()

        def main():
            from safe.splash import show_splash
            show_splash()
        """
    )

    diagnostics = validate_contract_source(source, contract=_CONTRACT, path=_PATH)

    assert [(item.code, item.line) for item in diagnostics] == [("SPLASH005", 2)]
    assert "warm_application_cache" in diagnostics[0].message


def test_checker_rejects_unreviewed_calls_on_boundary_path() -> None:
    """Filesystem, network, or composition calls added before visibility must fail."""

    source = _source(
        """
        def main():
            resolve_layout()
            load_configuration()
            from safe.splash import show_splash
            show_splash()
        """
    )

    diagnostics = validate_contract_source(source, contract=_CONTRACT, path=_PATH)

    assert [(item.code, item.line) for item in diagnostics] == [("SPLASH004", 4)]
    assert "load_configuration" in diagnostics[0].message


def test_checker_ignores_work_confined_to_a_returning_non_splash_mode() -> None:
    """Headless-only execution does not delay the installed splash route."""

    source = _source(
        """
        def main():
            if is_headless:
                download_release()
                return 0
            resolve_layout()
            from safe.splash import show_splash
            show_splash()
        """
    )

    assert validate_contract_source(source, contract=_CONTRACT, path=_PATH) == ()


def test_checker_rejects_missing_or_duplicated_visibility_boundaries() -> None:
    """A protected entrypoint must expose one unambiguous splash transition."""

    missing = _source(
        """
        def main():
            resolve_layout()
        """
    )
    duplicated = _source(
        """
        def main():
            show_splash()
            show_splash()
        """
    )

    missing_diagnostics = validate_contract_source(
        missing,
        contract=_CONTRACT,
        path=_PATH,
    )
    duplicated_diagnostics = validate_contract_source(
        duplicated,
        contract=_CONTRACT,
        path=_PATH,
    )

    assert [item.code for item in missing_diagnostics] == ["SPLASH001"]
    assert [item.code for item in duplicated_diagnostics] == ["SPLASH001"]


def test_checker_rejects_heavy_transitive_splash_dependencies() -> None:
    """The protected pre-paint closure cannot acquire application-wide imports."""

    source = _source(
        """
        from substitute.presentation.shell.window_frame import ShellBackdropMode
        import scipy
        """
    )
    contract = SplashDependencyContract(
        relative_path=Path("splash.py"),
        forbidden_import_prefixes=frozenset(
            {"scipy", "substitute.presentation.shell.window_frame"}
        ),
    )

    diagnostics = validate_dependency_source(source, contract=contract, path=_PATH)

    assert [(item.code, item.line) for item in diagnostics] == [
        ("SPLASH006", 2),
        ("SPLASH006", 3),
    ]


def test_checker_protects_imports_before_a_dependency_paint_boundary() -> None:
    """Session infrastructure may load after paint but never before it."""

    source = _source(
        """
        def main():
            from session.server import SplashSessionServer
            splash.show()
            from session.client import SplashSessionClient
        """
    )
    contract = SplashDependencyContract(
        relative_path=Path("splash.py"),
        forbidden_import_prefixes=frozenset({"session"}),
        function_name="main",
        boundary_call="splash.show",
    )

    diagnostics = validate_dependency_source(source, contract=contract, path=_PATH)

    assert [(item.code, item.line) for item in diagnostics] == [("SPLASH006", 3)]


def _source(value: str) -> str:
    """Return a left-aligned source fixture with stable line numbers."""

    return textwrap.dedent(value)
