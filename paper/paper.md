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

`emgteach` is a Python package for the undergraduate physiology teaching
laboratory. It packages a PySide6 desktop application that records,
analyses and normalises surface electromyography (sEMG) signals against
a maximum voluntary contraction (MVC) reference. Two hardware backends
are supported through one abstract interface: the BITalino *(revolution)*
Bluetooth device [@PlacidoDaSilva2014BITalino] and an Arduino RedBoard
Plus paired with a SparkFun MyoWare 2.0 sensor [@SparkFunMyoWare] over
USB serial. Recordings are written as EDF+ files [@Kemp2003EDFplus]
using the buffered-write pattern of @AgisTorres2026BSPC, which is
provably free of the silent file-corruption pitfall that affects the
EDF writers shipped with most Python biosignal stacks. The full DSP
pipeline (50 Hz mains notch, 20-450 Hz band-pass, 5 Hz envelope, Welch
PSD, mean and median frequency, polynomial fatigue fits, MVC
normalisation) is Qt-free and works equally well from notebooks or
command-line scripts.

# Statement of need

A modern undergraduate physiology curriculum increasingly expects
hands-on quantitative practical learning. For surface electromyography,
in particular, the cost of commercial teaching kits remains the main
deterrent to uptake by smaller departments [@DelToro2019].
Open-source hardware platforms such as BITalino
[@PlacidoDaSilva2014BITalino] and the SparkFun MyoWare 2.0 sensor
[@SparkFunMyoWare] have largely solved the hardware affordability
problem. The software side, however, is patchier. The PLUX manufacturer
of BITalino ships a polished free desktop suite, *OpenSignals
(revolution)* [@PluxOpenSignals2026], that handles acquisition,
real-time visualisation, event annotation and export to EDF and
several other formats. The catch is that EMG-specific analysis -
digital filtering, RMS, mean and median frequency, fatigue trends,
MVC normalisation - lives behind paid commercial add-ons (*EMG
Analysis*, *Muscle Load Analysis*) [@PluxOpenSignals2026]. OpenSignals
is also tied to PLUX devices, dropped its Linux support in July 2024
and has documented Bluetooth instability on macOS Ventura and later.
The MyoWare 2 ecosystem is a modular, solderless lineup of stackable
shields that lowers the electronic-prototyping barrier for instructors
without soldering experience, but on the host side it ships only with
an Arduino streaming sketch and no analysis software at all
[@SparkFunMyoWare].

There is therefore no turnkey, peer-reviewed Python package that
addresses the teaching-laboratory use case as a whole. A package that
did would need to bundle a graphical user interface accessible to
health sciences students with EDF+ output that downstream tools such
as MNE-Python [@Gramfort2013MNE] and EDFbrowser [@vanBeelenEDFlib]
can read directly. It would also need a complete and freely
modifiable EMG analysis pipeline, multi-vendor hardware support
through a single abstract interface, and a deterministic synthetic
data path that lets students run the full practical without touching
a real electrode.

`emgteach` fills that gap. The package is licensed under GPL-3.0 and
runs on a typical undergraduate-laboratory Windows 11 machine without
administrator privileges, using only the Microsoft Store distribution
of Python 3.12. The public API can be exercised from a notebook, so
a student who later wants to write their own analysis can reuse the
package without instantiating the GUI.

# State of the field

Several solutions cover parts of the surface-EMG workflow.
*OpenSignals (revolution)* [@PluxOpenSignals2026] is the most directly
comparable end-user application: free for BITalino and biosignalsplux
users, polished GUI, EDF export, but its EMG processing capability
sits behind paid add-ons and is closed source. NeuroKit2
[@Makowski2021NeuroKit2] offers a broad set of biosignal processing
routines, EMG included, but it is library-shaped: no real-time
acquisition, no GUI. The MyoWare reference design [@SparkFunMyoWare]
ships only an Arduino streaming sketch and no host-side analysis
software. ReSurfEMG [@Moore2023ReSurfEMG] targets respiratory surface
EMG with sophisticated offline analysis but, again, no acquisition
GUI nor a teaching focus. None of these tools combines free
EDF+-native output with a unified hardware-agnostic acquisition GUI
and a complete student-facing analysis pipeline.

`emgteach` adopts the architectural decision of *making the software
the product*: the same teaching application can talk to BITalino, to
an Arduino + MyoWare board, or to a fully synthetic signal generator,
through a single :class:`AcquisitionDevice` abstract interface. The
choice of acquisition hardware is therefore a deployment decision
rather than a re-engineering one. This was a direct response to the
saturation of the EMG-Arduino-versus-commercial benchmarking
literature [@DelToro2019; @Heywood2018; @MolinaMolina2020]: the
teaching-lab gap is no longer in hardware validation, but in usable
software.

# Software description

`emgteach` is a Qt-free analytic core surrounded by a thin PySide6
layer. The core consists of five modules: ``io`` (EDF+ reading and
buffered writing), ``dsp`` (filter design, online and offline
pipelines, Welch PSD, acquisition diagnostics), ``fatigue``
(polynomial fits of MDF over time and RMS over MDF), ``mvc``
(95th-percentile MVC reference, normalisation and adaptive plot
limits) and ``devices`` (the abstract :class:`AcquisitionDevice` and
its two concrete implementations). The Qt layer adds ``workers``
(background QThread orchestrators) and ``gui`` (three tabs:
Acquisition, Analysis, MVC). Every module ships with NumPy-style
docstrings. The test suite contains 73 tests that run end-to-end on
a headless runner.

## Buffered EDF+ writing

The central engineering contribution of `emgteach` is the
:class:`BufferedEdfWriter` class, which encapsulates the
buffer-then-flush pattern characterised in @AgisTorres2026BSPC. The
EDF/EDF+ specification mandates a fixed number of samples per data
record, and most Python EDF writers - including the widely used
`pyedflib` [@Nahrstaedt2025pyedflib] - silently pad short blocks up
to a complete record at write time. In a real-time acquisition loop
where the device delivers blocks much shorter than one second
(typically 100 ms), naive use of the writer produces files whose
duration is inflated by an order of magnitude, whose root-mean-square
amplitude is attenuated by a factor of approximately 3.2, and whose
power spectral density is severely distorted. The pitfall is
invisible to live monitoring and to short visual inspection. The
buffered pattern eliminates the artefact, and a dedicated round-trip
test on a synthetic 80 Hz EMG signal verifies the property at every
push.

## Watchdog for Bluetooth acquisition

A second engineering contribution is the watchdog mechanism for the
BITalino backend. The underlying Bluetooth read call can block
indefinitely when the link is silently dropped mid-session - the
single most common reason for an EMG laboratory session to be lost.
:class:`BitalinoDevice` releases its connection lock before each
blocking read; a separate :meth:`force_close` method, callable from
the GUI polling timer in a different thread, interrupts the stuck
read by closing the underlying socket. A unit test reproduces the
race condition and confirms that the read unblocks within tens of
milliseconds, well below the three-second threshold used by the GUI.

## Reproducible synthetic data path

The package also ships a deterministic synthetic EMG signal
generator, so that the full teaching practical can be reproduced
without any electrode contact. The generator uses a fixed random seed
and a pinned scientific stack (`numpy==1.26.4`, `scipy==1.13.1`,
`pyedflib==0.1.42`); under Python 3.12 on Windows 11, the resulting
EDF+ file is byte-stable and its SHA-256 can be verified against a
reference value. This makes the synthetic path useful both for
deployment-time smoke testing and for grading student submissions.

# Research and teaching impact

`emgteach` is in routine use in the practical teaching laboratory of
the Section of Physiology, Faculty of Pharmacy, Universidad
Complutense de Madrid. A pre/post study with the 2026/27 cohort is
planned and will be reported separately in *Advances in Physiology
Education*. The package is also the substrate on which the silent
EDF corruption phenomenon [@AgisTorres2026BSPC] was first identified,
and now serves as a reference implementation that other groups can
audit against.

# Acknowledgements

The author thanks the Department of Physiology and the Faculty of
Pharmacy of the Universidad Complutense de Madrid for institutional
support. This work was carried out during a research sabbatical
granted by the Universidad Complutense de Madrid to the author in
2025. This research did not receive any specific grant from funding
agencies in the public, commercial or not-for-profit sectors.

# Generative AI disclosure

The Python source code, documentation and this manuscript were
developed with the assistance of Claude (Anthropic, model Opus 4.7).
The author reviewed and edited the content, ran every test, and
takes full responsibility for the published artefact.

# References
