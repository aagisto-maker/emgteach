"""GUI test for the main window itself.

Marked ``gui`` (needs a QApplication). Constructing :class:`MainWindow`
exercises the whole start-up wiring — every tab, the shared logger and the
shared :class:`~emgteach.broadcast.BroadcastServer` — which the import-only
smoke tests cannot catch (e.g. passing the window positionally into
``BroadcastServer(http_port=...)`` crashed on launch but imported fine).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_main_window_constructs(qapp) -> None:
    from PySide6.QtCore import QSettings

    from emgteach.broadcast import DEFAULT_HTTP_PORT, DEFAULT_WS_PORT
    from emgteach.gui.app import MainWindow

    settings = QSettings("emgteach-test", "main-window")
    settings.clear()
    win = MainWindow(settings)
    try:
        # The shared broadcast server got the default ports, not a widget.
        assert win._broadcast._http_port == DEFAULT_HTTP_PORT
        assert win._broadcast._ws_port == DEFAULT_WS_PORT
        assert win._broadcast.parent() is win
        # All three tabs share the one broadcast instance.
        assert win._tab_adq._broadcast is win._broadcast
        assert win._tab_ana._broadcast is win._broadcast
    finally:
        settings.clear()
        qapp.processEvents()   # flush deferred canvas draws before teardown
        win.close()
