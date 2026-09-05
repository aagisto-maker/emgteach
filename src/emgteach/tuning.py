"""Saving a tuned EDF: the decisions made in the analysis, written back.

Two decisions are taken on screen and, until now, lived only there: **which
calibration repetitions count** and **which stretch of the task is the task**.
Both move every percentage in the session, and both were lost when the tab was
closed — so the same file reopened somewhere else told a different story, and
the two tabs could disagree about the same recording.

This writes them back into a **new** file, and the rule it exists to enforce is
traceability rather than convenience:

* **The original is never overwritten.** A derived name is proposed and, if
  something is already there, a counter is added rather than anything being
  replaced. A file "tuned" over its own source cannot be un-tuned.
* **The derived file says that it is one**, in the header and in an annotation:
  where it came from, what was kept of each phase, and when it was made.
  Without that the laboratory ends up with tuned files of unknown origin, which
  is worse than not having the feature.
* **The phases survive.** The calibration keeps its own samples and the spans
  of the repetitions that were kept; the discarded ones lose their ``CAL``
  annotations, so reopening the file recomputes exactly the reference that was
  on screen.

What is trimmed is the **recording phase only**. Everything up to ``REC start``
is copied through untouched — the calibration has to stay whole, or the
reference could not be recomputed from a file that claims to carry it — and
after it only the kept fragments, concatenated. The joins are discontinuities,
the same ones the analysis already works on when fragments are chosen; the
difference is that here they are in the file, where they can be seen.

And the header's ``patientname`` becomes the **student code**. It carries the
name in the original, and the derived file is the one that ends up circulating.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from emgteach.force_velocity import parse_fv_load_markers
from emgteach.io import (
    MAX_ANNOTATION_BYTES,
    ChannelInfo,
    RecordingMetadata,
    annotation_text,
    read_edf_markers,
    read_edf_metadata,
)
from emgteach.phases import (
    cal_end_marker,
    cal_start_marker,
    parse_phase_markers,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["DERIVED_PREFIX", "TunedSummary", "build_tuned_edf", "tuned_path"]

#: How a derived file announces itself, in the header and in an annotation at
#: t=0. A prefix and not a free sentence: whatever reads it later — a person, a
#: script, this program — needs one thing to look for.
DERIVED_PREFIX = "DERIVED"

_SUFIJO = "_tuned"

#: What an EDF+ annotation actually holds. Measured against pyedflib: a
#: forty-first *byte* does not raise, it simply is not there when the file
#: is read back — which is the same family of silent loss the buffered-write
#: paper is about.
_MAX_ANOTACION = MAX_ANNOTATION_BYTES


def _corta(texto: str) -> str:
    """Trim to what an annotation can hold, saying so when it has to.

    Bytes, not characters: this line used to be cut at the fortieth
    character, and the ellipsis it then added — three bytes — was itself
    cut after the first. One byte of a character is not UTF-8, and the
    tuned recording of 5 September could not be reopened at all because of
    it. See :func:`emgteach.io.annotation_text`.
    """
    return annotation_text(texto, _MAX_ANOTACION)


def tuned_path(source: str | Path, *, suffix: str = _SUFIJO) -> Path:
    """A derived path beside the original that does not exist yet.

    ``session.edf`` becomes ``session_tuned.edf``, then ``session_tuned_2.edf``
    and so on. Never returns the source itself, and never a path already in
    use: tuning is a lossy operation and its input has to stay recoverable.
    """
    src = Path(source)
    base = src.with_name(f"{src.stem}{suffix}{src.suffix}")
    if not base.exists():
        return base
    n = 2
    while True:
        cand = src.with_name(f"{src.stem}{suffix}_{n}{src.suffix}")
        if not cand.exists():
            return cand
        n += 1


class TunedSummary:
    """What the derived file kept, for the log and for the annotation."""

    def __init__(self, source: Path, dest: Path, *, reps_kept: int,
                 reps_total: int, fragments: int, kept_s: float,
                 full_s: float) -> None:
        self.source = source
        self.dest = dest
        self.reps_kept = reps_kept
        self.reps_total = reps_total
        self.fragments = fragments
        self.kept_s = kept_s
        self.full_s = full_s

    def as_annotations(self, when: datetime) -> tuple[str, ...]:
        """The traceability the derived file carries at t=0.

        Three lines, not one, because **an EDF+ annotation holds forty
        bytes** and anything longer comes back silently cut — measured,
        not assumed. Each one starts with the same prefix so a reader can
        collect them without knowing how many there are, and each says what it
        is, so an over-long filename costs the origin line and nothing else.
        """
        return (
            _corta(f"{DERIVED_PREFIX} from {self.source.name}"),
            _corta(f"{DERIVED_PREFIX} at {when.strftime('%Y-%m-%dT%H:%M')}"),
            _corta(
                f"{DERIVED_PREFIX} kept cal={self.reps_kept}/{self.reps_total} "
                f"rec={self.kept_s:.1f}/{self.full_s:.1f}s f={self.fragments}"
            ),
        )


def _cabe_en_edf(valor: float, *, hacia_arriba: bool) -> float:
    """The nearest value to ``valor`` that EDF+ can store without truncating.

    A physical minimum or maximum gets eight characters in the header, and
    pyedflib truncates anything longer — silently changing the digital-to-
    physical mapping of every sample. The gain correction leaves values like
    ``-1.6352799999999998``, so this is not hypothetical.

    Rounded **outward**, never inward: a range that closes in on the signal
    clips its extremes, which is a worse fault than the last decimal.
    """
    from math import ceil, floor

    for decimales in range(6, -1, -1):
        escala = 10.0 ** decimales
        v = (ceil(valor * escala) if hacia_arriba else floor(valor * escala)) / escala
        if len(f"{v:.{decimales}f}".rstrip("0").rstrip(".") or "0") <= 8:
            return float(f"{v:.{decimales}f}")
    return float(round(valor))


def _tramos_conservados(
    fragments: Sequence[tuple[float, float]] | None,
    rec_start_s: float,
    duration_s: float,
) -> list[tuple[float, float]]:
    """The stretches of the recording phase to keep, in file time."""
    if not fragments:
        return [(rec_start_s, duration_s)]
    limpios = []
    for a, b in fragments:
        ini = max(float(a), rec_start_s)
        fin = min(float(b), duration_s)
        if fin > ini:
            limpios.append((ini, fin))
    return sorted(limpios) or [(rec_start_s, duration_s)]


def _reetiquetar(
    markers: Sequence[tuple[float, str]],
    keep: dict[int, set[int]] | None,
    tramos: Sequence[tuple[float, float]],
    rec_start_s: float,
) -> list[tuple[float, str]]:
    """Move the annotations into the derived file's timeline.

    Before ``REC start`` nothing moves. After it, an annotation survives only
    if it falls inside a kept fragment, and it lands where that fragment lands
    once the gaps are closed up.

    The load markers of the force-velocity wizard are the exception, and they
    have to be: the wizard writes each one when it *asks* for the lift, so it
    sits in the pause before it, which is exactly the stretch the fragment
    editor throws away. Under the general rule the recording of 5 September
    kept four of its twelve loads, and a study of force against velocity with
    two thirds of the loads missing is not a study of anything. So each kept
    fragment is given the load that was last called for before it, written at
    the fragment's own start.
    """
    fases = parse_phase_markers(markers)
    descartadas = set()
    if keep:
        for r in fases.cal_reps:
            guardadas = keep.get(r.channel_index)
            if guardadas is not None and r.rep not in guardadas:
                descartadas.add((r.channel_index, r.rep))

    fuera = set()
    for canal, rep in descartadas:
        fuera.add(cal_start_marker(canal, rep))
        fuera.add(cal_end_marker(canal, rep))

    cargas = parse_fv_load_markers(markers)
    salida: list[tuple[float, str]] = []
    for t, texto in markers:
        if str(texto) in fuera:
            continue
        if parse_fv_load_markers([(t, texto)]) and t > rec_start_s:
            continue                       # re-issued per fragment, below
        if t <= rec_start_s:
            # ``REC start`` itself sits exactly here, and "inside a kept
            # fragment" is false for it: the first fragment begins later. Left
            # to the general rule the derived file lost its recording phase
            # altogether and reopened as a recording with no phases at all.
            salida.append((float(t), str(texto)))
            continue
        desplazado = _en_tiempo_recortado(float(t), tramos, rec_start_s)
        if desplazado is not None:
            salida.append((desplazado, str(texto)))
    salida.extend(_cargas_por_tramo(cargas, tramos, rec_start_s))
    return sorted(salida, key=lambda m: m[0])


def _cargas_por_tramo(
    cargas: Sequence[tuple[float, float]],
    tramos: Sequence[tuple[float, float]],
    rec_start_s: float,
) -> list[tuple[float, str]]:
    """One load marker per kept fragment, at the fragment's own start.

    The load is the last one the wizard called for at or before the fragment
    begins; a fragment from before the first cue — a stray effort, a
    rehearsal — is given none rather than a guess.
    """
    from emgteach.force_velocity import fv_load_marker

    ordenadas = sorted((float(t), float(kg)) for t, kg in cargas)
    if not ordenadas:
        return []
    salida: list[tuple[float, str]] = []
    cursor = rec_start_s
    for a, b in tramos:
        kg = None
        for onset, valor in ordenadas:
            if onset <= a + 0.5:           # half a second of slack for a
                kg = valor                 # fragment drawn on the cue itself
            else:
                break
        if kg is not None:
            salida.append((cursor, fv_load_marker(kg)))
        cursor += b - a
    return salida


def _en_tiempo_recortado(
    t: float, tramos: Sequence[tuple[float, float]], rec_start_s: float
) -> float | None:
    """Where ``t`` lands once the discarded stretches are closed up, or None."""
    cursor = rec_start_s
    for a, b in tramos:
        if a <= t < b:
            return cursor + (t - a)
        cursor += b - a
    return None


def build_tuned_edf(
    source: str | Path,
    dest: str | Path,
    *,
    keep: dict[int, set[int]] | None = None,
    fragments: Sequence[tuple[float, float]] | None = None,
    fragment_labels: Sequence[str] | None = None,
    references: dict[int, float] | None = None,
    when: datetime | None = None,
) -> TunedSummary:
    """Write ``source`` to ``dest`` with the analysis's decisions baked in.

    Parameters
    ----------
    keep
        Calibration repetitions to keep, by 0-based channel index. The spans of
        the rest lose their annotations, so the file's own definition of its
        calibration is the one that was chosen.
    fragments
        Stretches of the recording phase to keep, in file time. ``None`` keeps
        the whole phase.
    fragment_labels
        What the operator calls each of them, in the same order. A named
        fragment is written as an annotation at its own start, which is what
        makes it a window of the co-activation table when the file is reopened
        — the naming survives the session it was done in, and the derived file
        opens with its table already filled.
    references
        The recomputed reference per channel, written as a fresh ``MVC ref``
        annotation so the cached value agrees with the spans that are left.
    when
        Timestamp for the traceability annotation. Passed in rather than taken
        here so the caller — and the tests — decide it.

    Returns
    -------
    TunedSummary
        What was kept, for the log.
    """
    from pyedflib import highlevel

    from emgteach.io import BufferedEdfWriter
    from emgteach.mvc import mvc_ref_marker

    src = Path(source)
    dst = Path(dest)
    if dst.resolve() == src.resolve():
        raise ValueError("the tuned recording must not overwrite its source")

    señales, cabeceras, _ = highlevel.read_edf(str(src))
    if not len(señales):
        raise ValueError("the recording has no channels")
    fs = float(cabeceras[0].get("sample_frequency", 1000))
    n = len(señales[0])
    duracion = n / fs

    marcas = read_edf_markers(src)
    fases = parse_phase_markers(marcas)
    rec_start = fases.rec_start_s if fases.rec_start_s is not None else duracion
    rec_start = max(0.0, min(float(rec_start), duracion))

    tramos = _tramos_conservados(fragments, rec_start, duracion)
    conservado_s = sum(b - a for a, b in tramos)

    # Everything before the recording phase, then the kept fragments of it.
    def _recortar(sig) -> np.ndarray:
        arr = np.asarray(sig, dtype=np.float64)
        trozos = [arr[: round(rec_start * fs)]]
        for a, b in tramos:
            trozos.append(arr[round(a * fs) : round(b * fs)])
        return np.concatenate(trozos)

    recortadas = [_recortar(s) for s in señales]

    canales = [
        ChannelInfo(
            label=str(h.get("label", f"ch{i + 1}")),
            dimension=str(h.get("dimension", "mV")),
            physical_min=_cabe_en_edf(
                float(h.get("physical_min", -3.3)), hacia_arriba=False),
            physical_max=_cabe_en_edf(
                float(h.get("physical_max", 3.3)), hacia_arriba=True),
            digital_min=int(h.get("digital_min", 0)),
            digital_max=int(h.get("digital_max", 1023)),
            sample_frequency=round(fs),
        )
        for i, h in enumerate(cabeceras)
    ]

    original = read_edf_metadata(src)
    momento = when or datetime.now()
    total_reps = len(fases.cal_reps)
    guardadas = total_reps
    if keep:
        guardadas = sum(
            1 for r in fases.cal_reps
            if keep.get(r.channel_index) is None
            or r.rep in keep[r.channel_index]
        )
    resumen = TunedSummary(
        src, dst, reps_kept=guardadas, reps_total=total_reps,
        fragments=len(tramos), kept_s=conservado_s, full_s=duracion - rec_start,
    )

    # The name goes; the code stays. The header carries the student's name in
    # the original (io.RecordingMetadata), and this is the file that ends up
    # circulating between a laboratory bench and a marking pile.
    meta = RecordingMetadata(
        student_name=original.student_code or "",
        student_code=original.student_code,
        # The protocol is copied through untouched. Equipment, technician and
        # recording_additional share EDF_RECORDING_IDENT_BUDGET characters
        # *between them*, and on a real recording they are nearly spent — the
        # device string alone is twenty-eight of thirty-nine. Marking the
        # derivation there truncated the protocol instead of fitting beside
        # it: "agonist/antagonist" came back as "ag". The patient block has
        # its own, roomier budget and this file uses almost none of it, so
        # the mark goes there.
        protocol=original.protocol,
        patient_additional=f"{DERIVED_PREFIX} from {src.name}"[:80],
        technician=original.technician,
        equipment=original.equipment,
        start_datetime=original.start_datetime,
    )

    with BufferedEdfWriter(str(dst), channels=canales, metadata=meta) as w:
        bloque = round(fs)
        for i in range(0, len(recortadas[0]), bloque):
            w.add_samples(*[s[i : i + bloque] for s in recortadas])
        for linea in resumen.as_annotations(momento):
            w.add_annotation(0.0, linea)
        # The names, at the start of their own fragment in the derived file's
        # timeline — which is where the gaps have already been closed up.
        nombres = list(fragment_labels or [])
        cursor = rec_start
        for i, (a, b) in enumerate(tramos):
            nombre = nombres[i].strip() if i < len(nombres) else ""
            if nombre:
                w.add_annotation(cursor, _corta(nombre))
            cursor += b - a
        for t, texto in _reetiquetar(marcas, keep, tramos, rec_start):
            if not str(texto).startswith("MVC ref"):
                w.add_annotation(t, texto)
        # The cache, refreshed from the spans that are left, so a file that
        # carries both never carries two different answers.
        for canal, valor in (references or {}).items():
            if valor:
                w.add_annotation(0.0, mvc_ref_marker(int(canal), float(valor)))

    return resumen


def is_derived(markers: Sequence[tuple[float, Any]]) -> bool:
    """Whether these annotations came out of :func:`build_tuned_edf`."""
    return any(str(t).startswith(DERIVED_PREFIX) for _o, t in markers)
