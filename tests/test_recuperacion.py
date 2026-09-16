"""A recording the application did not get to close is not lost.

The marks are mirrored to a side-car text file as they are made, and
`emgteach.recovery` rebuilds a readable file from the records on disk plus
the side-car. Simulating the death of the process: the EDF's bytes are
copied while the writer is still open — the header says -1 records, as it
would after a power cut — and only then is the writer closed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pyedflib
import pytest

from emgteach.recovery import (
    count_records,
    main,
    read_sidecar,
    recover_recording,
    sidecar_path,
)

_WRITER_THAT_DIES = """
import os, sys
import numpy as np
from emgteach.io import BufferedEdfWriter, ChannelInfo, RecordingMetadata
path, seconds = sys.argv[1], int(sys.argv[2])
x = np.random.default_rng(7).normal(0.0, 0.1, seconds * 1000)
writer = BufferedEdfWriter(
    path, channels=[ChannelInfo("FCR", sample_frequency=1000)],
    metadata=RecordingMetadata(student_code="P07", protocol="pair", equipment="BITalino 44:E4"),
)
for i in range(0, x.size, 100):
    writer.add_samples(x[i:i + 100])
os._exit(1)                                   # no close(): the process dies
"""


def _unclosed_recording(tmp_path: Path, seconds: int = 3) -> tuple[Path, np.ndarray]:
    """An EDF as a dead process leaves it, plus the signal it was given.

    Written by a process that ends with ``os._exit`` before closing the
    writer, as after a power cut: the records are on disk and the header
    says -1 of them. (The file cannot be copied while pyedflib holds it
    open, so the death has to be real.)
    """
    dead = tmp_path / "P07_dead.edf"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        p for p in (str(Path(__file__).resolve().parents[1] / "src"),
                    os.environ.get("PYTHONPATH", "")) if p)}
    subprocess.run([sys.executable, "-c", _WRITER_THAT_DIES, str(dead), str(seconds)],
                   env=env, check=False, timeout=120)
    x = np.random.default_rng(7).normal(0.0, 0.1, seconds * 1000)
    return dead, x


def test_a_file_that_was_not_closed_says_minus_one_and_is_refused(tmp_path: Path) -> None:
    dead, _x = _unclosed_recording(tmp_path)
    in_header, on_disk = count_records(dead)
    assert in_header == -1 and on_disk == 3
    with pytest.raises(Exception, match=r"[Dd]atarecord"):
        pyedflib.EdfReader(str(dead))


def test_the_recovered_file_reads_back_with_the_side_car_marks(tmp_path: Path) -> None:
    dead, x = _unclosed_recording(tmp_path)
    side = sidecar_path(dead)
    side.write_text("# marks\n0.1000\tWARMUP start\n1.5000\tCAL start ch=1 rep=1\n"
                    "not a line\n2.2500\tMVC ref ch=1 value=0.42 mV\n", encoding="utf-8")
    said: list[str] = []
    out = recover_recording(dead, say=said.append)
    assert out.name == "P07_dead_recuperado.edf"
    with pyedflib.EdfReader(str(out)) as f:
        assert f.getFileDuration() == 3
        assert f.getPatientCode() == "P07" and f.getEquipment().startswith("BITalino")
        assert "RECOVERED" in f.getPatientAdditional()
        y = f.readSignal(0)
        onsets, _d, texts = f.readAnnotations()
    assert np.allclose(y, x, atol=6.6 / 1023)     # one ADC step of the ±3.3 V range
    assert [str(t) for t in texts] == ["WARMUP start", "CAL start ch=1 rep=1",
                                       "MVC ref ch=1 value=0.42 mV"]
    assert onsets[1] == pytest.approx(1.5, abs=1e-3)
    assert dead.read_bytes()[236:244].strip() == b"-1", "the original is untouched"
    assert any("3" in s for s in said)


def test_main_recovers_from_the_command_line(tmp_path: Path, capsys) -> None:
    dead, _x = _unclosed_recording(tmp_path, seconds=2)
    assert main([str(dead), "--out", str(tmp_path / "back.edf")]) == 0
    assert (tmp_path / "back.edf").exists()
    assert main([str(tmp_path / "nothing.edf")]) == 1


def test_the_side_car_parser_keeps_order_and_skips_noise(tmp_path: Path) -> None:
    p = tmp_path / "x.marcas.txt"
    p.write_text("# c\n\n3.5\tb\n1.0\ta\nbad\n2 no tab here", encoding="utf-8")
    assert read_sidecar(p) == [(3.5, "b"), (1.0, "a")]
    assert read_sidecar(tmp_path / "missing.txt") == []


@pytest.mark.gui
def test_the_worker_mirrors_each_mark_as_it_is_made_and_tidies_up(qapp, tmp_path: Path) -> None:
    from emgteach.devices import BitalinoDevice
    from emgteach.workers.acquisition import AcquisitionWorker

    path = tmp_path / "sim.edf"
    worker = AcquisitionWorker(BitalinoDevice("simulada", fs=1000, channels=[0]),
                               save_path=str(path), sensor_labels=["FCR"])
    worker.start()
    end = time.monotonic() + 8
    while time.monotonic() < end and not worker.is_streaming():
        qapp.processEvents()
        time.sleep(0.02)
    assert worker.is_streaming()
    worker.add_marker("CAL start ch=1 rep=1")
    time.sleep(0.15)
    side = sidecar_path(path)
    marks = read_sidecar(side)                  # readable while recording, without close()
    assert side.exists() and marks and marks[-1][1] == "CAL start ch=1 rep=1"
    assert marks[-1][0] > 0
    worker.stop()
    assert worker.wait(5000)
    assert path.exists() and not side.exists(), "closed normally, the side-car is redundant"
