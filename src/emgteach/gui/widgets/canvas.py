"""A matplotlib canvas that leaves the mouse wheel to the scroll area.

The Qt backend swallows every wheel event so it can zoom the axes under
the cursor. In the two tabs whose panels live inside a vertical scroll
area that meant the wheel changed the scale of whatever panel it happened
to be over, and never moved the page — the one thing a wheel is expected
to do over a tall document. Scaling has its own buttons in the sidebar.
"""

from __future__ import annotations

import shiboken6
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtGui import QWheelEvent


class ScrollingCanvas(FigureCanvasQTAgg):
    """FigureCanvasQTAgg whose wheel events go to the enclosing scroll area."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Not handled here: ignoring it hands the event to the parent chain,
        # where the QScrollArea scrolls the page.
        event.ignore()

    def _draw_idle(self) -> None:
        # matplotlib schedules the redraw on a single-shot timer. A canvas
        # whose window was closed in the meantime has lost its C++ side, and
        # with a Python override on the class the stale call raises instead
        # of being swallowed; a redraw of a widget that no longer exists is
        # simply nothing to do.
        if not shiboken6.isValid(self):
            return
        super()._draw_idle()
