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
        """And the same thing end to end, on a real string.

        Whether a *particular* sentence outgrows the floor is a property of
        the font the machine has, not of the widget: with Arial this one needs
        149 px and the panel goes to 241, while the fallback on a bare Linux
        runner puts it under the 118 px that would be needed. So the case is
        exhibited where it can be and declared unexhibitable where it cannot —
        the rule itself is covered above, on every platform.

        The first attempt at this guard compared the two texts' measurements,
        which was the wrong question: the runner *does* tell them apart, just
        not by enough.
        """
        overlay.show_done("MVC ready", "Short.")
        corto = overlay.height()
        overlay.show_done("MVC ready", self._LARGO)
        if overlay.height_for_text() <= corto:
            pytest.skip(
                "this Qt's fonts measure the message under the panel's own "
                "floor, so a real string cannot exhibit the growth here"
            )
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


# ---------------------------------------------------------------------------
# The title has to fit as well
# ---------------------------------------------------------------------------


#: Every title the wizard passes to the overlay, by mode, with the longest
#: label and repetition tag actually used. The brief-squeeze instruction is
#: the author's sentence, word for word, and in Spanish it is twice the
#: panel's width at the title's size.
def _titulos() -> list[tuple[str, str]]:
    from emgteach.i18n import tr

    label = "ECR"
    breve = tr(" (brief {i}/{n})").format(i=1, n=3)
    return [
        ("ready", tr("Get ready — {label}{rep}").format(label=label, rep=breve)),
        ("contract", tr(
            "Make a single, brief contraction of {label} with the greatest "
            "force you can{rep}"
        ).format(label=label, rep=breve)),
        ("contract", tr("Contract {label} at maximum!{rep}").format(
            label=label, rep=breve)),
        ("contract", tr("Contract at maximum! (no load)")),
        ("done", tr("Channels not separated")),
        ("done", tr("Calibration too weak")),
    ]


def _mostrar_titulo(overlay, modo: str, titulo: str) -> None:
    if modo == "ready":
        overlay.show_ready(titulo, 3, "x")
    elif modo == "done":
        overlay.show_done(titulo, "x")
    else:
        overlay.show_contract(titulo, 2.0, 0.5, 0.6)


class TestNoTitleLeavesThePanel:
    """Reported a second time from the bench, after the messages were fixed:
    the brief-squeeze instruction is drawn as the *title*, and the title was
    still a single bold line."""

    def test_every_real_title_fits_its_band(self, overlay, idioma) -> None:
        malos = []
        for modo, titulo in _titulos():
            _mostrar_titulo(overlay, modo, titulo)
            _x, _y, _w, alto = overlay.title_rect()
            if overlay.title_height() > alto:
                malos.append(f"[{idioma}/{modo}] {titulo[:60]!r}")
        assert not malos, "titles that overflow their band:\n" + "\n".join(malos)

    def test_the_message_starts_below_the_title(self, overlay, idioma) -> None:
        """A wrapped title pushes the message down instead of being drawn
        over it — and the whole thing still ends inside the panel."""
        for modo, titulo in _titulos():
            _mostrar_titulo(overlay, modo, titulo)
            _x, ty, _w, th = overlay.title_rect()
            _x, my, _w, mh = overlay.message_rect()
            assert ty + th <= my, f"{modo}: {titulo[:40]!r}"
            assert my + mh <= overlay.height()

    def test_a_long_title_moves_everything_down(self, overlay, monkeypatch) -> None:
        """The mechanism, independent of the machine's fonts: what the title
        measures is what the rest of the panel moves by."""
        overlay.show_contract("Short", 2.0, 0.5, 0.6)
        _x, y_corto, _w, _h = overlay.message_rect()
        alto_corto = overlay.height()
        monkeypatch.setattr(type(overlay), "title_height",
                            lambda self, text=None: 120)
        overlay.show_contract("Long enough to need four lines", 2.0, 0.5, 0.6)
        _x, y_largo, _w, _h = overlay.message_rect()
        assert y_largo - y_corto == 120 - 30
        assert overlay.height() > alto_corto

    def test_modes_without_a_title_band_report_none(self, overlay) -> None:
        overlay.show_relax("x")
        assert overlay.title_height() == 0
        assert overlay.title_rect() == (0, 0, 0, 0)
