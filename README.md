# emgteach

> Open-source teaching platform for surface electromyography (sEMG)
> acquisition and analysis, designed for undergraduate physiology
> laboratories.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python: 3.10–3.12](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](https://www.python.org/downloads/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20110845.svg)](https://doi.org/10.5281/zenodo.20110845)

`emgteach` is a Python package that provides a unified PySide6 desktop
application for real-time acquisition, offline analysis and maximum
voluntary contraction (MVC) normalisation of surface EMG signals. It
supports two interchangeable hardware backends: **BITalino (revolution)**
over Bluetooth and an **Arduino RedBoard Plus + MyoWare 2.0** over USB
serial. Output files follow the **EDF+** standard with reliable
buffered writing, free of the silent corruption pitfall described in
[Agis-Torres (2026), *Biomedical Signal Processing and Control*][bspc].

The package is intended for use in the practical teaching laboratory of
the Section of Physiology, Faculty of Pharmacy, Universidad
Complutense de Madrid, and is freely available for any group wishing
to introduce hands-on biopotential acquisition into their teaching.

## Status

`emgteach` v0.1.0 is the first public release. The package ships a
Qt-free analytic core (io, dsp, fatigue, mvc, devices), a Qt layer
(workers + three-tab PySide6 GUI), and a test suite of 73 tests
passing on Linux and Windows across Python 3.10-3.12. Submitted to
the [Journal of Open Source Software (JOSS)](https://joss.theoj.org/).

## Highlights

- **Three-tab GUI** (Acquisition, Analysis, MVC normalisation) wrapping a
  reusable acquisition library
- **Hardware-agnostic core** through the `AcquisitionDevice` interface;
  swap BITalino for Arduino+MyoWare with a single setting
- **EDF+ output with event annotations**, suitable for downstream
  analysis in MNE-Python, EDFbrowser and similar tools
- **Buffered-write pattern** for EDF that avoids the silent corruption
  artefact characterised in [Agis-Torres (2026)][bspc]
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

> ⚠️ **Windows users**: the `bitalino` package on Windows + Python 3.12
> depends on `PyBluez-bitalino`, which has no precompiled wheel and
> needs Microsoft C++ Build Tools to compile from source. If you do
> not have those tools and cannot install them, you can still use
> `emgteach` with the Arduino backend; the BITalino backend simply
> will not be available.

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

If you use this software, please cite both the article and the package:

- Agis-Torres, Á. (2026). *Silent corruption of EDF recordings during
  real-time biopotential streaming: a buffered-write solution.*
  Biomedical Signal Processing and Control, submitted.
- Agis-Torres, Á. (2026). *emgteach: an open-source teaching platform
  for surface electromyography.* Journal of Open Source Software, in
  preparation.

A `CITATION.cff` file is provided for automatic citation export.

## Related work

- [edf-buffered-write][repo-bspc] — minimal reproducibility package
  for the buffered-write pattern (BSPC paper, [DOI][bspc-doi])
- [BITalino](https://www.bitalino.com/) — commercial Bluetooth
  biopotential acquisition device
- [SparkFun MyoWare 2.0](https://www.sparkfun.com/products/21265) —
  open-hardware sEMG 