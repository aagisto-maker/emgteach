"""The classroom broadcast as a piece of its own (step 1 of
docs/PLAN-partir-AcquisitionTab.md): `ClassroomBox` is built with a server
and nothing else, drives it from its controls, and tells the tab what it
has to say through signals. The tab's side — what the followers are told
of the recording, and the load they show — stays in the tab and is covered
by tests/test_manejo_en_aula.py.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal

from emgteach.gui.acquisition import broadcast as mod
from emgteach.gui.acquisition.broadcast import (
    ESPERA_SEGUIDORES_MS,
    ClassroomBox,
    aviso_puerto_ocupado,
    aviso_sin_red,
    aviso_sin_seguidores,
)

pytestmark = pytest.mark.gui


class _Servidor(QObject):
    """A BroadcastServer that opens no port: it remembers what it is told."""

    clients_changed = Signal(int)

    def __init__(self, *, arranca: bool = True, puerto_fallido: int | None = None) -> None:
        super().__init__()
        self.arranca = arranca
        self.failed_port = puerto_fallido
        self.payloads: list[dict] = []
        self._running = False
        self._clientes = 0

    def start(self) -> bool:
        self._running = self.arranca
        return self.arranca

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def follower_url(self) -> str:
        return "http://10.0.0.5:8080/?k=abc"

    def client_count(self) -> int:
        return self._clientes

    def broadcast(self, payload: dict) -> None:
        self.payloads.append(payload)


@pytest.fixture
def caja(qapp, monkeypatch):
    monkeypatch.setattr(mod, "hay_red_utilizable", lambda: True)
    servidor = _Servidor()
    box = ClassroomBox(servidor)
    box.registro: list[str] = []
    box.avisos: list[str] = []
    box.arranques: list[bool] = []
    box.logged.connect(box.registro.append)
    box.warned.connect(box.avisos.append)
    box.started.connect(lambda: box.arranques.append(True))
    yield box, servidor
    box.deleteLater()
    qapp.processEvents()


def test_turning_it_on_offers_the_link_and_asks_the_tab_for_the_config(caja) -> None:
    box, servidor = caja
    assert not box.is_running() and not box._btn_copy.isVisible() and not box._btn_qr.isEnabled()
    box._chk.setChecked(True)
    assert servidor.is_running() and box.is_running()
    assert servidor.follower_url() in box._lbl.text()
    assert box._btn_qr.isEnabled()
    assert box.arranques == [True]
    assert any("follow at" in line for line in box.registro)
    # Nobody has joined: the warning is armed, for a minute and a half.
    assert box._timer_sin_seguidores is not None and box._timer_sin_seguidores.isActive()
    assert box._timer_sin_seguidores.interval() == ESPERA_SEGUIDORES_MS
    box._chk.setChecked(False)
    assert not servidor.is_running() and box._lbl.text() == ""
    assert not box._timer_sin_seguidores.isActive() and not box._btn_qr.isEnabled()
    assert any("off" in line for line in box.registro)
    assert box.avisos == []


def test_without_a_network_it_says_so_instead_of_waiting(caja, monkeypatch) -> None:
    box, _servidor = caja
    monkeypatch.setattr(mod, "hay_red_utilizable", lambda: False)
    box._on_toggle(True)
    assert box.avisos == [aviso_sin_red()]
    assert "No network" in box._lbl.text()
    assert box._timer_sin_seguidores is None


def test_a_port_in_use_unticks_the_box_and_names_the_port(qapp) -> None:
    servidor = _Servidor(arranca=False, puerto_fallido=8080)
    box = ClassroomBox(servidor)
    avisos: list[str] = []
    box.warned.connect(avisos.append)
    box._chk.setChecked(True)
    assert not box._chk.isChecked()
    assert avisos == [aviso_puerto_ocupado(8080)]
    box.deleteLater()


def test_the_first_follower_disarms_the_warning_and_is_counted(caja) -> None:
    box, servidor = caja
    box._on_toggle(True)
    servidor._clientes = 0
    box._avisar_sin_seguidores()
    assert box.avisos == [aviso_sin_seguidores()]
    servidor.clients_changed.emit(2)
    assert not box._timer_sin_seguidores.isActive()
    assert "2 following" in box._lbl.text()


def test_what_the_followers_are_sent(caja) -> None:
    box, servidor = caja
    # Off: nothing goes out but the config and status the tab chooses to send.
    box.live([[0.1] * 100], 1, {"warn": 30.0, "danger": 60.0, "ch": []})
    box.calib(True, "ready", "Título")
    box.marker(1.26, "fatigue")
    assert servidor.payloads == []
    box._on_toggle(True)
    servidor.payloads.clear()
    box.config(2, ["flexor", "extensor"], False)
    box.status(True)
    carga = {"warn": 30.0, "danger": 60.0,
             "ch": [{"active": True, "pct": 12.5, "static": 5.0, "median": 10.0,
                     "peak": 20.0, "zone": "ok"}]}
    box.live([[i / 100 for i in range(100)]], 1, carga)
    box.calib(True, "contract", "Pull", "hard", count=[True, False], secs=2.5)
    box.calib(False)
    box.marker(1.26, "fatigue")
    assert servidor.payloads[0] == {"t": "config", "n": 2, "labels": ["flexor", "extensor"],
                                    "recording": False}
    assert servidor.payloads[1] == {"t": "status", "recording": True}
    datos = servidor.payloads[2]
    assert datos["t"] == "data" and len(datos["env"]) == 1 and len(datos["env"][0]) == 8
    assert datos["env"][0][0] == 0.0 and datos["env"][0][-1] == pytest.approx(0.84)
    assert servidor.payloads[3] == {"t": "load", **carga}
    assert servidor.payloads[4] == {"t": "calib", "active": True, "phase": "contract",
                                    "title": "Pull", "sub": "hard", "count": [True, False],
                                    "secs": 2.5, "progress": None, "effort": None}
    assert servidor.payloads[5]["active"] is False
    assert servidor.payloads[6] == {"t": "marker", "time": 1.3, "label": "fatigue"}


def test_the_tab_builds_it_on_the_identifier_s_line(qapp) -> None:
    """Same line, same controls, same order as before the split: the box
    sits after the identifier, and the whole row is what the basic level
    hides."""
    from tests.test_arreglos_pantalla import _cierra, _ventana

    win = _ventana(qapp, "single")
    try:
        adq = win._tab_adq
        assert isinstance(adq._aula, ClassroomBox)
        assert adq._aula.parent() is adq._box_aula
        fila = adq._box_aula.layout()
        assert fila.itemAt(fila.count() - 1).widget() is adq._aula
        assert adq._aula.is_running() is False
    finally:
        _cierra(qapp, win)
