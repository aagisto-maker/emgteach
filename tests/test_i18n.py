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
