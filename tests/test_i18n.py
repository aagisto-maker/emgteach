"""Tests for the minimal i18n layer (:mod:`emgteach.i18n`)."""

from __future__ import annotations

import pytest

from emgteach import i18n


@pytest.fixture(autouse=True)
def _restore_language():
    """Keep the process-wide language global from leaking between tests."""
    previous = i18n.get_language()
    try:
        yield
    finally:
        i18n.set_language(previous)


def test_default_language_is_english() -> None:
    assert i18n.get_language() == "en"
    # English is canonical: tr returns the key unchanged.
    assert i18n.tr("Connect") == "Connect"


def test_spanish_translation() -> None:
    i18n.set_language("es")
    assert i18n.get_language() == "es"
    assert i18n.tr("Connect") == "Conectar"


def test_unknown_key_falls_back_to_english() -> None:
    i18n.set_language("es")
    sentinel = "a string with no translation entry"
    assert i18n.tr(sentinel) == sentinel


def test_set_language_rejects_unknown_codes() -> None:
    i18n.set_language("fr")  # unsupported → English
    assert i18n.get_language() == "en"


def test_resolve_startup_language_prefers_saved_setting() -> None:
    class _FakeSettings:
        def value(self, key: str, default: str = "") -> str:
            return "es" if key == "app/language" else default

    assert i18n.resolve_startup_language(_FakeSettings()) == "es"


def _tr_keys() -> dict[str, str]:
    """Every literal passed to tr() in the source tree, with where it is used."""
    import ast
    import pathlib

    root = pathlib.Path(i18n.__file__).parent
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        if path.name == "i18n.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.setdefault(node.args[0].value, f"{path.name}:{node.lineno}")
    return found


def test_every_translatable_string_has_a_spanish_entry() -> None:
    """No tr() literal may fall back to English in the Spanish interface.

    This is the silent failure of a hand-written catalogue: a key that drifts
    from the source by one character — an em dash where the entry has a hyphen —
    still runs, it just quietly shows English to Spanish-speaking students. It
    is how "E" and "A" went years without an entry while their sibling "R" had
    one, and only looked right because the initial happens to match in both
    languages.
    """
    missing = {k: where for k, where in _tr_keys().items() if k not in i18n._ES}
    assert not missing, "sin traducción al español: " + "; ".join(
        f"{where} {key[:60]!r}"
        for key, where in sorted(missing.items(), key=lambda kv: kv[1])
    )
