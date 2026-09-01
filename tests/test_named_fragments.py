"""Fragmentos con nombre: el §2 de las enmiendas, y lo que lo obliga.

De los siete registros del banco de los días 30 y 31 de agosto **ninguno tiene
una sola marca de fase**: todas las anotaciones son `Onset (auto)` y `MVC ref`.
Por eso la tabla de coactivación ha dicho siempre «registro completo — marque
las fases», y por eso siguen faltando dos de los cuatro números del banco.

Y lo automático solo no puede producirlos, **nunca**. El detector dice «aquí
empezó una contracción»; el índice necesita «esta ventana es la presa». La
diferencia entre flexión, extensión y presa no está en la forma de la
envolvente: está en lo que se le pidió al sujeto. Ningún algoritmo va a
nombrarla, así que la nombra el operador, después, sobre una traza que puede
ver — y ese acto de interpretación *es* la práctica.

Marcar en vivo tenía una ventaja real que se pierde: se sabía en el momento qué
se le había pedido al sujeto. Marcando después hay que reconocerlo en la traza,
lo cual obliga a hacer siempre las maniobras en el mismo orden. Está dicho en el
protocolo de la práctica.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from emgteach.io import BufferedEdfWriter, ChannelInfo, read_edf_markers
from emgteach.mvc import mvc_ref_marker
from emgteach.phases import (
    cal_end_marker,
    cal_start_marker,
    parse_phase_markers,
    prep_start_marker,
    rec_start_marker,
)
from emgteach.selection import Segment, normalise_segments

FS = 1000
DURACION = 44
CAL = [(4.0, 8.0, 1.00), (12.0, 16.0, 1.40)]
PREP_S = 18.0
REC_S = 20.0
#: The practical's three manoeuvres, inside the recording phase.
MANIOBRAS = [
    (22.0, 27.0, "Flexion", 0.40, 0.05),
    (28.0, 33.0, "Extension", 0.05, 0.40),
    (34.0, 41.0, "Grip", 0.35, 0.30),
]


def _sesion(path: Path) -> str:
    t = np.arange(DURACION * FS) / FS
    a = np.full(t.size, 0.01)
    b = np.full(t.size, 0.01)
    for ini, fin, _n, va, vb in MANIOBRAS:
        a[int(ini * FS) : int(fin * FS)] = va
        b[int(ini * FS) : int(fin * FS)] = vb
    for ini, fin, amp in CAL:
        a[int(ini * FS) : int(fin * FS)] = amp
        b[int(ini * FS) : int(fin * FS)] = amp
    portadora = np.sin(2 * np.pi * 80 * t)
    canales = [
        ChannelInfo("FCR", dimension="mV", sample_frequency=FS),
        ChannelInfo("ECR", dimension="mV", sample_frequency=FS),
    ]
    with BufferedEdfWriter(str(path), channels=canales) as w:
        w.add_samples(portadora * a, portadora * b)
        for i, (ini, fin, _amp) in enumerate(CAL, start=1):
            for canal in (0, 1):
                w.add_annotation(ini, cal_start_marker(canal, i))
                w.add_annotation(fin, cal_end_marker(canal, i))
        w.add_annotation(PREP_S, prep_start_marker())
        w.add_annotation(REC_S, rec_start_marker())
        w.add_annotation(23.0, "Onset (auto) — FCR")
        w.add_annotation(2.0, mvc_ref_marker(0, 0.9))
        w.add_annotation(2.1, mvc_ref_marker(1, 0.9))
    return str(path)


def _fragmentos() -> tuple[list[tuple[float, float]], list[str]]:
    return ([(a, b) for a, b, _n, _x, _y in MANIOBRAS],
            [n for _a, _b, n, _x, _y in MANIOBRAS])


def _analizar(qapp, edf: str, **kw) -> dict:
    pytest.importorskip("mne")
    from emgteach.workers import AnalysisWorker

    worker = AnalysisWorker(
        edf_path=edf, channel_name="FCR", channel_name_2="ECR", **kw)
    salida: list[dict] = []
    worker.result_ready.connect(salida.append)
    worker.start()
    from PySide6.QtCore import QElapsedTimer

    reloj = QElapsedTimer()
    reloj.start()
    while not salida and reloj.elapsed() < 30000:
        qapp.processEvents()
    worker.wait(5000)
    assert salida, "the analysis produced no result"
    return salida[0]


class TestTheNameTravelsWithTheFragment:
    """`Segment.label` — Qt-free, so it can be checked on its own terms."""

    def test_clamping_keeps_it(self) -> None:
        (s,) = normalise_segments([Segment(-1.0, 5.0, label="Grip")], 10.0)
        assert s.label == "Grip"

    def test_merging_two_keeps_the_earlier_one(self) -> None:
        """Two fragments that overlap are one stretch, and the operator named
        its start."""
        (s,) = normalise_segments(
            [Segment(0.0, 5.0, label="Grip"), Segment(4.0, 8.0, label="Rest")],
            10.0,
        )
        assert s.label == "Grip"

    def test_an_unnamed_fragment_stays_unnamed(self) -> None:
        (s,) = normalise_segments([Segment(0.0, 5.0)], 10.0)
        assert s.label == ""


@pytest.mark.gui
class TestANamedFragmentIsAWindowOfTheTable:
    def test_without_names_there_is_only_the_whole_recording(
        self, qapp, tmp_path: Path
    ) -> None:
        """Where every bench recording so far has been. The automatic onsets
        are filtered out on purpose — one row per burst is not a phase."""
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"))
        assert r["coactivation_from_markers"] is False
        assert len(r["coactivation"]) == 1

    def test_naming_them_produces_one_row_each(
        self, qapp, tmp_path: Path
    ) -> None:
        segs, nombres = _fragmentos()
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"),
                      roi_segments=segs, roi_labels=nombres)
        assert r["coactivation_from_markers"] is True
        assert [f.label for f in r["coactivation"]] == nombres

    def test_the_reciprocal_manoeuvres_and_the_grip_read_differently(
        self, qapp, tmp_path: Path
    ) -> None:
        """The demonstration the practical exists for: in flexion and
        extension one muscle leads and the other is near rest, so there is no
        co-activation to measure; in the grip both work."""
        segs, nombres = _fragmentos()
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"),
                      roi_segments=segs, roi_labels=nombres)
        flexion, extension, presa = r["coactivation"]
        assert flexion.index is None or flexion.index < presa.index
        assert extension.index is None or extension.index < presa.index
        assert presa.index is not None, presa.reason

    def test_an_unnamed_fragment_is_kept_but_opens_no_window(
        self, qapp, tmp_path: Path
    ) -> None:
        """Trimming and naming are two different acts: a stretch can be worth
        analysing without being a manoeuvre."""
        segs, _nombres = _fragmentos()
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"),
                      roi_segments=segs, roi_labels=["", "", "Grip"])
        assert [f.label for f in r["coactivation"]] == ["Grip"]
        # And all three fragments are still in the analysed signal.
        esperado = sum(b - a for a, b in segs)
        assert r["duration"] == pytest.approx(esperado, abs=0.2)

    def test_repeating_a_name_makes_one_window_of_the_several_fragments(
        self, qapp, tmp_path: Path
    ) -> None:
        """The answer to the objection the naming raised on the bench.

        Auto-suggest yields one fragment per *contraction*, so a run of six
        flexions arrives as six fragments; but the muscle that is agonist and
        the one that is antagonist are fixed by the *manoeuvre*, and the six
        are six samples of it. Naming them all «Flexion» must give one row,
        not six identical ones.
        """
        segs, _ = _fragmentos()
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"),
                      roi_segments=segs,
                      roi_labels=["Flexion", "Flexion", "Flexion"])
        assert [f.label for f in r["coactivation"]] == ["Flexion"]
        # And the one window spans all three, not just the first.
        ventana = r["coactivation"][0].window_s
        assert ventana[1] - ventana[0] == pytest.approx(
            sum(b - a for a, b in segs), abs=0.6
        )

    def test_a_name_that_comes_back_later_opens_a_second_window(
        self, qapp, tmp_path: Path
    ) -> None:
        """Only *consecutive* repeats merge. Flexion, extension, flexion is
        an alternation — three windows — because what lies between them is a
        different condition, not more of the same one."""
        segs, _ = _fragmentos()
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"),
                      roi_segments=segs,
                      roi_labels=["Flexion", "Extension", "Flexion"])
        assert [f.label for f in r["coactivation"]] == [
            "Flexion", "Extension", "Flexion",
        ]

    def test_the_windows_land_where_the_fragments_do(
        self, qapp, tmp_path: Path
    ) -> None:
        """In concatenated time: the gaps between fragments are closed up
        before the table sees them, so the second window starts where the
        first ends and not where the recording says."""
        segs, nombres = _fragmentos()
        r = _analizar(qapp, _sesion(tmp_path / "sesion.edf"),
                      roi_segments=segs, roi_labels=nombres)
        flexion, extension, _presa = r["coactivation"]
        assert flexion.window_s[0] == pytest.approx(0.0, abs=0.1)
        assert extension.window_s[0] == pytest.approx(5.0, abs=0.2)


@pytest.mark.gui
class TestTheEditorOffersTheName:
    @pytest.fixture
    def dlg(self, qapp, tmp_path: Path):
        """A dialog that is destroyed deterministically.

        Dropped instead, its matplotlib canvas is freed by the garbage
        collector at an arbitrary moment — including inside the next
        ``processEvents()``, which then raises from the C++ side. The rest of
        the suite already fights this; there is no need to add to it.
        """
        from emgteach.gui.widgets.fragment_selection import (
            FragmentSelectionDialog,
        )

        edf = _sesion(tmp_path / "sesion.edf")
        creados = []

        def crear(**kw):
            d = FragmentSelectionDialog.from_edf(
                edf, "FCR",
                {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0,
                 "f_env": 5.0},
                **kw,
            )
            creados.append(d)
            return d

        yield crear
        for d in creados:
            d.close()
            d.deleteLater()
        qapp.processEvents()

    def test_the_practicals_own_vocabulary_is_already_in_it(
        self, dlg
    ) -> None:
        """The MARK presets were not lost when the button went: they stopped
        being live labels and became the suggestions here."""
        from emgteach.profiles import EMG_PROFILE

        d = dlg(segments=[(22.0, 27.0)])
        combo = d._row_widgets[0]["label"]
        ofrecidos = {combo.itemText(i) for i in range(combo.count())}
        assert any(p in " ".join(ofrecidos) or p in ofrecidos
                   for p in EMG_PROFILE.marker_presets if p != "Other…")

    def test_a_name_typed_comes_back(self, dlg) -> None:
        d = dlg(segments=[(22.0, 27.0), (28.0, 33.0)])
        d._row_widgets[0]["label"].setCurrentText("Grip")
        assert d.labels() == ["Grip", ""]
        assert d.named_segments()[0][2] == "Grip"

    def test_reopening_restores_the_names(self, dlg) -> None:
        """Otherwise every visit to the editor would cost the naming."""
        d = dlg(segments=[(22.0, 27.0)], labels=["Grip"])
        assert d._row_widgets[0]["label"].currentText() == "Grip"

    def test_an_unnamed_row_stays_empty(self, dlg) -> None:
        d = dlg(segments=[(22.0, 27.0)])
        assert d._row_widgets[0]["label"].currentText() == ""

    def test_with_one_muscle_the_column_is_not_offered(self, dlg) -> None:
        """A name is read by one thing only: the co-activation table, which
        needs an agonist and an antagonist. Analysing a single muscle — and in
        the MVC tab always — the column asked the operator for something no
        part of the program would ever look at.
        """
        d = dlg(segments=[(22.0, 27.0)], naming=False)
        assert d._table.isColumnHidden(4)

    def test_with_two_muscles_it_is(self, dlg) -> None:
        d = dlg(segments=[(22.0, 27.0)], naming=True)
        assert not d._table.isColumnHidden(4)

    def test_the_naming_paragraph_goes_with_it(self, dlg) -> None:
        """The dialogue is a secondary tool most sessions never open. Half its
        text explained a column that is not there."""
        def texto(d) -> str:
            from PySide6.QtWidgets import QLabel
            # The explanation is the longest label in the dialogue.
            return max((w.text() for w in d.findChildren(QLabel)), key=len)

        con = texto(dlg(segments=[(22.0, 27.0)], naming=True))
        sin = texto(dlg(segments=[(22.0, 27.0)], naming=False))
        assert sin in con and len(sin) < len(con)


class TestTheNamesSurviveInTheTunedFile:
    def test_they_are_written_at_their_own_start(self, tmp_path: Path) -> None:
        """The naming outlives the session it was done in, so a derived file
        opens with its table already filled."""
        pytest.importorskip("pyedflib")
        from emgteach.tuning import build_tuned_edf, tuned_path

        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        segs, nombres = _fragmentos()
        build_tuned_edf(src, dst, fragments=segs, fragment_labels=nombres,
                        when=datetime(2026, 9, 1, 10, 0))
        marcas = {t: o for o, t in read_edf_markers(dst)}
        assert set(nombres) <= set(marcas)
        # The first manoeuvre opens the recording phase; the second follows it
        # once the gap between them is closed up.
        assert marcas["Flexion"] == pytest.approx(REC_S, abs=0.1)
        assert marcas["Extension"] == pytest.approx(REC_S + 5.0, abs=0.2)

    def test_the_phases_still_survive_beside_them(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        from emgteach.tuning import build_tuned_edf, tuned_path

        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        segs, nombres = _fragmentos()
        build_tuned_edf(src, dst, fragments=segs, fragment_labels=nombres,
                        when=datetime(2026, 9, 1, 10, 0))
        fases = parse_phase_markers(read_edf_markers(dst))
        assert fases.rec_start_s == pytest.approx(REC_S)
        assert len(fases.cal_reps) == 4

    def test_an_unnamed_fragment_writes_nothing(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        from emgteach.tuning import build_tuned_edf, tuned_path

        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        segs, _n = _fragmentos()
        build_tuned_edf(src, dst, fragments=segs,
                        fragment_labels=["", "", "Grip"],
                        when=datetime(2026, 9, 1, 10, 0))
        textos = [t for _o, t in read_edf_markers(dst)]
        assert "Grip" in textos
        assert "Flexion" not in textos
