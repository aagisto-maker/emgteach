"""What the fragment editor proposes, fixed before its algorithm leaves the window.

The automatic suggestion — the detection over the span, one row per lift, the
rows widened to the envelope, the hundredths — lived inside
``FragmentSelectionDialog``. These cases record what it proposed on the day it
was taken out into a module without Qt (encargo D, 14 Oct 2026): the same
inputs have to give the same rows, to the hundredth, before and after.

Four synthetic recordings and a real one: the author's own recording of the
three manoeuvres, ``docs/informe-sourcebook/ejemplo_tres_maniobras.edf``, read
as ``tools/hoja_puesto.py`` reads it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

FS = 1000
FILTROS = {"f_low": 20.0, "f_high": 450.0, "f_notch": 50.0, "f_env": 5.0}
EJEMPLO = (Path(__file__).resolve().parents[1]
           / "docs" / "informe-sourcebook" / "ejemplo_tres_maniobras.edf")


def _senal(rafagas, duracion_s: float, semilla: int, amplitud: float = 0.5) -> np.ndarray:
    """Noise with 90 Hz bursts: ``(start, end)`` or ``(start, end, amplitude)``."""
    rng = np.random.default_rng(semilla)
    sig = rng.normal(0.0, 0.01, size=int(duracion_s * FS))
    for a, b, *g in rafagas:
        i0, i1 = int(a * FS), int(b * FS)
        t = np.arange(i1 - i0) / FS
        sig[i0:i1] += (g[0] if g else amplitud) * np.sin(2 * np.pi * 90.0 * t)
    return sig


#: One muscle, two strong bursts and a weak one that only the default
#: sensitivity finds.
UNO = _senal([(2.0, 3.5), (6.0, 7.5), (8.2, 8.9, 0.015)], 10, 0)
#: Two muscles: a calibration-like burst before the span, then one led by
#: each muscle and one by both.
PAR_1 = _senal([(1.0, 2.0, 1.5), (5.0, 6.0), (9.0, 10.0, 0.1), (13.0, 14.0, 0.4)], 16, 1)
PAR_2 = _senal([(1.0, 2.0, 1.5), (5.0, 6.0, 0.1), (9.0, 10.0), (13.0, 14.0, 0.4)], 16, 2)
#: Three lifts: one split at a dip, one with no burst in its window, one whole;
#: and a stray burst no cue owns.
LEVANTAMIENTOS = _senal([(10.3, 10.8), (10.82, 11.6), (30.2, 31.4), (40.0, 41.0)], 45, 3)
VENTANAS = [(10.0, 12.0), (20.0, 22.0), (30.0, 32.0)]

#: What the editor proposed on 14 Oct 2026, before the move.
ESPERADO = {
    "uno": [(1.87, 3.63, ""), (5.87, 7.63, ""), (8.12, 8.98, "")],
    "uno_k6": [(1.87, 3.63, ""), (5.87, 7.63, "")],
    "par": [(4.87, 6.13, "FCR"), (8.87, 10.13, "ECR"), (12.87, 14.13, "Co-activation")],
    "levantamientos": [(10.17, 11.73, ""), (25.41, 25.91, ""), (30.07, 31.53, "")],
    "tres_maniobras": [
        (58.55, 59.46, "FCR"), (60.2, 61.54, "FCR"), (62.08, 63.71, "FCR"),
        (64.27, 65.83, "FCR"), (66.34, 67.27, "FCR"), (68.03, 69.14, "FCR"),
        (70.55, 72.3, "Co-activation"), (74.76, 76.17, "ECR"),
        (76.18, 77.73, "Co-activation"), (77.74, 78.76, "ECR"),
        (79.44, 80.58, "Co-activation"), (80.87, 82.16, "ECR"),
        (82.33, 83.23, "Co-activation"), (89.63, 97.47, "FCR"),
    ],
}


def _filas(dlg) -> list[tuple[float, float, str]]:
    if dlg._naming:
        return [(round(a, 2), round(b, 2), n) for a, b, n in dlg.named_segments()]
    return [(round(a, 2), round(b, 2), "") for a, b in dlg.selected_segments()]


def _dialogo(caso: str):
    from emgteach.gui.widgets.fragment_selection import FragmentSelectionDialog

    if caso == "uno":
        return FragmentSelectionDialog(UNO, FS, FILTROS, naming=False)
    if caso == "uno_k6":
        return FragmentSelectionDialog(UNO, FS, FILTROS, naming=False,
                                       detection={"k": 6.0})
    if caso == "par":
        return FragmentSelectionDialog(PAR_1, FS, FILTROS, raw_2=PAR_2,
                                       name_1="FCR", name_2="ECR",
                                       span=(3.0, 16.0), default_k=4.4)
    if caso == "levantamientos":
        return FragmentSelectionDialog(LEVANTAMIENTOS, FS, FILTROS, naming=False,
                                       lifts=VENTANAS)
    from emgteach.force_velocity import parse_fv_load_markers
    from emgteach.io import edf_duration, read_edf_markers
    from emgteach.modes import MODE_PAIR, mode_detection_k
    from emgteach.mvc import parse_mvc_ref_markers
    from emgteach.phases import parse_phase_markers
    from emgteach.profiles import EMG_PROFILE

    marcas = read_edf_markers(str(EJEMPLO))
    refs = parse_mvc_ref_markers(marcas)
    tramo = parse_phase_markers(marcas).rec_span(
        edf_duration(str(EJEMPLO)), parse_fv_load_markers(marcas))
    return FragmentSelectionDialog.from_edf(
        str(EJEMPLO), "FCR", dict(EMG_PROFILE.filter_kwargs()), span=tramo,
        channel_name_2="ECR", default_k=mode_detection_k(MODE_PAIR),
        mvc_ref=refs.get(0), mvc_ref_2=refs.get(1))


@pytest.mark.gui
@pytest.mark.parametrize("caso", list(ESPERADO))
def test_the_editor_proposes_what_it_proposed(qapp, caso: str) -> None:
    dlg = _dialogo(caso)
    try:
        assert _filas(dlg) == ESPERADO[caso]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# The same proposals from emgteach.fragments, with no window
# ---------------------------------------------------------------------------


def _entradas(caso: str) -> tuple[np.ndarray, float, dict]:
    """``(raw, fs, keyword arguments)`` of suggest_fragments for each case."""
    if caso == "uno":
        return UNO, FS, {}
    if caso == "uno_k6":
        return UNO, FS, {"detection": {"k": 6.0}}
    if caso == "par":
        return PAR_1, FS, {"raw_2": PAR_2, "span": (3.0, 16.0), "default_k": 4.4}
    if caso == "levantamientos":
        return LEVANTAMIENTOS, FS, {"lifts": VENTANAS}
    from emgteach.force_velocity import parse_fv_load_markers
    from emgteach.fragments import read_channels
    from emgteach.io import edf_duration, read_edf_markers
    from emgteach.modes import MODE_PAIR, mode_detection_k
    from emgteach.phases import parse_phase_markers

    marcas = read_edf_markers(str(EJEMPLO))
    tramo = parse_phase_markers(marcas).rec_span(
        edf_duration(str(EJEMPLO)), parse_fv_load_markers(marcas))
    raw, fs, raw_2 = read_channels(str(EJEMPLO), "FCR", "ECR")
    return raw, fs, {"raw_2": raw_2, "span": tramo,
                     "default_k": mode_detection_k(MODE_PAIR)}


@pytest.mark.parametrize("caso", list(ESPERADO))
def test_the_module_proposes_the_same_rows(caso: str) -> None:
    """The rows, without the names: naming is the editor's, after the proposal."""
    from emgteach.fragments import suggest_fragments
    from emgteach.profiles import EMG_PROFILE

    raw, fs, opciones = _entradas(caso)
    filtros = dict(EMG_PROFILE.filter_kwargs()) if caso == "tres_maniobras" else FILTROS
    filas = suggest_fragments(raw, fs, filtros, **opciones)
    assert [(round(f.start_s, 2), round(f.end_s, 2)) for f in filas] == [
        (a, b) for a, b, _n in ESPERADO[caso]]


def test_the_module_does_not_bring_qt_in() -> None:
    """Imported in a fresh interpreter, and a proposal made, Qt is never loaded."""
    import json
    import os
    import subprocess
    import sys

    import emgteach

    src = str(Path(emgteach.__file__).resolve().parents[1])
    code = (
        "import json, sys\n"
        "import numpy as np\n"
        "from emgteach.fragments import suggest_fragments\n"
        "rng = np.random.default_rng(0)\n"
        "raw = rng.normal(0.0, 0.01, 5000)\n"
        "raw[2000:3000] += 0.5 * np.sin(2 * np.pi * 90.0 * np.arange(1000) / 1000)\n"
        "print(len(suggest_fragments(raw, 1000.0, {})))\n"
        "print('MODULES=' + json.dumps(sorted({m.split('.')[0] for m in sys.modules})))\n"
    )
    paths = [src, os.environ.get("PYTHONPATH", "")]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in paths if p)}
    run = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                         text=True, encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.splitlines()[0] == "1"
    line = next(ln for ln in run.stdout.splitlines() if ln.startswith("MODULES="))
    assert "PySide6" not in json.loads(line.removeprefix("MODULES="))
