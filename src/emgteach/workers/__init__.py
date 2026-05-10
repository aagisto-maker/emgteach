"""QThread workers that orchestrate device, DSP and EDF I/O.

The workers are the bridge between the GUI tabs (which run on the Qt
main thread) and the rest of the package (which is hardware-agnostic
and Qt-free). They are kept as thin as possible: most of the
substantive logic lives in :mod:`emgteach.io`, :mod:`emgteach.dsp`,
:mod:`emgteach.fatigue` and :mod:`emgteach.mvc`.
"""

from __future__ import annotations

from emgteach.workers.acquisition import AcquisitionWorker
from emgteach.workers.analysis import AnalysisWorker
from emgteach.workers.mvc import MvcWorker

__all__ = [
    "AcquisitionWorker",
    "AnalysisWorker",
    "MvcWorker",
]
