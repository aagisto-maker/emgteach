"""The pieces the acquisition tab is made of.

`emgteach.gui.tabs.acquisition.AcquisitionTab` stays where it is — forty
test files import it from there — and grows smaller one responsibility at
a time, following docs/PLAN-partir-AcquisitionTab.md. Each piece here is a
widget or a QObject that keeps no reference to the tab: the tab calls its
methods and connects to its signals, and passes it what it needs to know.
"""

from __future__ import annotations

from emgteach.gui.acquisition.broadcast import ClassroomBox
from emgteach.gui.acquisition.connection import ConnectionBox
from emgteach.gui.acquisition.plots import LivePlots

__all__ = ["ClassroomBox", "ConnectionBox", "LivePlots"]
