"""The README's factual claims, checked against the package.

The README is what a reviewer reads on GitHub before anything else, and its
numbers go stale silently: it claimed 216 tests when there were 329, and
advertised a "reproducible synthetic-signal path" that never existed as a
public function — the very feature a reviewer then asked about. Prose cannot
be tested, but the countable claims can be, so they are.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import emgteach

ROOT = Path(emgteach.__file__).resolve().parent.parent.parent
README = ROOT / "README.md"


@pytest.fixture(scope="module")
def readme() -> str:
    if not README.exists():          # installed as a wheel, no repo around
        pytest.skip("README.md is not part of an installed package")
    return README.read_text(encoding="utf-8")


def test_the_test_count_is_current(readme: str, request) -> None:
    """The number of tests the README boasts is the number there are.

    Only meaningful on a full run: collecting one file would otherwise make
    this fail for the wrong reason.
    """
    total = len(request.session.items)
    if total < 100:
        pytest.skip("only meaningful when the whole suite is collected")

    match = re.search(r"\*\*(\d[\d\s,]*) tests\*\*", readme)
    assert match, "the README no longer states a test count"
    claimed = int(re.sub(r"[\s,]", "", match.group(1)))
    assert claimed == total, (
        f"the README claims {claimed} tests; the suite collects {total}"
    )


def test_the_supported_python_versions_match_the_packaging(
    readme: str,
) -> None:
    """A stale version claim in the README sent people to install the wrong
    Python once already, over an extra that had not existed for months."""
    # Read with a regular expression rather than a TOML parser: ``tomllib``
    # is standard library only from 3.11, and this repository supports 3.10 —
    # so the test that guards the supported-version claim was itself the one
    # thing that could not run on the lowest version it guards. One scalar is
    # not worth a dependency, and a format change fails the assertion below
    # rather than passing quietly.
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match_req = re.search(
        r'^\s*requires-python\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match_req, "pyproject.toml no longer declares requires-python"
    requires = match_req.group(1)
    floor = re.search(r">=\s*3\.(\d+)", requires)
    ceiling = re.search(r"<\s*3\.(\d+)", requires)
    assert floor and ceiling, requires
    lowest, highest = int(floor.group(1)), int(ceiling.group(1)) - 1
    for minor in range(lowest, highest + 1):
        assert f"3.{minor}" in readme, (
            f"the packaging supports 3.{minor}; the README does not say so"
        )


def test_the_version_matches_the_package(readme: str) -> None:
    assert emgteach.__version__ in readme, (
        f"the README does not mention the shipped version "
        f"{emgteach.__version__}"
    )


class TestNoPromiseTheCodeDoesNotKeep:
    """Features the README used to advertise that were never public API.

    A reviewer who reads GitHub finds the promise; this is exactly what
    happened with the synthetic-signal path, and it cost a round of review.
    """

    def test_it_does_not_advertise_a_synthetic_signal_generator(
        self, readme: str
    ) -> None:
        """Withdrawn deliberately: what exists is test scaffolding and the
        force-velocity rehearsal's own subject, not a generator students can
        use. If one is ever promoted to public API, say so here again."""
        assert "synthetic" not in readme.lower(), (
            "the README advertises synthetic signals again — either make it "
            "public API or take the claim out"
        )

    def test_every_module_it_names_as_core_exists_and_is_qt_free(
        self, readme: str
    ) -> None:
        """The core is named module by module; a rename would leave the list
        pointing at nothing, and a stray Qt import would quietly make the
        "Qt-free" claim false.

        What is checked is the import at **module level**. ``i18n`` reaches
        for ``QLocale`` inside a function to detect the start-up language,
        and that is the house pattern: the module still imports, and still
        works, with no Qt installed at all. A top-level import is what would
        break the claim.
        """
        import ast

        block = re.search(
            r"Qt-free analytic core \(([^)]+)\)", readme, re.DOTALL
        )
        assert block, "the README no longer lists the analytic core"
        names = [n.strip() for n in block.group(1).replace("\n", " ").split(",")]
        pkg = Path(emgteach.__file__).parent
        for name in names:
            source = pkg / f"{name}.py"
            assert source.exists(), f"README names a missing module: {name}"
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in tree.body:               # module level only
                if isinstance(node, ast.Import):
                    imported = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                else:
                    continue
                assert not any(m.startswith("PySide6") for m in imported), (
                    f"{name} is listed as Qt-free but imports Qt at module "
                    "level"
                )
