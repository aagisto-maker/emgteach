# emgteach

> Open-source teaching platform for surface electromyography (sEMG)
> acquisition and analysis, designed for undergraduate physiology
> laboratories.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python: 3.10–3.12](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](https://www.python.org/downloads/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20723265.svg)](https://doi.org/10.5281/zenodo.20723265)

`emgteach` is a Python package that provides a unified PySide6 desktop
application for real-time acquisition, offline analysis and maximum
voluntary contraction (MVC) normalisation of surface EMG signals. It
supports two interchangeable hardware backends: **BITalino (revolution)**
over Bluetooth and an **Arduino RedBoard Plus + MyoWare 2.0** over USB
serial. Output files follow the **EDF+** standard with reliable
buffered writing, free of the silent corruption pitfall described in
[Agis-Torres (2026)](https://doi.org/10.5281/zenodo.20042878).

The package is intended for use in the practical teaching laboratory of
the Section of Physiology, Faculty of Pharmacy, Universidad
Complutense de Madrid, and is freely available for any group wishing
to introduce hands-on biopotential acquisition into their teaching.

## Status

`emgteach` v0.3.0 builds on the two-channel release with a **stacked
two-channel live view**, a compact themed GUI and a **bilingual
(English / Spanish) interface**. Earlier, v0.2.0 added **two-channel
acquisition** (e.g. agonist/antagonist), **automatic contraction-onset
annotation** and **one-click PDF session reports**. The package ships a
Qt-free analytic core (io, dsp, fatigue, mvc, devices, profiles,
reports, i18n), a Qt layer (workers + three-tab PySide6 GUI), and a test
suite of 126 tests passing on Linux and Windows across Python
3.10-3.12. See [`CHANGELOG.md`](CHANGELOG.md) for the full history.

## Highlights

- **Three-tab GUI** (Acquisition, Analysis, MVC normalisation) wrapping a
  reusable acquisition library
- **Bilingual interface (English / Spanish)** with automatic start-up
  language detection and an in-app language switch
- **Hardware-agnostic core** through the `AcquisitionDevice` interface;
  swap BITalino for Arduino+MyoWare with a single setting
- **Two-channel acquisition** for agonist/antagonist studies, with an
  editable label per channel; the data layer is generic over N channels
- **Stacked two-channel live view** that gives each channel its own
  vertical lane (raw and filtered) for clearer agonist/antagonist reading
- **Automatic onset detection** (baseline + k·SD threshold) that flags
  contraction onsets in real time and stores them as EDF+ annotations
- **One-click PDF session reports**: signal plot with annotations,
  metrics table, configuration used and a reproducible footer
- **EDF+ output with event annotations**, suitable for downstream
  analysis in MNE-Python, EDFbrowser and similar tools
- **Buffered-write pattern** for EDF that avoids the silent corruption
  artefact characterised in [Agis-Torres (2026)](https://doi.org/10.5281/zenodo.20042878)
- **Robust connectivity**: BITalino watchdog releases blocked
  Bluetooth reads in ~50 ms after disconnection
- **Reproducible synthetic signals** for class assignments and CI
  testing without hardware
- **Open-source firmware** for the Arduino+MyoWare side, included in
  the repository

## Install

Requires **Python 3.10, 3.11 or 3.12** on Windows, macOS or Linux.
Python 3.13+ is not currently supported because the pinned scientific
stack does not yet ship pre-built wheels for it.

```bash
pip install emgteach
```

Until the first PyPI release, install from source:

```bash
git clone https://github.com/aagisto-maker/emgteach.git
cd emgteach
pip install -e ".[dev]"
```

On **Windows 11** the easiest way to install Python 3.12 is via
**Microsoft Store** (search "Python 3.12"). It installs without
administrator privileges and configures the PATH automatically.

### Hardware backends

`emgteach` ships out of the box with the **Arduino + MyoWare** backend
over USB serial. To use the **BITalino** backend over Bluetooth you
need to install the optional extra:

```bash
pip install "emgteach[bitalino]"
```

> ⚠️ **BITalino needs Python ≤ 3.11.** The `bitalino` package depends on
> `PyBluez-bitalino`, whose C extension does **not** work on Python 3.12
> (it raises at connection time). Use **Python 3.11** for the BITalino
> backend. On Windows it also has no precompiled wheel, so it needs
> Microsoft C++ Build Tools to build from source. The Arduino + MyoWare
> backend uses `pyserial` (pure Python) and is unaffected — it works on
> every supported version.

## Quickstart

```bash
emgteach          # launch the GUI
```

Or programmatically (without the GUI):

```python
import numpy as np
from emgteach import ArduinoDevice, BufferedEdfWriter, ChannelInfo

device = ArduinoDevice(port="COM4", fs=1000)
device.open()
try:
    blocks = [device.read(100) for _ in range(100)]   # 100 x 100 ms = 10 s
finally:
    device.close()

samples = np.concatenate(blocks)
ch = ChannelInfo("EMG", sample_frequency=1000)
with BufferedEdfWriter("session.edf", channels=[ch]) as writer:
    writer.add_samples(samples)
```

## Documentation

The user guide and API reference will be built with MkDocs Material and
hosted on https://aagisto-maker.github.io/emgteach. Until then, the
docstrings of `src/emgteach/` are the authoritative reference.

## Citation

If you use this software, please cite the package (a `CITATION.cff` file
is provided for automatic citation export) and, where relevant, the
methodological article on the buffered-write pattern it implements:

- Agis-Torres, Á., Fernandes, V. S., Navarro-Dorado, J., & Muñoz-Picos, M.
  (2026). *emgteach: an open-source teaching platform for surface
  electromyography* (software). Zenodo.
  https://doi.org/10.5281/zenodo.20723265
- Agis-Torres, Á. (2026). *Silent corruption of EDF recordings during
  real-time biopotential streaming: a buffered-write solution.*
  Manuscript; reproducibility package:
  https://doi.org/10.5281/zenodo.20042878

A dedicated software paper is in preparation. Author contributions are
recorded in [`AUTHORS.md`](AUTHORS.md) using the
[CRediT](https://credit.niso.org/) taxonomy.

## Contributing

Contributions are welcome — bug reports, documentation, tests, hardware
backends and features. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
development setup, the test/lint commands, the branch and commit
conventions, and how to add or translate user-facing strings (the UI is
bilingual: English-canonical source plus a Spanish translation map).

## Development

Parts of this software were developed with the assistance of an AI
coding assistant (Anthropic's Claude) under the direction and review of
the author, who set all requirements, took the design decisions and is
responsible for the released code. The AI assistant is a tool and is not
an author; see [`AUTHORS.md`](AUTHORS.md).

## Related work

- [edf-buffered-write](https://doi.org/10.5281/zenodo.20042878) —
  minimal reproducibility package for the buffered-write pattern
- [BITalino](https://www.bitalino.com/) — commercial Bluetooth
  biopotential acquisition device
- [SparkFun MyoWare 2.0](https://www.sparkfun.com/products/21265) —
  open-hardware sEMG 