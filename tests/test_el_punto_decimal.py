"""One decimal mark, and it is the point.

The application wrote three notations at once. The handful of numbers that
went through :func:`emgteach.i18n.cifra` came out as 1,5 in Spanish; the
hundred-odd formatted inline — every percentage, every millivolt, every
frequency — came out as 1.5; and every spin box followed the operating
system, so on the Spanish Windows of the laboratory it showed 1,5 and
refused the 1.5 the manual printed beside it.

These tests hold the decision in place: the interface and the documents the
student reads write the point, a field takes either mark and shows the
point, and the CSV keeps its own dialect, which is the spreadsheet's and
not the text's.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from emgteach import i18n
from emgteach.exports import csv_dialect
from emgteach.i18n import cifra, get_language, set_language

RAIZ = Path(__file__).resolve().parent.parent

#: A decimal comma: a digit, a comma, a digit.
COMA = re.compile(r"\d,\d")

#: What the student reads on paper. The specifications, the release notes
#: and the report for the article are records of what was decided when, and
#: are not rewritten.
DOCUMENTOS = (
    "manual_emgteach_es.md",
    "chuleta_es.md",
    "guion_practicas_es.md",
    "colocacion_electrodos_antebrazo_es.md",
    "rubrica_evaluacion_es.md",
)


@pytest.fixture
def idioma():
    """Switch language, and leave the suite in the one it came in with."""
    anterior = get_language()
    yield set_language
    set_language(anterior)


def test_a_number_is_written_the_same_in_both_languages(idioma) -> None:
    for lang in ("en", "es"):
        idioma(lang)
        assert cifra(4.5) == "4.5"
        assert cifra(1.5) == "1.5"
        assert cifra(3.0) == "3"        # ``:g``, so no trailing zero either


def test_no_string_of_the_catalogue_writes_a_decimal_comma() -> None:
    culpables = [
        (k[:60], v[:60])
        for k, v in i18n._ES.items()
        if COMA.search(k) or COMA.search(v)
    ]
    assert not culpables, culpables


def test_the_documents_the_student_reads_write_the_point() -> None:
    """A manual that prints 4,5 % for a screen that prints 4.5 % is a
    second number to look for, not a translation."""
    culpables: list[str] = []
    for nombre in DOCUMENTOS:
        texto = (RAIZ / "docs" / nombre).read_text(encoding="utf-8")
        for n, linea in enumerate(texto.splitlines(), 1):
            if COMA.search(linea):
                culpables.append(f"{nombre}:{n} {linea.strip()[:60]}")
    assert not culpables, culpables


def test_a_field_writes_the_point_and_takes_the_comma(qapp) -> None:
    """Qt's own, under the locale of the laboratory's machines.

    The comma is accepted because the numeric keypad of a Spanish keyboard
    sends one: refusing it would put a new fault in place of the old one.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtGui import QValidator

    from emgteach.gui.widgets.decimal_spin import DecimalSpinBox

    anterior = QLocale()
    QLocale.setDefault(QLocale("es_ES"))
    try:
        spin = DecimalSpinBox()
        spin.setDecimals(1)
        spin.setRange(0.0, 10.0)
        spin.setValue(4.4)
        assert spin.text() == "4.4"
        estado, texto, _ = spin.validate("4,4", 3)
        assert estado == QValidator.State.Acceptable
        assert texto == "4.4"           # what was typed, as the field shows it
        assert spin.valueFromText("4,4") == pytest.approx(4.4)
    finally:
        QLocale.setDefault(anterior)


def test_every_editable_number_of_the_interface_goes_through_it() -> None:
    """A plain ``QDoubleSpinBox`` would take the mark back to the system's."""
    gui = Path(i18n.__file__).parent / "gui"
    culpables = [
        f"{ruta.relative_to(gui).as_posix()}:{n}"
        for ruta in sorted(gui.rglob("*.py"))
        if ruta.name != "decimal_spin.py"
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1)
        if "QDoubleSpinBox" in linea
    ]
    assert not culpables, culpables


def test_the_csv_keeps_the_mark_of_whatever_reads_it(idioma) -> None:
    """The deliberate exception: a spreadsheet, not a person, reads it.

    Excel and LibreOffice set to Spanish open a comma-separated file in a
    single column and read 0.05 as text, so the Spanish export keeps the
    semicolon and the decimal comma. The file says which pair it carries on
    its first line, and the manual says why.
    """
    idioma("es")
    assert csv_dialect() == (";", ",")
    idioma("en")
    assert csv_dialect() == (",", ".")

    manual = (RAIZ / "docs" / "manual_emgteach_es.md").read_text(encoding="utf-8")
    assert "punto y coma de separador y coma\ndecimal" in manual
