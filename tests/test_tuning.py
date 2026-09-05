"""El EDF afinado: las decisiones del análisis, escritas de vuelta.

Dos decisiones se toman en pantalla y hasta ahora vivían solo ahí —qué
repeticiones de calibración cuentan y qué tramo de la tarea es la tarea—, y las
dos mueven todos los porcentajes de la sesión. El mismo fichero abierto en otro
sitio contaba otra historia.

Lo que estas pruebas defienden es la trazabilidad, no la comodidad. Un fichero
«afinado» de origen desconocido es peor que no tener la función:

* el original **no se sobrescribe nunca**, ni aunque se pida;
* el derivado **dice que lo es**, en la cabecera y en anotaciones;
* las fases sobreviven, y **reabrirlo da la misma referencia** que había en
  pantalla, que es lo único que hace útil guardar la decisión.

Dos hallazgos medidos aquí, no supuestos, y ambos de la misma familia que el
artículo de la escritura tamponada —pérdida silenciosa en un EDF—:

* **una anotación EDF+ guarda 40 bytes** y el byte 41 no da error, simplemente
  no está al releer —y si el corte parte un carácter por la mitad, el fichero
  entero deja de poder abrirse;
* **`recording_additional`, `technician` y `equipment` comparten 80 caracteres**,
  y en un registro real están casi gastados: marcar ahí la derivación truncaba
  el protocolo en vez de caber a su lado.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from emgteach.dsp import process_offline
from emgteach.io import (
    BufferedEdfWriter,
    ChannelInfo,
    RecordingMetadata,
    edf_duration,
    read_edf_markers,
    read_edf_metadata,
    read_edf_pyedflib,
)
from emgteach.mvc import mvc_ref_marker
from emgteach.phases import (
    FROM_REPS,
    cal_end_marker,
    cal_start_marker,
    mvc_reference,
    parse_phase_markers,
    prep_start_marker,
    rec_start_marker,
    warmup_start_marker,
)
from emgteach.profiles import EMG_PROFILE
from emgteach.tuning import (
    DERIVED_PREFIX,
    build_tuned_edf,
    is_derived,
    tuned_path,
)

FS = 1000
DURACION = 50
CAL = [(4.0, 8.0, 1.00), (12.0, 16.0, 1.40), (20.0, 24.0, 1.20)]
PREP_S = 26.0
REC_S = 30.0
CUANDO = datetime(2026, 8, 31, 20, 30)


def _sesion(path: Path, *, protocolo: str = "agonist/antagonist") -> str:
    t = np.arange(DURACION * FS) / FS
    amp = np.full(t.size, 0.01)
    for a, b, valor in CAL:
        amp[int(a * FS) : int(b * FS)] = valor
    for a, b in ((32.0, 36.0), (40.0, 44.0)):
        amp[int(a * FS) : int(b * FS)] = 0.30
    senal = np.sin(2 * np.pi * 80 * t) * amp
    meta = RecordingMetadata(
        student_name="Ada Lovelace", student_code="A1",
        protocol=protocolo, equipment="BITalino (98:D3:91:FE:44:E4)",
    )
    with BufferedEdfWriter(
        str(path),
        channels=[ChannelInfo("FCR", dimension="mV", sample_frequency=FS)],
        metadata=meta,
    ) as w:
        w.add_samples(senal)
        w.add_annotation(0.1, warmup_start_marker())
        for i, (a, b, _amp) in enumerate(CAL, start=1):
            w.add_annotation(a, cal_start_marker(0, i))
            w.add_annotation(b, cal_end_marker(0, i))
        w.add_annotation(PREP_S, prep_start_marker())
        w.add_annotation(REC_S, rec_start_marker())
        w.add_annotation(34.0, "Grip")
        w.add_annotation(42.0, "Grip")
    return str(path)


def _referencia(path: str, canal: int = 0) -> tuple[float | None, str]:
    d = read_edf_pyedflib(path, canal)
    env = process_offline(d["emg_raw"], d["sfreq"])["emg_envelope"]
    fases = parse_phase_markers(d["markers"])
    return mvc_reference(
        canal, phases=fases, envelope=env, fs=d["sfreq"],
        percentile=EMG_PROFILE.mvc_percentile,
        window_s=EMG_PROFILE.mvc_peak_window_s,
    )


def _sesion_fv(path: Path) -> str:
    """A kinematics session: calibration, then four loads lifted three times."""
    from emgteach.force_velocity import fv_load_marker

    dur = 120
    t = np.arange(dur * FS) / FS
    amp = np.full(t.size, 0.01)
    for a, b, valor in CAL:
        amp[int(a * FS) : int(b * FS)] = valor
    levantamientos = []
    inicio = 34.0
    for kg in (2.0, 3.4, 5.0, 7.0):
        for _ in range(3):
            levantamientos.append((inicio, kg))
            amp[int((inicio + 2.0) * FS) : int((inicio + 4.0) * FS)] = 0.30
            inicio += 7.0
    senal = np.sin(2 * np.pi * 80 * t) * amp
    with BufferedEdfWriter(
        str(path),
        channels=[ChannelInfo("Musculo", dimension="mV", sample_frequency=FS)],
    ) as w:
        w.add_samples(senal)
        w.add_annotation(0.1, warmup_start_marker())
        for i, (a, b, _amp) in enumerate(CAL, start=1):
            w.add_annotation(a, cal_start_marker(0, i))
            w.add_annotation(b, cal_end_marker(0, i))
        w.add_annotation(PREP_S, prep_start_marker())
        w.add_annotation(REC_S, rec_start_marker())
        for cue, kg in levantamientos:
            w.add_annotation(cue, fv_load_marker(kg))
    # The fragments the editor would propose: the effort, not the pause
    # before it in which the wizard called the load out.
    tramos = [(cue + 1.8, cue + 4.2) for cue, _kg in levantamientos]
    return str(path), tramos, levantamientos


class TestTheLoadsSurviveTheTrimming:
    """The wizard writes each load where it *asks* for the lift.

    Which is the pause before it — precisely the stretch the fragment editor
    throws away. Under the rule «an annotation survives if it falls inside a
    kept fragment» the tuned recording of 5 September kept four of its twelve
    loads, silently, and the force-velocity study read from that file would
    have been a study of four points instead of twelve.
    """

    def test_every_kept_fragment_carries_its_load(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        from emgteach.force_velocity import parse_fv_load_markers

        src, tramos, esperadas = _sesion_fv(tmp_path / "cinematica.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=tramos, when=CUANDO)

        cargas = parse_fv_load_markers(read_edf_markers(dst))
        assert [kg for _t, kg in cargas] == [kg for _c, kg in esperadas]

    def test_each_one_lands_at_the_start_of_its_own_fragment(
        self, tmp_path: Path
    ) -> None:
        """Where the analysis will look for it: the load of a contraction is
        the last one called before its middle."""
        pytest.importorskip("pyedflib")
        from emgteach.force_velocity import parse_fv_load_markers

        src, tramos, _e = _sesion_fv(tmp_path / "cinematica.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=tramos, when=CUANDO)

        cargas = parse_fv_load_markers(read_edf_markers(dst))
        cursor = REC_S
        for (a, b), (t, _kg) in zip(tramos, cargas, strict=True):
            assert t == pytest.approx(cursor, abs=0.05)
            cursor += b - a

    def test_a_fragment_from_before_the_first_load_is_given_none(
        self, tmp_path: Path
    ) -> None:
        """A stray effort is not guessed at."""
        pytest.importorskip("pyedflib")
        from emgteach.force_velocity import parse_fv_load_markers

        src, tramos, _e = _sesion_fv(tmp_path / "cinematica.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(31.0, 33.0), *tramos],
                        when=CUANDO)
        cargas = parse_fv_load_markers(read_edf_markers(dst))
        assert len(cargas) == len(tramos)
        assert cargas[0][0] > REC_S + 1.9    # not on the stray one

    def test_a_fragment_drawn_before_its_cue_still_gets_that_load(
        self, tmp_path: Path
    ) -> None:
        """Decided on the middle of the fragment, as the analysis decides it.

        On the bench recording of 5 September the editor had drawn one lift's
        fragment starting a little *before* the cue that called for it, and
        deciding on the start put it under the previous load: the derived
        file came back with four lifts at 2 kg and two at 3.4.
        """
        pytest.importorskip("pyedflib")
        from emgteach.force_velocity import parse_fv_load_markers

        src, _tramos, esperadas = _sesion_fv(tmp_path / "cinematica.edf")
        # Every fragment opened a second earlier than the cue it belongs to.
        adelantados = [(cue - 1.0, cue + 4.2) for cue, _kg in esperadas]
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=adelantados, when=CUANDO)

        cargas = parse_fv_load_markers(read_edf_markers(dst))
        assert [kg for _t, kg in cargas] == [kg for _c, kg in esperadas]


class TestAnAnnotationIsCutByBytes:
    """One byte of a character is not UTF-8, and it costs the whole file.

    The line that says what a derived file kept was trimmed to forty
    *characters* and then given an ellipsis — three bytes — of which only
    the first fitted in the forty *bytes* the format holds. The recording
    tuned on 5 September could not be reopened at all: MNE reads the
    annotation channel strictly and refused the file, a hundred seconds of
    signal lost to a typographic flourish.
    """

    def test_the_derived_file_can_be_read_back(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        pytest.importorskip("mne")
        from emgteach.io import read_edf_mne

        src = _sesion(tmp_path / "un nombre de fichero larguisimo.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(32.0, 36.0)], when=CUANDO)
        assert len(read_edf_mne(str(dst), "FCR")["emg_raw"]) > 0

    def test_no_annotation_holds_half_a_character(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "un nombre de fichero larguisimo.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(32.0, 36.0)],
                        fragment_labels=["Contracción sostenida del músculo "
                                         "flexor radial del carpo"],
                        when=CUANDO)
        for _t, texto in read_edf_markers(dst):
            assert len(str(texto).encode("utf-8")) <= 40
            str(texto).encode("utf-8").decode("utf-8")   # no half characters


class TestTheOriginalIsNeverTouched:
    def test_the_proposed_name_is_beside_it_and_free(self, tmp_path: Path) -> None:
        src = tmp_path / "sesion.edf"
        src.write_bytes(b"x")
        assert tuned_path(src).name == "sesion_tuned.edf"

    def test_a_name_already_taken_gets_a_counter(self, tmp_path: Path) -> None:
        src = tmp_path / "sesion.edf"
        src.write_bytes(b"x")
        (tmp_path / "sesion_tuned.edf").write_bytes(b"x")
        assert tuned_path(src).name == "sesion_tuned_2.edf"

    def test_writing_over_the_source_is_refused(self, tmp_path: Path) -> None:
        """Tuning discards signal, so its input has to stay recoverable."""
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        with pytest.raises(ValueError):
            build_tuned_edf(src, src, when=CUANDO)

    def test_the_source_is_byte_for_byte_the_same_afterwards(
        self, tmp_path: Path
    ) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        antes = Path(src).read_bytes()
        build_tuned_edf(src, tuned_path(src), fragments=[(32.0, 36.0)],
                        when=CUANDO)
        assert Path(src).read_bytes() == antes


class TestTheDerivedFileSaysSo:
    @pytest.fixture
    def afinado(self, tmp_path: Path) -> Path:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, keep={0: {2, 3}},
                        fragments=[(32.0, 36.0)], when=CUANDO)
        return dst

    def test_in_its_annotations(self, afinado: Path) -> None:
        marcas = read_edf_markers(afinado)
        assert is_derived(marcas)
        derivadas = [t for _o, t in marcas if t.startswith(DERIVED_PREFIX)]
        assert any("sesion.edf" in t for t in derivadas)
        assert any("2026-08-31T20:30" in t for t in derivadas)
        assert any("cal=2/3" in t for t in derivadas)

    def test_none_of_them_is_silently_cut(self, afinado: Path) -> None:
        """An EDF+ annotation holds forty characters and the forty-first does
        not raise — it is simply absent when the file is read back. Measured,
        which is why the traceability is three lines and not one."""
        derivadas = [t for _o, t in read_edf_markers(afinado)
                     if t.startswith(DERIVED_PREFIX)]
        assert len(derivadas) == 3
        assert all(len(t) <= 40 and not t.endswith("…") for t in derivadas)

    def test_in_the_header(self, afinado: Path) -> None:
        meta = read_edf_metadata(afinado)
        assert meta.patient_additional.startswith(DERIVED_PREFIX)
        assert "sesion.edf" in meta.patient_additional

    def test_the_protocol_survives_being_marked(self, afinado: Path) -> None:
        """recording_additional, technician and equipment share eighty
        characters, and a real device string spends twenty-eight of them.
        Writing the derivation there truncated the protocol instead of fitting
        beside it: "agonist/antagonist" came back as "ag"."""
        assert read_edf_metadata(afinado).protocol.startswith("agonist")

    def test_the_students_name_does_not_travel(self, afinado: Path) -> None:
        """The derived file is the one that ends up circulating, so it carries
        the code and not the name."""
        meta = read_edf_metadata(afinado)
        assert "Ada" not in meta.student_name
        assert "Ada" not in meta.patient_additional


class TestReopeningItGivesTheSameAnswer:
    """The point of saving the decision at all."""

    def test_the_reference_is_the_one_that_was_on_screen(
        self, tmp_path: Path
    ) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        entera, _f = _referencia(src)
        dst = tuned_path(src)
        build_tuned_edf(src, dst, keep={0: {1, 3}}, when=CUANDO)

        recortada, fuente = _referencia(str(dst))
        assert fuente == FROM_REPS
        # Discarding the best of 1.00 / 1.40 / 1.20 leaves 1.20.
        assert recortada / entera == pytest.approx(1.20 / 1.40, rel=0.02)

    def test_the_discarded_repetitions_lose_their_spans(
        self, tmp_path: Path
    ) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, keep={0: {1, 3}}, when=CUANDO)
        fases = parse_phase_markers(read_edf_markers(dst))
        assert [r.rep for r in fases.cal_reps] == [1, 3]

    def test_the_phases_survive(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(32.0, 36.0)], when=CUANDO)
        fases = parse_phase_markers(read_edf_markers(dst))
        assert fases.warmup_start_s == pytest.approx(0.1)
        assert fases.prep_start_s == pytest.approx(PREP_S)
        # ``REC start`` sits exactly at the phase boundary and is not inside
        # any kept fragment. Left to the general rule it was dropped, and the
        # derived file reopened as a recording with no phases at all.
        assert fases.rec_start_s == pytest.approx(REC_S)

    def test_a_cached_reference_is_written_to_agree_with_the_spans(
        self, tmp_path: Path
    ) -> None:
        """A file that carries both must never carry two different answers."""
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, references={0: 0.4242}, when=CUANDO)
        assert any(t == mvc_ref_marker(0, 0.4242)
                   for _o, t in read_edf_markers(dst))


class TestOnlyTheRecordingPhaseIsTrimmed:
    def test_the_calibration_keeps_its_samples(self, tmp_path: Path) -> None:
        """It has to, or the reference could not be recomputed from a file
        that claims to carry it."""
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(32.0, 36.0)], when=CUANDO)
        assert edf_duration(dst) == pytest.approx(REC_S + 4.0, abs=0.5)

    def test_two_fragments_are_closed_up(self, tmp_path: Path) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(32.0, 36.0), (40.0, 44.0)],
                        when=CUANDO)
        assert edf_duration(dst) == pytest.approx(REC_S + 8.0, abs=0.5)

    def test_a_marker_inside_a_kept_fragment_moves_with_it(
        self, tmp_path: Path
    ) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(40.0, 44.0)], when=CUANDO)
        marcas = [o for o, t in read_edf_markers(dst) if t == "Grip"]
        # The one at 42 s was 2 s into its fragment and stays 2 s into it.
        assert marcas == [pytest.approx(REC_S + 2.0, abs=0.1)]

    def test_a_marker_in_a_discarded_stretch_is_gone(
        self, tmp_path: Path
    ) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, fragments=[(40.0, 44.0)], when=CUANDO)
        assert len([o for o, t in read_edf_markers(dst) if t == "Grip"]) == 1

    def test_with_nothing_chosen_the_whole_recording_is_kept(
        self, tmp_path: Path
    ) -> None:
        pytest.importorskip("pyedflib")
        src = _sesion(tmp_path / "sesion.edf")
        dst = tuned_path(src)
        build_tuned_edf(src, dst, when=CUANDO)
        assert edf_duration(dst) == pytest.approx(DURACION, abs=0.5)
