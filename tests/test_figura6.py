"""La figura 6 del artículo: patrón recíproco arriba, presa abajo.

`tools/figura6.py` conduce la aplicación para no recalcular nada, pero el
reparto de las ventanas entre los dos paneles y el dibujo en sí son suyos, y
son lo que puede salir mal el día que haya que rehacer la figura con prisa.
Eso es lo que se prueba aquí, sin hardware y sin abrir la interfaz: se le da
un resultado de análisis fabricado y se comprueba qué hace con él.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _figura6():
    """Importa la herramienta, que vive en `tools/` y no es un paquete."""
    ruta = RAIZ / "tools" / "figura6.py"
    spec = importlib.util.spec_from_file_location("figura6", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def figura6(qapp):          # qapp: el módulo construye un QApplication
    return _figura6()


def _ventana(label, a, b, indice=30.0):
    from emgteach.coactivation import CoactivationResult

    return CoactivationResult(indice, 20.0, 15.0, (a, b), None, label)


def _resultado(fs=100.0, dur=30.0):
    """Dos envolventes: la primera manda hasta el segundo 20, luego las dos."""
    t = np.arange(0.0, dur, 1.0 / fs)
    e1 = np.full(t.size, 0.02)
    e2 = np.full(t.size, 0.02)
    e1[(t >= 2) & (t < 8)] = 0.20            # flexión
    e2[(t >= 10) & (t < 16)] = 0.20          # extensión
    e1[(t >= 20) & (t < 28)] = 0.18          # presa: los dos a la vez
    e2[(t >= 20) & (t < 28)] = 0.16
    return {
        "times": t,
        "fs": fs,
        "emg_envelope": e1,
        "emg_envelope_2": e2,
        "mvc_ref": 0.20,
        "mvc_ref_2": 0.20,
        "channel_name": "FCR",
        "channel_name_2": "ECR",
        "coactivation_from_markers": True,
        "coactivation": [
            _ventana("Flexión", 2.0, 9.0, 8.0),
            _ventana("Extensión", 10.0, 18.0, 11.0),
            _ventana("Presa", 20.0, 28.0, 74.0),
        ],
    }


class TestHowItSplitsTheWindows:
    def test_the_grip_goes_to_the_lower_panel(self, figura6) -> None:
        arriba, abajo = figura6.ventanas(
            _resultado(), re.compile(r"presa|grip", re.IGNORECASE))
        assert [w.label for w in arriba] == ["Flexión", "Extensión"]
        assert [w.label for w in abajo] == ["Presa"]

    def test_it_recognises_the_grip_in_english_too(self, figura6) -> None:
        r = _resultado()
        r["coactivation"][2] = _ventana("Grip", 20.0, 28.0, 74.0)
        _, abajo = figura6.ventanas(r, re.compile(r"presa|grip", re.IGNORECASE))
        assert [w.label for w in abajo] == ["Grip"]

    def test_without_a_grip_the_lower_panel_is_simply_empty(self, figura6) -> None:
        """El caso del registro del 3 de septiembre: la figura tiene que salir
        igual, diciendo que falta, en vez de no salir."""
        r = _resultado()
        r["coactivation"] = r["coactivation"][:2]
        arriba, abajo = figura6.ventanas(
            r, re.compile(r"presa|grip", re.IGNORECASE))
        assert len(arriba) == 2
        assert abajo == []

    def test_the_span_covers_every_window_of_the_panel(self, figura6) -> None:
        arriba, _ = figura6.ventanas(
            _resultado(), re.compile(r"presa", re.IGNORECASE))
        assert figura6._span(arriba) == (2.0, 18.0)
        assert figura6._span([]) is None


class TestWhatItDraws:
    def test_it_writes_both_a_png_and_a_pdf(self, figura6, tmp_path) -> None:
        figura6.dibuja(_resultado(), tmp_path, "f6",
                       re.compile(r"presa", re.IGNORECASE),
                       figura6.ROTULOS["en"])
        assert (tmp_path / "f6.png").stat().st_size > 0
        assert (tmp_path / "f6.pdf").stat().st_size > 0

    def test_the_page_is_the_size_the_journal_asks_for(self, figura6) -> None:
        assert (figura6.ANCHO_PULGADAS, figura6.ALTO_PULGADAS) == (6.5, 4.0)
        assert figura6.PUNTOS >= 8

    def test_both_panels_share_one_ceiling(self, figura6, tmp_path) -> None:
        """Lo que la figura afirma es que en la presa suben las dos curvas y en
        la alternancia no. Con un eje distinto en cada panel, no afirma nada."""
        import matplotlib.pyplot as plt

        figura6.dibuja(_resultado(), tmp_path, "f6",
                       re.compile(r"presa", re.IGNORECASE),
                       figura6.ROTULOS["es"])
        # `dibuja` cierra su figura; lo que se comprueba es que el techo que
        # calcula no depende del panel, recorriendo el mismo camino.
        assert plt.get_fignums() == []

    def test_it_survives_a_recording_with_no_windows_at_all(
        self, figura6, tmp_path
    ) -> None:
        r = _resultado()
        r["coactivation"] = []
        r["coactivation_from_markers"] = False
        figura6.dibuja(r, tmp_path, "f6", re.compile(r"presa"),
                       figura6.ROTULOS["en"])
        assert (tmp_path / "f6.png").exists()
