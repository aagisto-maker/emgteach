"""La coactivación de una ventana con nombre se lee sobre el registro sin recortar.

Elegir fragmentos en la pestaña de Análisis los concatenaba en una sola señal
y la tabla de coactivación se leía sobre ella. El índice resta a cada músculo
su nivel de reposo, el percentil 10 de la señal analizada, y una señal hecha
solo de contracciones no tiene reposo: su percentil 10 es lo más callado que
estuvo el músculo *mientras trabajaba*. Para el antagonista, eso es su propia
parte en la maniobra del otro, y restarla castiga en proporción a la señal
pequeña, que es justo la que la práctica quiere enseñar.

Ahora la envolvente y el reposo se calculan una vez, sobre la fase de registro
sin recortar, y cada fragmento con nombre es una máscara sobre ella. La prueba
de aceptación es la del artículo: las tres maniobras del registro de ejemplo,
elegidas en la pestaña como una fila cada una, tienen que dar lo mismo que la
figura 6 leyéndolas a mano sobre el original.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import numpy as np
import pytest

from emgteach.coactivation import coactivation_by_fragments, resting_level

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "docs" / "informe-sourcebook" / "ejemplo_tres_maniobras.edf"

#: The article's three manoeuvres, in seconds of the example file.
MANIOBRAS = [(57.5, 70.0, "Flexion"), (72.0, 85.0, "Extension"), (88.0, 97.0, "Grip")]
#: What the figure gives for them: index and the two means, % MVC.
PUBLICADO = {
    "Flexion": (28.3, 14.13, 5.83),
    "Extension": (None, 4.20, 6.17),
    "Grip": (75.7, 14.48, 9.08),
}

FS = 100.0


def _envolventes():
    """Two muscles over 20 s: at rest 1 and 2 % MVC; the first works alone in
    [2, 5) and [8, 11), both work in [14, 18), and an unnamed burst of both
    sits in [12, 13). Flat levels, so every mean is exact by construction."""
    n = int(20 * FS)
    e1 = np.full(n, 1.0)
    e2 = np.full(n, 2.0)
    for a, b, v1, v2 in ((2, 5, 30.0, 3.0), (8, 11, 30.0, 3.0),
                         (14, 18, 20.0, 15.0), (12, 13, 50.0, 50.0)):
        e1[int(a * FS):int(b * FS)] = v1
        e2[int(a * FS):int(b * FS)] = v2
    return e1, e2


class TestTheRestComesFromTheWholeSpan:
    def test_the_rest_is_the_spans_not_the_fragments(self) -> None:
        """Read off the fragments alone, the first muscle's 10th percentile
        would be 20 — its level during the grip — and the grip's mean 0."""
        e1, e2 = _envolventes()
        (grip,), _ = coactivation_by_fragments(
            e1, e2, FS, [(14.0, 18.0, "Grip")])
        assert grip.mean_1 == pytest.approx(20.0 - resting_level(e1))
        assert grip.mean_2 == pytest.approx(15.0 - resting_level(e2))
        assert resting_level(e1) == pytest.approx(1.0)
        assert resting_level(e2) == pytest.approx(2.0)
        assert grip.index is not None

    def test_the_window_is_read_only_on_its_fragments(self) -> None:
        """The rest *between* two fragments of one manoeuvre is not part of
        the manoeuvre; it only sets the zero."""
        e1, e2 = _envolventes()
        (flexion,), _ = coactivation_by_fragments(
            e1, e2, FS, [(2.0, 5.0, "Flexion"), (8.0, 11.0, "Flexion")])
        assert flexion.mean_1 == pytest.approx(29.0)
        assert flexion.mean_2 == pytest.approx(1.0)
        assert flexion.index is None, "the second muscle sits under the floor"


class TestWhatMakesAWindow:
    def test_consecutive_fragments_of_one_name_are_one_window(self) -> None:
        e1, e2 = _envolventes()
        out, desde_marcas = coactivation_by_fragments(
            e1, e2, FS,
            [(2.0, 5.0, "Flexion"), (8.0, 11.0, "Flexion"), (14.0, 18.0, "Grip")])
        assert desde_marcas is True
        assert [w.label for w in out] == ["Flexion", "Grip"]
        assert out[0].window_s == (2.0, 11.0)
        assert out[1].window_s == (14.0, 18.0)

    def test_an_unnamed_fragment_opens_no_window_and_enters_none(self) -> None:
        """Signal worth keeping is not a manoeuvre. The unnamed burst at 50 %
        lies between the two flexions: it neither breaks the run nor feeds
        its samples into it."""
        e1, e2 = _envolventes()
        out, _ = coactivation_by_fragments(
            e1, e2, FS,
            [(2.0, 5.0, "Flexion"), (12.0, 13.0, ""), (14.0, 18.0, "Flexion")])
        assert [w.label for w in out] == ["Flexion"]
        assert out[0].window_s == (2.0, 18.0)
        # 3 s at 30 and 4 s at 20, above a rest of 1: not a sample of the 50.
        assert out[0].mean_1 == pytest.approx((3 * 29.0 + 4 * 19.0) / 7)

    def test_a_name_that_comes_back_opens_a_second_window(self) -> None:
        e1, e2 = _envolventes()
        out, _ = coactivation_by_fragments(
            e1, e2, FS,
            [(2.0, 5.0, "Flexion"), (8.0, 11.0, "Grip"), (14.0, 18.0, "Flexion")])
        assert [w.label for w in out] == ["Flexion", "Grip", "Flexion"]

    def test_with_no_named_fragment_it_is_the_whole_span(self) -> None:
        e1, e2 = _envolventes()
        out, desde_marcas = coactivation_by_fragments(
            e1, e2, FS, [(2.0, 5.0, ""), (14.0, 18.0, "")])
        assert desde_marcas is False
        assert len(out) == 1
        assert out[0].window_s == (0.0, 20.0)

    def test_t0_shifts_the_reported_seconds_only(self) -> None:
        e1, e2 = _envolventes()
        (grip,), _ = coactivation_by_fragments(
            e1, e2, FS, [(14.0, 18.0, "Grip")], t0=57.3)
        assert grip.window_s == pytest.approx((71.3, 75.3))
        assert grip.mean_1 == pytest.approx(19.0)


def _figura6():
    ruta = RAIZ / "tools" / "figura6.py"
    spec = importlib.util.spec_from_file_location("figura6", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _analizar(qapp, edf: Path, **kw) -> dict:
    pytest.importorskip("mne")
    from PySide6.QtCore import QElapsedTimer

    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(
        edf_path=str(edf), channel_name="FCR", channel_name_2="ECR", **kw)
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.start()
    worker.wait(180000)
    reloj = QElapsedTimer()
    reloj.start()
    while not salida and reloj.elapsed() < 5000:
        qapp.processEvents()
    assert salida, "the analysis produced no result"
    return salida[0]


def _por_nombre(ventanas):
    return {w.label: w for w in ventanas}


@pytest.mark.gui
class TestTheExampleRecordingGivesTheArticleItsNumbers:
    """The acceptance test: through the tab, as a teacher would do it."""

    @pytest.fixture(scope="class")
    def por_la_pestana(self, qapp):
        r = _analizar(
            qapp, EJEMPLO,
            roi_segments=[(a, b) for a, b, _n in MANIOBRAS],
            roi_labels=[n for _a, _b, n in MANIOBRAS],
        )
        assert r["coactivation_from_markers"] is True
        return _por_nombre(r["coactivation"])

    @pytest.fixture(scope="class")
    def por_la_figura(self, qapp):
        """`tools/figura6.py --ventana`, on the analysis of the uncut phase."""
        r = _analizar(qapp, EJEMPLO)
        off = float(r["rec_start_s"])
        f6 = _figura6()
        arriba, abajo = f6.ventanas_a_mano(
            r, [(n, a - off, b - off) for a, b, n in MANIOBRAS],
            re.compile("grip", re.IGNORECASE))
        return _por_nombre(arriba + abajo)

    def test_the_three_manoeuvres_read_the_same_both_ways(
        self, por_la_pestana, por_la_figura
    ) -> None:
        for nombre in ("Flexion", "Extension", "Grip"):
            tab, fig = por_la_pestana[nombre], por_la_figura[nombre]
            assert (tab.index is None) == (fig.index is None)
            if tab.index is not None:
                assert tab.index == pytest.approx(fig.index, abs=1e-6)
            assert tab.mean_1 == pytest.approx(fig.mean_1, abs=1e-6)
            assert tab.mean_2 == pytest.approx(fig.mean_2, abs=1e-6)

    def test_and_they_are_the_published_ones(self, por_la_pestana) -> None:
        for nombre, (indice, m1, m2) in PUBLICADO.items():
            w = por_la_pestana[nombre]
            if indice is None:
                assert w.index is None, w.reason
            else:
                assert w.index == pytest.approx(indice, abs=0.05)
            assert w.mean_1 == pytest.approx(m1, abs=0.05)
            assert w.mean_2 == pytest.approx(m2, abs=0.05)

    def test_the_editors_own_grip_row_keeps_the_extensor(self, qapp) -> None:
        """The row the fragment editor proposes for the grip has no rest
        inside it. Read off its concatenation the extensor fell to 6.3 % MVC
        and the index to 58 %; read where it lies, it is what it was."""
        r = _analizar(qapp, EJEMPLO, roi_segments=[(89.71, 97.43)],
                      roi_labels=["Grip"])
        (grip,) = r["coactivation"]
        assert grip.index is not None and grip.index > 74.0
        assert grip.mean_2 > 10.0
        # And in the recording phase's own seconds, not the concatenation's.
        assert grip.window_s[0] == pytest.approx(89.71 - r["rec_start_s"], abs=0.01)
