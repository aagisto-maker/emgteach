---
title: 'emgteach: an open-source teaching platform for surface electromyography acquisition and analysis with Arduino-based hardware'
tags:
  - Python
  - electromyography
  - EMG
  - EDF+
  - biopotential acquisition
  - Arduino
  - BITalino
  - MyoWare
  - physiology teaching
authors:
  - name: Ángel Agis-Torres
    orcid: 0000-0002-3548-7264
    corresponding: true
    affiliation: 1
affiliations:
  - name: Departmental Section of Physiology, Faculty of Pharmacy, Universidad Complutense de Madrid, Spain
    index: 1
    ror: 02p0gd045
date: 10 May 2026
bibliography: paper.bib
---

# Summary

`emgteach` is a Python package that provides a unified PySide6 desktop
application for the real-time acquisition, offline analysis and
maximum-voluntary-contraction (MVC) normalisation of surface
electromyography (sEMG) signals, intentionally designed for the
undergraduate physiology teaching laboratory. The package supports
two interchangeable hardware backends — the BITalino *(revolution)*
commercial Bluetooth device [@PlacidoDaSilva2014BITalino] and an
Arduino RedBoard Plus board paired with the SparkFun MyoWare 2.0
sensor [@SparkFunMyoWare] over USB serial — and writes EDF+ files
[@Kemp2003EDFplus] using the buffered-write pattern proposed in
@AgisTorres2026BSPC, which is provably free of the silent
file-corruption pitfall that affects naive uses of the EDF writers
shipped with most Python biosignal stacks. The complete signal
processing pipeline (50 Hz mains notch, 20–450 Hz band-pass,
rectification, 5 Hz envelope, Welch power spectral density, mean and
median frequency, polynomial fatigue fits, MVC normalisation) is
implemented in a Qt-free core that can be reused from notebooks and
command-line scripts.

# Statement of need

A modern undergraduate physiology curriculum increasingly expects
hands-on quantitative practicals. For surface electromyography in
particular, the cost of commercial teaching kits remains the main
deterrent to uptake by smaller departments [@DelToro2019].
Open-source hardware platforms such as BITalino [@PlacidoDaSilva2014BITalino]
and the SparkFun MyoWare 2.0 sensor [@SparkFunMyoWare] have largely
solved the hardware affordability problem. On the software side, the
PLUX manufacturer of BITalino ships a polished free desktop suite,
*OpenSignals (revolution)* [@PluxOpenSignals2026], that handles
acquisition, real-time visualisation, event annotation and export to
EDF and several other formats; however, the EMG-specific analysis
features that the teaching laboratory actually relies on (digital
filtering, RMS, mean and median frequency estimation, fatigue trends,
MVC normalisation) are gated behind paid commercial add-ons such as
*EMG Analysis* and *Muscle Load Analysis* [@PluxOpenSignals2026].
OpenSignals is also tied to PLUX devices, dropped its Linux support
in July 2024, and has documented Bluetooth instability on macOS
Ventura and later. The MyoWare 2 ecosystem is a
modular, solderless lineup of stackable shields (sensor, power, LED,
link, cable, Arduino) that lowers the electronic-prototyping barrier
for instructors without soldering experience, but on the host side it
ships only with an Arduino streaming sketch and no analysis software
at all [@SparkFunMyoWare].
There is therefore no turnkey, peer-reviewed Python package that
combines: a graphical user interface suitable for first-year medical
or pharmacy students; EDF+ output that is interoperable with
downstream neurophysiology tools such as MNE-Python [@Gramfort2013MNE]
and EDFbrowser [@vanBeelenEDFlib]; a complete and freely modifiable
EMG analysis pipeline; multi-vendor hardware support through a single
abstract interface; and a reproducible synthetic data path that lets
students run the full practical without touching a real electrode.

`emgteach` fills that gap. The package is licensed under GPL-3.0 and
is engineered for installation on a typical undergraduate-laboratory
Windows 11 machine without administrator privileges, using only the
Microsoft Store distribution of Python 3.12. It exposes a public API
that is independently testable from notebooks, so that students who
later want to write their own analyses can reuse the components of
the package without instantiating the GUI.

# State of the field

Several solutions cover parts of the surface-EMG workflow.
*OpenSignals (revolution)* [@PluxOpenSignals2026] is, as discussed
above, the most directly comparable end-user application: it ships
free for BITalino and biosignalsplux users with a friendly GUI and
EDF export, but its EMG processing capability lives behind paid
add-ons and is closed source. NeuroKit2 [@Makowski2021NeuroKit2]
offers a broad set of biosignal processing routines, including EMG,
but is library-shaped and includes neither real-time acquisition nor
a GUI. The MyoWare reference design [@SparkFunMyoWare] ships only an
Arduino streaming sketch and no host-side analysis software.
ReSurfEMG [@Moore2023ReSurfEMG] targets respiratory surface EMG
with sophisticated offline analysis but, again, no acquisition GUI
nor a teaching focus. None of these solutions combines free
EDF+-native output with a unified hardware-agnostic acquisition GUI
and a complete student-facing analysis pipeline.

`emgteach` adopts the architectural decision of *making the software
the product*: the same teaching application can talk to BITalino, to
an Arduino + MyoWare board, or to a fully synthetic signal generator,
through a single :class:`AcquisitionDevice` abstract interface. This
hardware-agnostic design makes the choice of acquisition device a
deployment decision rather than a re-engineering one, and was a
direct response to the saturation of the EMG-Arduino-versus-commercial
benchmarking literature [@DelToro2019; @Heywood2018; @MolinaMolina2020].

# Software description

`emgteach` is structured as a Qt-free analytic core surrounded by a
thin PySide6 layer. The core consists of five modules: ``io``
(EDF+ reading and buffered writing), ``dsp`` (filter design, online
and offline pipelines, Welch PSD, acquisition diagnostics),
``fatigue`` (polynomial fits of MDF over time and RMS over MDF),
``mvc`` (95th-percentile MVC reference, normalisation and adaptive
plot limits) and ``devices`` (the abstract :class:`AcquisitionDevice`
and its two concrete implementations). The thin Qt layer is split
into ``workers`` (background QThread orchestrators) and ``gui`` (three
tabs: Acquisition, Analysis, MVC). Each module ships with NumPy-style
docstrings and is covered by the package's test suite, which contains
73 tests that run end-to-end without a display server.

## Buffered EDF+ writing

The central engineering contribution of `emgteach` is its
:class:`BufferedEdfWriter` class, which encapsulates the buffer-then-flush
pattern characterised in @AgisTorres2026BSPC. The pattern is
necessary because the EDF/EDF+ specification mandates a fixed number
of samples per data record, and most Python EDF writers, including
the widely used `pyedflib` [@Nahrstaedt2025pyedflib], silently pad
short blocks up to a complete record at write time. In a real-time
acquisition loop where the device delivers blocks much shorter than
one second (typically 100 ms), naive use of the writer therefore
produces files whose duration is inflated by an order of magnitude,
whose root-mean-square amplitude is attenuated by a factor of
approximately 3.2, and whose power spectral density is heavily
distorted. The pitfall is invisible to live monitoring and to short
visual inspection. By adopting the buffered pattern, `emgteach`
guarantees that every recording is faithfully reproduced when read
back; the property is verified at every push by a dedicated
round-trip test on a synthetic 80 Hz EMG signal.

## Watchdog for Bluetooth acquisition

A second engineering contribution is the watchdog mechanism for the
BITalino backend. The underlying Bluetooth read call can block
indefinitely when the link is silently dropped mid-session; this is
the most common reason for an EMG laboratory session to be lost. The
:class:`BitalinoDevice` releases its connection lock before each
blocking read, and a separate :meth:`force_close` method that any
thread can call from the GUI's polling timer interrupts the stuck
read by closing the underlying socket. A unit test reproduces the
race condition and verifies that the read unblocks within tens of
milliseconds, well below the 3-second threshold used by the GUI.

## Reproducible synthetic data path

The package ships with a deterministic synthetic EMG signal generator
that allows the entire teaching practical to be reproduced without
any electrode contact. The synthetic generator uses a fixed random
seed and pinned scientific stack (`numpy==1.26.4`, `scipy==1.13.1`,
`pyedflib==0.1.42`) so that, given Python 3.12 on Windows 11, the
output file is byte-stable and its SHA-256 can be verified against a
reference value. This