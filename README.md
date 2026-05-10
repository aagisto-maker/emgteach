# emgteach

> Open-source teaching platform for surface electromyography (sEMG)
> acquisition and analysis, designed for undergraduate physiology
> laboratories.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python: 3.10–3.12](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](https://www.python.org/downloads/)

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

🚧 **Pre-release**. This repository currently contains the package
skeleton only (build configuration, license, citation file, CI). The
full source code is being progressively migrated from a working but
unstructured local prototype. The first feature-complete release will
coincide with submission to the [Journal of Open Source Software
(JOSS)](https://joss.theoj.org/).

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

Or programmatically:

```python
from emgteach.acquisition import ArduinoSerialDevice
from emgteach.io import write_edf_buffered

device = ArduinoSerialDevice(port="COM4", fs=1000)
device.open()
samples = device.read(seconds=10)
device.close()

write_edf_buffered("session.edf", samples, fs=1000)
```

## Documentation

The user guide and API reference will be built with MkDocs Material and
hosted on https://aagisto-maker.github.io/emgteach. Until then, the
docstrings of `src/emgteach/` are the authoritative reference.

## Citation

If you use this software, please cite both the article and the package:

- Agis-Torres, Á. (2026). *Silent corruption of EDF recordings during
  real-time biopotential streaming: a buffered-write solution.*
  Biomedical Signal Processing and Control, in press.
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
  open-hardware sEMG sensor
- [pyEDFlib](https://pyedflib.readthedocs.io/) — Python EDF library

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).

## Acknowledgements

Developed in the Departmental Section of Physiology, Faculty of
Pharmacy, Universidad Complutense de Madrid. Thanks to the colleagues
of the section for ongoing feedback during teaching trials.

## Generative AI disclosure

The Python source code and documentation in this repository were
developed with the assistance of Claude (Anthropic, model Opus 4.7),
and were reviewed and tested by the author.

[bspc]: https://doi.org/10.5281/zenodo.20042878
[bspc-doi]: https://doi.org/10.5281/zenodo.20042878
[repo-bspc]: https://github.com/aagisto-maker/edf-buffered-write
