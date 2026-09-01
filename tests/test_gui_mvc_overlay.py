"""Every message the calibration panel can show has to fit inside it.

Reported from the bench: «algunos mensajes de la calibración se salen de la
ventana negra flotante». The panel was 460x210 fixed and only the "done"
message was word-wrapped; every other subtitle was drawn as a single centred
line into a strip 28 px tall, so anything long ran off both edges — and the
long messages are the ones that explain what went wrong, which are exactly the
ones worth reading.

It is also a regression that arrives by editing a string, not by editing the
widget: lengthening the calibration instruction in another file is what made it
visible. So the test enumerates the **real** messages, in **both languages**,
and asks the panel itself whether they fit.
"""

from __future__ import annotations

import pytest

from emgteach import i18n

pytestmark = pytest.mark.gui


#: Every subtitle the wizard passes to the overlay, by the mode it shows in.
#: Formatted with plausible values — a message only overflows once it is filled
#: in, and the muscle labels are as long as the ones actually used.
def _mensajes() -> list[tuple[str, str]]:
    from emgteach.i18n import tr

    musculos = "FCR · ECR"
    return [
        ("ready", tr(
            "Push as hard as you can when the count reaches 0 — against "
            "something that cannot move, such as the underside of the table, "
            "not against a hand"
        )),
        ("ready", tr(
            "Two or three easy contractions of each muscle. The first "
            "maximal effort of a session is never the strongest one."
        )),
        ("ready", tr(
            "The recording starts when the count reaches 0. "
            "The calibration is already saved."
        )),
        ("relax", tr("Get ready for the next repetition")),
        ("relax", tr("Next muscle: {label}").format(label="ECR")),
        ("done", tr(
            "{muscles}: this is not a maximum. Calibrate again against "
            "a resistance the joint cannot move."
        ).format(muscles=musculos)),
        ("done", tr(
            "{pairs}. Move the electrode pairs further apart, over the "
            "belly of each muscle, and support the forearm."
        ).format(pairs=tr("{other} at {pct:.0f} % during {muscle}").format(
            other="FCR", muscle="ECR", pct=61))),
        ("done", tr("{summary}\nYou can start recording.").format(
            summary="FCR: 0.08 mV · ECR: 0.34 mV")),
        ("done", tr("No signal — check the electrodes.")),
        ("contract", tr("Contract as hard as you can until the count reaches 0")),
    ]


@pytest.fixture
def overlay(qapp):
    from emgteach.gui.widgets.mvc_overlay import MvcOverlay

    widget = MvcOverlay()
    yield widget
    widget.close()


@pytest.fixture(params=["en", "es"])
def idioma(request):
    """Both languages: a Spanish string is routinely a fifth longer."""
    previo = i18n.get_language()
    i18n.set_language(request.param)
    yield request.param
    i18n.set_language(previo)


def _mostrar(overlay, modo: str, texto: str) -> None:
    if modo == "ready":
        overlay.show_ready("Get ready — FCR (rep 1/3)", 3, texto)
    elif modo == "relax":
        overlay.show_relax(texto)
    elif modo == "done":
        overlay.show_done("MVC ready", texto)
    else:
        overlay.show_contract("Contract FCR at maximum! (rep 1/3)", 2.0, 0.5, 0.6)


class TestNoMessageLeavesThePanel:
    def test_every_real_message_fits(self, overlay, idioma) -> None:
        malos = []
        for modo, texto in _mensajes():
            _mostrar(overlay, modo, texto)
            _x, _y, _w, alto = overlay.message_rect()
            necesita = overlay.text_height()
            if necesita > alto:
                malos.append(
                    f"[{idioma}/{modo}] needs {necesita} px, has {alto}: "
                    f"{texto[:60]!r}"
                )
        assert not malos, "messages that overflow the panel:\n" + "\n".join(malos)

    def test_the_message_band_stays_inside_the_panel(
        self, overlay, idioma
    ) -> None:
        """Fitting the text is not enough if the band itself hangs off the
        bottom — which is what a fixed height did to a grown message."""
        for modo, texto in _mensajes():
            _mostrar(overlay, modo, texto)
            _x, y, _w, alto = overlay.message_rect()
            assert y + alto <= overlay.height(), f"{modo}: {texto[:40]!r}"

    #: A message that needs several lines at the panel's width.
    _LARGO = ("A message long enough to need several lines once it is wrapped "
              "at the width of this panel, which a single-line strip could "
              "never have shown without running off both of its edges.")

    def test_the_panel_follows_what_the_text_measures(
        self, overlay, monkeypatch
    ) -> None:
        """The mechanism, stated without depending on the platform's fonts.

        Asserting it through a real string made this test a statement about
        the machine's font metrics rather than about the widget: on a Linux
        runner with no fonts installed the long message measured under the
        panel's own floor, both heights came out at 210, and the suite failed
        for a reason that had nothing to do with the code. What the widget
        promises is that the height follows the measurement — so the
        measurement is the thing to control.
        """
        overlay.show_done("MVC ready", "Short.")
        corto = overlay.height()
        monkeypatch.setattr(
            type(overlay), "text_height", lambda self, text=None: 400)
        overlay.show_done("MVC ready", self._LARGO)
        assert overlay.height() > corto
        assert overlay.height() >= 400

    def test_a_long_message_makes_the_panel_taller(self, overlay) -> None:
        """And the same thing end to end, wherever text can be measured.

        Skipped rather than weakened where it cannot: a machine with no fonts
        cannot tell a long message from a short one, and a test that quietly
        passed there would be claiming something it never checked.
        """
        if overlay.text_height(self._LARGO) <= overlay.text_height("Short."):
            pytest.skip("this Qt has no fonts: text cannot be measured")
        overlay.show_done("MVC ready", "Short.")
        corto = overlay.height()
        overlay.show_done("MVC ready", self._LARGO)
        assert overlay.height() > corto

    def test_a_short_message_does_not_shrink_it_below_its_floor(
        self, overlay
    ) -> None:
        overlay.show_relax("x")
        assert overlay.height() >= _altura_minima()

    def test_the_width_never_moves(self, overlay) -> None:
        """The acquisition tab centres the panel from its width, and is not
        told when it changes. Growing downwards keeps that arrangement true."""
        anchos = set()
        for modo, texto in _mensajes():
            _mostrar(overlay, modo, texto)
            anchos.add(overlay.width())
        assert len(anchos) == 1


def _altura_minima() -> int:
    from emgteach.gui.widgets.mvc_overlay import MvcOverlay

    return MvcOverlay._H
