"""Tests for the classroom broadcast server (:mod:`emgteach.broadcast`).

Marked ``gui`` because the Qt-native servers need a QApplication / event loop
(offscreen, set in ``conftest.py``).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def test_dashboard_asset_and_lan_ip() -> None:
    from emgteach.broadcast import _load_dashboard_html, lan_ipv4

    html = _load_dashboard_html()
    assert b"emgteach" in html
    assert b"{{WS_PORT}}" in html          # placeholder substituted at serve time
    ip = lan_ipv4()
    assert isinstance(ip, str) and ip.count(".") == 3


def test_start_stop_and_config_cache(qapp) -> None:
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8110, ws_port=8111)
    assert srv.start()
    assert srv.is_running()
    url = srv.follower_url()
    assert url.startswith("http://") and f":8110/?k={srv._token}" in url
    assert srv.client_count() == 0
    # Broadcasting with no followers is a safe no-op, and config is remembered.
    srv.broadcast({"t": "config", "n": 1, "labels": ["EMG"], "recording": False})
    assert srv._last_config is not None
    srv.stop()
    assert not srv.is_running()


def test_session_code_rotates_between_starts(qapp) -> None:
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8116, ws_port=8117)
    assert srv.start()
    first = srv._token
    assert len(first) == 6
    srv.stop()
    assert srv.start()
    # A new session mints a new code, so links shared for the previous
    # practical no longer work.
    assert srv._token != first
    srv.stop()


def test_broadcast_reaches_a_follower(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebSockets import QWebSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8112, ws_port=8113)
    assert srv.start()

    received: list[str] = []
    ws = QWebSocket()
    ws.textMessageReceived.connect(received.append)

    def on_open() -> None:
        # config is auto-sent on connect (cached); push one live frame too.
        srv.broadcast({"t": "config", "n": 2, "labels": ["A", "B"], "recording": True})
        srv.broadcast({"t": "data", "env": [[0.1], [0.2]]})

    ws.connected.connect(on_open)
    ws.open(QUrl(f"ws://127.0.0.1:8113/?k={srv._token}"))

    # Espera a que lleguen los dos mensajes, con un techo de tres segundos, en
    # vez de esperar 600 ms fijos y mirar. Los 600 ms bastaban para una vuelta
    # por localhost en una máquina ociosa, y en el corredor de Linux, con la
    # suite entera por delante, no siempre bastan: la prueba fallaba por el
    # presupuesto, no por el servidor —`client_count()` daba 1, o sea que la
    # conexión estaba hecha y solo faltaba que llegara el texto—. Esperando
    # por la condición sigue tardando lo mismo cuando todo va rápido.
    # Y el techo, holgado: esperando por la condición, un techo solo cuesta
    # tiempo cuando lo que se espera no llega —es decir, cuando la prueba
    # tiene que fallar—, así que ponerlo corto no compra nada y compra
    # fallos. Con tres segundos volvió a caerse en dos corredores de Linux
    # a la vez, con `client_count()` en 1: la conexión hecha y el texto en
    # camino. Una pasada sana sigue tardando milisegundos.
    loop = QEventLoop()
    QTimer.singleShot(15000, loop.quit)

    def _ya_estan() -> None:
        if any('"t":"config"' in m for m in received) and any(
            '"t":"data"' in m for m in received
        ):
            loop.quit()

    ws.textMessageReceived.connect(lambda _m: _ya_estan())
    loop.exec()

    assert srv.client_count() == 1
    assert any('"t":"config"' in m for m in received)
    assert any('"t":"data"' in m for m in received)

    ws.close()
    srv.stop()


def test_follower_without_session_code_is_rejected(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebSockets import QWebSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8118, ws_port=8119)
    assert srv.start()

    ws = QWebSocket()
    ws.open(QUrl("ws://127.0.0.1:8119"))          # no ?k=... code
    ws_bad = QWebSocket()
    ws_bad.open(QUrl("ws://127.0.0.1:8119/?k=nope"))

    loop = QEventLoop()
    QTimer.singleShot(600, loop.quit)
    loop.exec()

    assert srv.client_count() == 0
    ws.close()
    ws_bad.close()
    srv.stop()


def test_registered_download_is_served(qapp) -> None:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtNetwork import QTcpSocket

    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8114, ws_port=8115)
    assert srv.start()
    srv.register_download("/dl/x.csv", b"a,b\n1,2\n", "text/csv", "datos.csv")

    def http_get(target: str) -> bytes:
        raw = bytearray()
        sock = QTcpSocket()
        sock.readyRead.connect(lambda: raw.extend(bytes(sock.readAll().data())))
        sock.connected.connect(
            lambda: sock.write(
                b"GET " + target.encode() + b" HTTP/1.1\r\nHost: x\r\n\r\n"
            )
        )
        sock.connectToHost("127.0.0.1", 8114)
        loop = QEventLoop()
        QTimer.singleShot(600, loop.quit)
        loop.exec()
        return bytes(raw)

    resp = http_get(f"/dl/x.csv?k={srv._token}")
    assert b"200 OK" in resp
    assert b'Content-Disposition: attachment; filename="datos.csv"' in resp
    assert b"a,b\n1,2\n" in resp

    # The dashboard is served (not a 404) for any unregistered path with a
    # valid code…
    resp = http_get(f"/whatever?k={srv._token}")
    assert b"200 OK" in resp and b"text/html" in resp

    # …while a missing or stale session code gets the 403 page instead of
    # the dashboard or the file.
    for target in ("/", "/dl/x.csv", "/dl/x.csv?k=stale1"):
        resp = http_get(target)
        assert b"403 Forbidden" in resp
        assert b"a,b" not in resp

    srv.stop()


def test_the_default_ports_are_8080_and_8443() -> None:
    from emgteach.broadcast import BroadcastServer

    assert BroadcastServer().ports() == (8080, 8443)


@pytest.mark.parametrize(("busy", "which"), [("page", 8120), ("data", 8121)])
def test_a_busy_port_is_named(qapp, busy: str, which: int) -> None:
    from PySide6.QtNetwork import QHostAddress, QTcpServer

    from emgteach.broadcast import BroadcastServer

    blocker = QTcpServer()
    assert blocker.listen(QHostAddress(QHostAddress.SpecialAddress.Any), which)
    srv = BroadcastServer(http_port=8120, ws_port=8121)
    try:
        assert not srv.start()
        assert srv.failed_port == which
        assert not srv.is_running()
    finally:
        blocker.close()
    assert srv.start()
    assert srv.failed_port is None
    srv.stop()


def _follow(srv, port: int, wait_ms: int = 600) -> list[str]:
    """Connect one follower, wait, and return what it received."""
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWebSockets import QWebSocket

    received: list[str] = []
    ws = QWebSocket()
    ws.textMessageReceived.connect(received.append)
    ws.open(QUrl(f"ws://127.0.0.1:{port}/?k={srv._token}"))
    loop = QEventLoop()
    QTimer.singleShot(wait_ms, loop.quit)
    loop.exec()
    ws.close()
    loop2 = QEventLoop()
    QTimer.singleShot(200, loop2.quit)
    loop2.exec()
    return received


def test_a_follower_who_joins_after_the_report_still_gets_it(qapp) -> None:
    """Ported from ecgteach 0.4.0 (bench of 5 Oct 2026, E11), and the same in
    the 3.7.2: the «download» frame went once, to whoever was connected at that
    instant, so a phone that opened the page later, or reconnected after its
    screen went off, never got the report."""
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8122, ws_port=8123)
    assert srv.start()
    try:
        srv.broadcast({"t": "config", "n": 1, "labels": ["Bíceps"], "recording": False})
        srv.register_download("/report.pdf", b"%PDF-1.4", "application/pdf", "emg_informe.pdf")
        srv.broadcast({"t": "download", "kind": "report", "url": "/report.pdf",
                       "name": "emg_informe.pdf"})
        late = _follow(srv, 8123)
        assert any('"t":"download"' in m and "report.pdf" in m for m in late), late
        # And the phone that reconnects (screen off, a Wi-Fi hiccup) gets it again.
        again = _follow(srv, 8123)
        assert any('"t":"download"' in m for m in again), again
    finally:
        srv.stop()


def test_a_new_broadcast_does_not_offer_the_old_report(qapp) -> None:
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8124, ws_port=8125)
    assert srv.start()
    srv.register_download("/report.pdf", b"%PDF-1.4", "application/pdf", "emg_informe.pdf")
    srv.broadcast({"t": "download", "kind": "report", "url": "/report.pdf",
                   "name": "emg_informe.pdf"})
    srv.stop()
    assert srv.start()
    try:
        late = _follow(srv, 8125)
        assert not any('"t":"download"' in m for m in late), late
    finally:
        srv.stop()


@pytest.mark.parametrize("new", [
    {"t": "config", "n": 1, "labels": ["Tríceps"], "recording": False},
    {"t": "status", "recording": True},
])
def test_the_report_of_an_earlier_recording_is_not_offered(qapp, new) -> None:
    """With the broadcast on from one recording to the next, a phone joining
    during the second must not get the first one's PDF. A new config, or the
    start of a new recording (a status frame, sent by the acquisition tab),
    forgets the offers."""
    from emgteach.broadcast import BroadcastServer

    srv = BroadcastServer(http_port=8126, ws_port=8127)
    assert srv.start()
    try:
        srv.broadcast({"t": "config", "n": 1, "labels": ["Bíceps"], "recording": False})
        srv.register_download("/report.pdf", b"%PDF-1.4", "application/pdf", "emg_informe.pdf")
        srv.broadcast({"t": "download", "kind": "report", "url": "/report.pdf",
                       "name": "emg_informe.pdf"})
        srv.broadcast(new)
        late = _follow(srv, 8127)
        assert not any('"t":"download"' in m for m in late), late
    finally:
        srv.stop()


def test_a_follower_who_joins_after_the_results_still_gets_them(qapp) -> None:
    """Decision of 11 Oct 2026 (A1): the metrics travel with the report. A
    phone that joined after them saw the download button over an empty
    results panel; it now gets the last «results» frame too, and a new
    config or a new recording forgets it, as it does the report."""
    from emgteach.broadcast import BroadcastServer

    results = {"t": "results", "file": "P07.edf", "mnf": 81.2, "mdf": 70.4,
               "mdf_slope": -0.31, "rms": 0.42, "iemg": 12.3, "duration": 30.0,
               "fatigue": -1}
    srv = BroadcastServer(http_port=8128, ws_port=8129)
    assert srv.start()
    try:
        srv.broadcast({"t": "config", "n": 1, "labels": ["Bíceps"], "recording": False})
        srv.broadcast(results)
        late = _follow(srv, 8129)
        assert any('"t":"results"' in m and "P07.edf" in m for m in late), late
        for new in ({"t": "config", "n": 1, "labels": ["Tríceps"], "recording": False},
                    {"t": "status", "recording": True}):
            srv.broadcast(results)
            srv.broadcast(new)
            late = _follow(srv, 8129)
            assert not any('"t":"results"' in m for m in late), (new, late)
        srv.broadcast(results)              # on offer when the broadcast stops
    finally:
        srv.stop()
    assert srv.start()
    try:
        late = _follow(srv, 8129)
        assert not any('"t":"results"' in m for m in late), late
    finally:
        srv.stop()
