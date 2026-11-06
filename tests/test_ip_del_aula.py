"""Which address of this computer the phones' link carries (broadcast.choose_ipv4).

It used to be the first IPv4 of the first interface the system listed. On
laboratory PCs other than the teacher's the phones could not load the page:
the link carried a virtual adapter's address (WSL, VirtualBox, a VPN), on a
network no phone was on. The address is now chosen, and every candidate is
written to the event log with the choice and its reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from emgteach import broadcast, difusion, i18n
from emgteach.broadcast import (
    AddressChoice,
    Candidate,
    address_report,
    choose_ipv4,
    current_address_choice,
)
from emgteach.difusion import read_broadcast_address, read_broadcast_ports

WSL = Candidate("172.27.32.1", "vEthernet (WSL)", virtual=True)
VBOX = Candidate("192.168.56.1", "VirtualBox Host-Only Network", virtual=True)
VPN = Candidate("10.212.134.5", "GlobalProtect VPN", virtual=True)
CABLE = Candidate("10.1.2.3", "Ethernet")
WIFI = Candidate("192.168.0.14", "Wi-Fi")
HOTSPOT = Candidate("192.168.137.1", "Conexión de área local* 10")


@pytest.fixture(autouse=True)
def en_ingles():
    previa = i18n.get_language()
    i18n.set_language("en")
    yield
    i18n.set_language(previa)


# ── The choice ───────────────────────────────────────────────────────────────

def test_a_virtual_adapter_listed_first_is_not_chosen() -> None:
    elegida = choose_ipv4([WSL, VBOX, CABLE], route="10.1.2.3")
    assert (elegida.ip, elegida.reason) == ("10.1.2.3", "route")
    # Without a default route, the first one that is not virtual.
    elegida = choose_ipv4([WSL, VBOX, CABLE], route=None)
    assert (elegida.ip, elegida.reason) == ("10.1.2.3", "first_real")


def test_with_cable_and_wifi_the_default_route_decides() -> None:
    assert choose_ipv4([CABLE, WIFI], route="192.168.0.14").ip == "192.168.0.14"
    assert choose_ipv4([CABLE, WIFI], route="10.1.2.3").ip == "10.1.2.3"


def test_the_mobile_hotspot_wins_and_says_where_the_route_goes() -> None:
    elegida = choose_ipv4([CABLE, HOTSPOT], route="10.1.2.3")
    assert (elegida.ip, elegida.reason) == ("192.168.137.1", "hotspot")
    ultima = address_report(elegida)[-1]
    assert "the mobile hotspot, 192.168.137.1" in ultima
    assert "the default route goes through Ethernet (10.1.2.3)" in ultima
    sin_ruta = address_report(choose_ipv4([HOTSPOT], route=None))[-1]
    assert "there is no default route" in sin_ruta


def test_the_hotspot_line_says_it_in_the_words_asked_for_in_spanish() -> None:
    i18n.set_language("es")
    ultima = address_report(choose_ipv4([CABLE, HOTSPOT], route="10.1.2.3"))[-1]
    assert ultima.startswith("Se elige el punto de acceso móvil, 192.168.137.1; "
                             "la ruta por defecto va por Ethernet (10.1.2.3).")


def test_a_vpn_that_takes_all_the_traffic_does_not_take_the_link() -> None:
    elegida = choose_ipv4([VPN, CABLE], route="10.212.134.5")
    assert (elegida.ip, elegida.reason) == ("10.1.2.3", "first_real")


def test_with_only_virtual_adapters_one_is_given_and_the_log_warns() -> None:
    elegida = choose_ipv4([WSL, VBOX], route=None)
    assert (elegida.ip, elegida.reason) == ("172.27.32.1", "virtual")
    assert "may not reach it" in address_report(elegida)[-1]


def test_without_any_network_it_is_no_network() -> None:
    elegida = choose_ipv4([], route=None)
    assert (elegida.ip, elegida.reason) == ("127.0.0.1", "none")
    assert address_report(elegida) == [
        "Broadcast: this computer has no IPv4 address the phones could reach."]


def test_an_address_fixed_in_difusion_txt_wins_when_it_is_there() -> None:
    elegida = choose_ipv4([CABLE, WIFI], route="10.1.2.3", fixed_ip="192.168.0.14")
    assert (elegida.ip, elegida.reason) == ("192.168.0.14", "fixed_ip")
    # Not on the computer now: said, and chosen otherwise.
    elegida = choose_ipv4([CABLE, WIFI], route="10.1.2.3", fixed_ip="192.168.9.9")
    assert (elegida.ip, elegida.reason) == ("10.1.2.3", "route")
    assert any("192.168.9.9" in n and "not on this computer" in n for n in elegida.notes)


def test_an_interface_fixed_in_difusion_txt_survives_a_new_dhcp_address() -> None:
    elegida = choose_ipv4([WSL, CABLE, WIFI], route="10.1.2.3", fixed_interface="wi-fi")
    assert (elegida.ip, elegida.reason) == ("192.168.0.14", "fixed_interface")
    assert "of the interface «Wi-Fi»" in address_report(elegida)[-1]
    elegida = choose_ipv4([CABLE], route="10.1.2.3", fixed_interface="Wi-Fi")
    assert elegida.reason == "route"
    assert any("«Wi-Fi»" in n and "no IPv4 address" in n for n in elegida.notes)


def test_with_both_the_address_wins_and_then_the_interface() -> None:
    ambas = {"fixed_ip": "10.1.2.3", "fixed_interface": "Wi-Fi"}
    assert choose_ipv4([CABLE, WIFI], route=None, **ambas).reason == "fixed_ip"
    ambas["fixed_ip"] = "10.9.9.9"                       # a DHCP lease that changed
    elegida = choose_ipv4([CABLE, WIFI], route=None, **ambas)
    assert (elegida.ip, elegida.reason) == ("192.168.0.14", "fixed_interface")


def test_the_log_lists_every_candidate_and_marks_the_virtual_ones() -> None:
    lineas = address_report(choose_ipv4([WSL, CABLE], route="10.1.2.3"))
    assert lineas[0] == ("Broadcast addresses of this computer: 172.27.32.1 "
                         "(vEthernet (WSL), virtual); 10.1.2.3 (Ethernet).")
    assert lineas[1] == "Chosen: 10.1.2.3 (Ethernet), the one the default route goes through."


@pytest.mark.parametrize("nombre, virtual", [
    ("vEthernet (Default Switch)", True), ("vEthernet (WSL)", True),
    ("VirtualBox Host-Only Network", True), ("VMware Network Adapter VMnet8", True),
    ("Tailscale", True), ("OpenVPN TAP-Windows6", True),
    ("Ethernet", False), ("Ethernet 2", False), ("Wi-Fi", False),
    ("Conexión de área local* 10", False),
])
def test_virtual_adapters_are_told_by_their_names(nombre: str, virtual: bool) -> None:
    assert broadcast._looks_virtual(nombre) is virtual


# ── What the computer and the file say ───────────────────────────────────────

def test_the_route_is_read_without_sending_anything_and_none_without_one(monkeypatch) -> None:
    class _Sin:
        def __init__(self, *a): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def connect(self, *a): raise OSError("Network is unreachable")

    monkeypatch.setattr(broadcast.socket, "socket", _Sin)
    assert broadcast.default_route_ipv4() is None


def test_the_interfaces_of_this_computer_give_no_loopback_or_link_local() -> None:
    for c in broadcast.ipv4_candidates():
        assert not c.ip.startswith(("127.", "169.254.")) and ":" not in c.ip


def _difusion(tmp_path: Path, texto: str) -> Path:
    (tmp_path / "difusion.txt").write_text(texto, encoding="utf-8")
    return tmp_path


def test_difusion_txt_reads_the_address_and_the_interface(tmp_path: Path) -> None:
    carpeta = _difusion(tmp_path, "# station 3\nip = 192.168.1.20  # this PC\n"
                                  "interfaz = Ethernet\npagina = 8081\n")
    assert read_broadcast_address(carpeta) == ("192.168.1.20", "Ethernet")
    # And the ports' reader takes the two lines as good ones.
    assert read_broadcast_ports(carpeta) == (8081, 8443, None)
    assert read_broadcast_address(_difusion(tmp_path, "interface = Wi-Fi\n")) == (None, "Wi-Fi")
    assert read_broadcast_address(_difusion(tmp_path, "pagina = 8080\n")) == (None, None)


def test_the_choice_follows_the_file_of_this_station(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(difusion, "app_folder", lambda: tmp_path)
    monkeypatch.setattr(broadcast, "ipv4_candidates", lambda: [WSL, CABLE, WIFI])
    monkeypatch.setattr(broadcast, "default_route_ipv4", lambda: "10.1.2.3")
    assert current_address_choice().ip == "10.1.2.3"
    _difusion(tmp_path, "interfaz = Wi-Fi\n")
    assert current_address_choice().ip == "192.168.0.14"
    assert broadcast.lan_ipv4() == "192.168.0.14"


def test_no_network_is_still_no_network(monkeypatch) -> None:
    monkeypatch.setattr(broadcast, "ipv4_candidates", lambda: [])
    monkeypatch.setattr(broadcast, "default_route_ipv4", lambda: None)
    monkeypatch.setattr(broadcast, "read_broadcast_address", lambda folder=None: (None, None))
    assert broadcast.lan_ipv4() == "127.0.0.1"
    assert broadcast.hay_red_utilizable() is False


def test_a_choice_carries_what_the_report_needs() -> None:
    elegida = choose_ipv4([CABLE], route="10.1.2.3")
    assert isinstance(elegida, AddressChoice) and elegida.candidates == [CABLE]
    assert elegida.route == "10.1.2.3" and elegida.notes == []
