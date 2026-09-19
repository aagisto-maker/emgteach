"""The calibration asks for a brief, explosive maximal jerk.

A surface electrode on the forearm sees the compartment beneath it, and a
reference is only a yardstick if it recruits the muscle mass the task
recruits: the grip of the agonist/antagonist task needs the finger flexors,
which a clenched fist brings in and a push of the wrist leaves out. So the
wizard names each forearm gesture in that practical, and nothing on screen asks
any more for a push against something that cannot move.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from emgteach import i18n
from emgteach.modes import MODE_KINEMATICS, MODE_PAIR, MODE_SINGLE
from emgteach.pairs import PAIR_ARM, PAIR_FOREARM, PAIR_OTHER


def _gesto(mode: str, canal: int, idioma: str = "en",
           par: str = PAIR_FOREARM) -> str:
    from emgteach.gui.tabs.acquisition import AcquisitionTab

    anterior = i18n.get_language()
    try:
        i18n.set_language(idioma)
        return AcquisitionTab._mvc_gesto(
            SimpleNamespace(_mode=mode, _par=par), canal)
    finally:
        i18n.set_language(anterior)


def test_the_pair_names_each_forearm_gesture() -> None:
    """With the pair of the practical guide, which is the default."""
    flexor, extensor = _gesto(MODE_PAIR, 0), _gesto(MODE_PAIR, 1)
    assert "jerk" in flexor and "wrist flexion" in flexor and "fist" in flexor
    assert "jerk" in extensor and "wrist extension" in extensor
    assert "hand open" in extensor
    assert "sacudida" in _gesto(MODE_PAIR, 0, "es")


def test_another_pair_names_its_own_gesture_or_none() -> None:
    """The rule is the same for every pair; the example is the pair's."""
    codo = _gesto(MODE_PAIR, 0, par=PAIR_ARM)
    assert "jerk" in codo and "elbow flexion" in codo
    assert "wrist" not in codo
    otro = _gesto(MODE_PAIR, 0, par=PAIR_OTHER)
    assert "jerk" in otro
    for anatomia in ("wrist", "elbow", "fist", "forearm"):
        assert anatomia not in otro, otro


@pytest.mark.parametrize("mode", [MODE_SINGLE, MODE_KINEMATICS])
def test_the_other_practicals_give_the_general_rule(mode) -> None:
    """The single-muscle practical may be on the biceps, and the kinematics
    one always is: a wrist gesture would be the wrong instruction there."""
    texto = _gesto(mode, 0)
    assert "jerk" in texto
    assert "wrist" not in texto and "fist" not in texto


def test_nothing_asks_for_a_push_against_something_that_cannot_move() -> None:
    for clave, valor in i18n._ES.items():
        for texto in (clave, valor):
            t = texto.lower()
            for viejo in ("cannot move", "underside", "no se pueda mover",
                          "canto inferior", "no pueda moverse"):
                assert viejo not in t, (viejo, clave[:60])
