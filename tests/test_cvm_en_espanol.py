"""In Spanish the unit reads «% CVM», in English «% MVC».

With the interface in Spanish (21 Oct 2026, 3.9.0, simulated board) the load
bar of the acquisition tab and the data panel of the normalisation tab wrote
«% MVC»: the unit was written straight into an f-string, past ``tr()``. The
report's metrics table did the same. The catalogue already had the entry; the
four places now go through it, and the number keeps its format.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from emgteach.i18n import _ES, get_language, set_language
from emgteach.reports import build_mvc_report
from tests.test_informes_y_csv import _pdf_text, _resultado_cvm


@pytest.fixture
def idioma():
    previo = get_language()
    yield set_language
    set_language(previo)


def test_the_catalogue_has_the_unit_in_both_languages() -> None:
    assert _ES["% MVC"] == "% CVM"


@pytest.mark.parametrize(("lang", "unit"), [("es", "% CVM"), ("en", "% MVC")])
def test_the_load_bar_writes_the_unit_of_the_language(qapp, idioma, lang, unit) -> None:
    from emgteach.gui.widgets.load_bar import LoadBar

    idioma(lang)
    bar = LoadBar()
    bar.set_value(43.4)
    assert bar._text() == f"43 {unit}"


@pytest.mark.parametrize(("lang", "unit"), [("es", "% CVM"), ("en", "% MVC")])
def test_the_normalisation_panel_writes_the_unit_of_the_language(idioma, lang, unit) -> None:
    from emgteach.gui.tabs.mvc import MvcTab

    idioma(lang)
    html = MvcTab._metric_html("P10", 2.0, 10.0, "")
    assert f"2 {unit}</span>" in html
    other = "% MVC" if unit == "% CVM" else "% CVM"
    assert other not in html


@pytest.mark.parametrize(("lang", "unit"), [("es", "% CVM"), ("en", "% MVC")])
def test_the_report_writes_the_unit_of_the_language(tmp_path: Path, idioma, lang, unit) -> None:
    idioma(lang)
    out = tmp_path / "cvm.pdf"
    resultado = _resultado_cvm()
    build_mvc_report(out, resultado, time_range=(0.5, 3.5), meta={})
    text = _pdf_text(out)
    # Mean activation and the three load levels.
    assert f"{resultado['mean_norm']:.1f} {unit}" in text
    assert f"{resultado['apdf'].static.value:.0f} {unit} (" in text
    assert f"{resultado['apdf'].peak.value:.0f} {unit} (" in text
    if lang == "es":
        assert "% MVC" not in text
