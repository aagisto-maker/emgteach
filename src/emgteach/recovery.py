"""Recover a recording the application did not get to close.

An EDF+ file is written record by record, but two things are only written
when the recording closes: the number of records in the header, which says
``-1`` until then, and the annotations, which pyedflib keeps in memory. A
process that dies in mid-recording — a power cut, a forced close, a fault
in a library — therefore leaves a file with all its signal on disk that no
reader accepts, and without a single one of the session's marks: the
calibration spans, the reference of each muscle, the start of the recording
phase.

The acquisition worker guards against the second loss by also appending
each mark, as it is made, to a side-car text file next to the EDF
(:func:`sidecar_path`), flushed to disk mark by mark and removed when the
recording closes normally. This module repairs the first: it counts the
records from the file's size, reads the signal back, and writes a new file
with the marks the side-car holds.

Command line::

    python -m emgteach.recovery C:\\Records\\P07_2026-09-10_16-32.edf

writes ``P07_2026-09-10_16-32_recuperado.edf`` beside it. The original is
never modified.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from emgteach.i18n import tr
from emgteach.io import BufferedEdfWriter, ChannelInfo, RecordingMetadata

#: Suffix of the side-car file that mirrors the marks of a recording in
#: progress: ``P07_2026-09-10_16-32.marcas.txt`` next to the EDF.
SIDECAR_SUFFIX = ".marcas.txt"
#: Suffix of the file this module writes.
RECOVERED_SUFFIX = "_recuperado"

_HEADER_RECORDS = slice(236, 244)     # number of data records, ASCII
_HEADER_BYTES = slice(184, 192)       # bytes in the header record
_HEADER_NS = slice(252, 256)          # number of signals


def sidecar_path(edf_path: str | Path) -> Path:
    """The side-car that mirrors *edf_path*'s marks while it is recorded."""
    p = Path(edf_path)
    return p.with_name(p.stem + SIDECAR_SUFFIX)


def read_sidecar(path: str | Path) -> list[tuple[float, str]]:
    """The ``(time_s, label)`` marks a side-car holds, in file order.

    Lines that start with ``#`` are comments; a line that does not parse is
    skipped rather than failing the recovery of the rest.
    """
    marks: list[tuple[float, str]] = []
    p = Path(path)
    if not p.exists():
        return marks
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        t, sep, label = line.partition("\t")
        if not sep:
            continue
        try:
            marks.append((float(t), label.strip()))
        except ValueError:
            continue
    return marks


def count_records(edf_path: str | Path) -> tuple[int, int]:
    """``(records_in_header, records_on_disk)`` of an EDF file.

    The header's count is ``-1`` in a file that was never closed; the count
    on disk comes from the file's size, the header's length and the bytes
    each record occupies (two per sample, summed over the signals).
    """
    p = Path(edf_path)
    size = p.stat().st_size
    with p.open("rb") as f:
        head = f.read(256)
        if len(head) < 256:
            raise ValueError(tr("{path} is too short to be an EDF file.").format(path=p))
        header_bytes = int(head[_HEADER_BYTES].decode("ascii", "replace").strip() or 0)
        in_header = int(head[_HEADER_RECORDS].decode("ascii", "replace").strip() or -1)
        ns = int(head[_HEADER_NS].decode("ascii", "replace").strip() or 0)
        f.seek(256 + ns * 216)
        samples = f.read(ns * 8).decode("ascii", "replace")
    per_record = sum(int(samples[i:i + 8].strip() or 0) for i in range(0, ns * 8, 8))
    record_bytes = 2 * per_record
    if header_bytes <= 0 or record_bytes <= 0:
        raise ValueError(tr("{path} does not have a readable EDF header.").format(path=p))
    return in_header, max(0, (size - header_bytes) // record_bytes)


def _with_record_count(edf_path: Path, records: int, out: Path) -> None:
    """Copy *edf_path* to *out* with *records* written into its header."""
    shutil.copyfile(edf_path, out)
    with out.open("r+b") as f:
        f.seek(_HEADER_RECORDS.start)
        f.write(f"{records:<8d}".encode("ascii"))


def recover_recording(edf_path: str | Path, out_path: str | Path | None = None,
                      sidecar: str | Path | None = None,
                      say=print) -> Path:
    """Write a readable copy of *edf_path* with the marks of its side-car.

    Parameters
    ----------
    edf_path
        The recording that was not closed. It is read, never written.
    out_path
        Where to write the recovered file; by default next to the original,
        with :data:`RECOVERED_SUFFIX` before the extension.
    sidecar
        The side-car with the marks; by default :func:`sidecar_path` of the
        original. Missing, the recovered file carries only the annotations
        the original already held (a file closed normally has them all).
    say
        Where to report each step.

    Returns
    -------
    Path
        The recovered file.
    """
    import pyedflib

    src = Path(edf_path)
    out = Path(out_path) if out_path else src.with_name(src.stem + RECOVERED_SUFFIX + src.suffix)
    side = Path(sidecar) if sidecar else sidecar_path(src)

    in_header, on_disk = count_records(src)
    say(tr("{path}: {n} records in the header, {m} on disk.").format(
        path=src.name, n=in_header, m=on_disk))
    if on_disk == 0:
        raise ValueError(tr("{path} holds no complete record; there is nothing to recover.")
                         .format(path=src.name))

    # A readable twin: the same bytes with the record count filled in. Kept
    # in a temporary name and removed afterwards.
    twin = out.with_name(out.stem + ".tmp" + out.suffix)
    _with_record_count(src, on_disk, twin)
    try:
        reader = pyedflib.EdfReader(str(twin))
        try:
            n = reader.signals_in_file
            labels = reader.getSignalLabels()
            channels = []
            signals = []
            for i in range(n):
                channels.append(ChannelInfo(
                    str(labels[i]),
                    dimension=str(reader.getPhysicalDimension(i)),
                    physical_min=float(reader.getPhysicalMinimum(i)),
                    physical_max=float(reader.getPhysicalMaximum(i)),
                    digital_min=int(reader.getDigitalMinimum(i)),
                    digital_max=int(reader.getDigitalMaximum(i)),
                    sample_frequency=round(reader.getSampleFrequency(i)),
                ))
                signals.append(np.asarray(reader.readSignal(i), dtype=np.float64))
            onsets, _durations, texts = reader.readAnnotations()
            held = [(float(o), str(t)) for o, t in zip(onsets, texts, strict=False)]
            try:
                start: datetime | None = reader.getStartdatetime()
            except Exception:
                start = None
            metadata = RecordingMetadata(
                student_name=str(reader.getPatientName() or ""),
                student_code=str(reader.getPatientCode() or ""),
                protocol=str(reader.getRecordingAdditional() or ""),
                technician=str(reader.getTechnician() or ""),
                equipment=str(reader.getEquipment() or ""),
                # Not translated: the header outlives the session's language,
                # as the tuned file's «DERIVED from» does.
                patient_additional=f"RECOVERED from {src.name}",
                start_datetime=start,
            )
        finally:
            reader.close()
    finally:
        try:
            twin.unlink()
        except OSError:
            pass

    marks = read_sidecar(side)
    say(tr("{n} marks already in the file, {m} in the side-car {side}.").format(
        n=len(held), m=len(marks), side=side.name if side.exists() else "—"))
    seen = {(round(t, 4), label) for t, label in held}
    merged = list(held)
    for t, label in marks:
        if (round(t, 4), label) not in seen:
            merged.append((t, label))
            seen.add((round(t, 4), label))
    merged.sort(key=lambda m: m[0])

    with BufferedEdfWriter(str(out), channels=channels, metadata=metadata) as writer:
        writer.add_samples(*signals)
        for t, label in merged:
            writer.add_annotation(t, label)
    say(tr("Recovered: {path} — {seconds:.0f} s, {n} marks.").format(
        path=out, seconds=on_disk, n=len(merged)))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=tr("Recover an emgteach recording that was not closed."))
    parser.add_argument("edf", help=tr("the .edf file the application did not get to close"))
    parser.add_argument("--out", default=None, help=tr("where to write the recovered file"))
    parser.add_argument("--marks", default=None,
                        help=tr("the .marcas.txt side-car (by default, the one next to the .edf)"))
    args = parser.parse_args(argv)
    try:
        recover_recording(args.edf, args.out, args.marks)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
