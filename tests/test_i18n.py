"""Tests for the minimal i18n layer (:mod:`emgteach.i18n`)."""

from __future__ import annotations

import re

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


def test_the_names_a_practical_imposes_are_translated() -> None:
    """Channel names fixed by a practical reach ``tr()`` as a variable.

    The scan above only sees literals, so a name held as data — here, and the
    marker presets in ``SignalProfile`` — slips past it and shows in English
    to a Spanish-speaking student. Which is the exact failure that test was
    written for, arriving by a door it cannot watch.
    """
    from emgteach.modes import MODES, mode_fixed_labels

    faltan = [
        name for mode in MODES for name in mode_fixed_labels(mode)
        if name not in i18n._ES
    ]
    assert not faltan, f"sin traducción al español: {faltan}"


def test_the_spanish_interface_does_not_switch_to_tu() -> None:
    """One register, all the way through.

    English hides the choice — «you» is both — so a new string can be written
    in English, translated in good faith, and land in the Spanish interface
    addressing the user as «tú» while the other hundred and fifty entries
    address them as «usted». It reads as two people wrote the program, and it
    went unnoticed until it was seen on screen.

    The net below is not exhaustive; it catches the forms that have no other
    reading.
    """
    tuteo = re.compile(
        r"\b(decides|puedes|tienes|debes|quieres|sabes|haces|ver[áa]s|podr[áa]s"
        r"|por ti|contigo|tuyos?|tuyas?)\b",
        re.IGNORECASE,
    )
    culpables = {
        en: es for en, es in i18n._ES.items() if tuteo.search(es)
    }
    assert not culpables, "tutean, y el resto de la interfaz trata de usted: " + "; ".join(
        repr(v[:70]) for v in culpables.values()
    )


def test_the_suggested_manoeuvres_are_translated() -> None:
    """The other door the literal scan cannot watch.

    ``marker_presets`` is a tuple of names handed to ``tr()`` one by one, so
    changing it — as the move from instants to manoeuvres did — adds strings
    that no scan of the source will report as missing.
    """
    from emgteach.profiles import PROFILES

    faltan = [
        preset for perfil in PROFILES.values()
        for preset in perfil.marker_presets
        if preset not in i18n._ES
    ]
    assert not faltan, f"sin traducción al español: {faltan}"


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


# ── The other hole: text that never reached tr() at all ───────────────────
#
# The completeness test above checks that every key tr() is *given* has a
# Spanish entry. It cannot see a label that was written straight into a
# QLabel: that string is never a missing key, it simply comes out in English
# in both languages, and the only way it gets noticed is somebody reading the
# Spanish interface and spotting a word. That is exactly the manual hunt these
# tests exist to replace.

#: Widget constructors whose first argument is the visible label.
_LABEL_CONSTRUCTORS = {
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox",
    "QToolButton", "QAction", "QCommandLinkButton",
}
#: Methods whose first argument (or list of them) is shown to the user.
_LABEL_SETTERS = {
    "setText", "setToolTip", "setWindowTitle", "setPlaceholderText",
    "setTitle", "setStatusTip", "setWhatsThis", "setSuffix", "setPrefix",
    "addItem", "addTab", "setHorizontalHeaderLabels", "setLabelText",
    "setInformativeText", "setDetailedText", "setItemText",
}

#: Strings that are shown untranslated on purpose. Each one is a decision, so
#: they are listed rather than pattern-matched away: a new arrival has to be
#: looked at and either translated or added here with a reason.
_DELIBERATELY_UNTRANSLATED = {
    # A language picker names each language in that language — translating
    # "Español" to "Spanish" would hide the option from the person who needs it.
    "English", "Español",
    # Product names.
    "BITalino (Bluetooth)", "Arduino + MyoWare 2.0 (USB)",
    # An example of what to type; the words in it are the same in both.
    "98:D3:91:FE:44:E4   ·   COM5   ·   (auto)",
    # Signal and channel names, and the abbreviation for the integrated EMG.
    "EMG", "iEMG: —",
}


def _looks_like_prose(s: str) -> bool:
    """Filter out what is visible but is not language: symbols, units, CSS."""
    s = s.strip()
    if len(s) < 3 or not any(c.isalpha() for c in s):
        return False
    if s.startswith(("#", "font-", "color:", "background")):
        return False
    if ":" in s and ";" in s:                       # a style sheet
        return False
    return sum(c.isalpha() for c in s) >= 3


def _is_tr_call(node) -> bool:
    """tr("…") — or something built from it, like tr("…").format(…)."""
    import ast

    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        node = node.func.value
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "tr"
    )


def test_no_visible_string_escapes_translation() -> None:
    """Nothing shown to the user is written straight into a widget."""
    import ast
    import pathlib

    def constants(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node
        elif isinstance(node, ast.List | ast.Tuple):
            for element in node.elts:
                yield from constants(element)

    escaped: list[str] = []
    root = pathlib.Path(i18n.__file__).parent
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            named = (
                isinstance(node.func, ast.Name)
                and node.func.id in _LABEL_CONSTRUCTORS
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _LABEL_SETTERS
            )
            if not named or _is_tr_call(node.args[0]):
                continue
            for c in constants(node.args[0]):
                if (
                    _looks_like_prose(c.value)
                    and c.value not in _DELIBERATELY_UNTRANSLATED
                ):
                    escaped.append(f"{path.name}:{c.lineno} {c.value!r}")

    assert not escaped, (
        "shown to the user but never passed through tr(): "
        + "; ".join(escaped)
    )
