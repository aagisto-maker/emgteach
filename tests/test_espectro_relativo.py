"""Panel 3 draws each spectrum scaled to unit area.

The PSD goes with the square of the amplitude, so in mV²/Hz the height of
one muscle against the other compared skin and electrode placement — what
the % MVC panels exist not to compare — and the muscle that contracts less
was pinned to the axis. Scaled to unit area each curve is a density: read by
shape, with the MDF line splitting its shaded area in two equal halves. The
total power goes in the legend, and a muscle whose power is a small fraction
of the other's is drawn faint and said to be so. MDF and MNF are invariant
to the scaling: nothing computed changes.
"""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure
from scipy.integrate import trapezoid

from emgteach.figures import (
    PSD_FAINT_RATIO,
    draw_psd_panel,
    draw_spectrum_before_filter,
    relative_spectrum,
    spectrum_power,
)
from emgteach.i18n import get_language, set_language, tr

F = np.linspace(20.0, 450.0, 216)


def _campana(centro: float, escala: float) -> np.ndarray:
    return escala * np.exp(-((F - centro) ** 2) / 2000.0)


def _resultado(escala_1: float = 3e-4, escala_2: float = 4e-5) -> dict:
    return {
        "frequencies": F, "psd": _campana(90.0, escala_1), "mnf": 95.0, "mdf": 90.0,
        "frequencies_2": F, "psd_2": _campana(120.0, escala_2), "mdf_2": 120.0,
        "channel_name": "FCR", "channel_name_2": "ECR", "f_high": 450.0,
    }


def _curvas(ax) -> dict[str, object]:
    """The solid lines by the muscle their legend entry names."""
    return {ln.get_label().split(" ")[0]: ln for ln in ax.lines
            if ln.get_label() and not ln.get_label().startswith("_")
            and ln.get_linestyle() == "-"}


class TestUnitArea:
    def test_both_curves_have_unit_area_whatever_their_power(self) -> None:
        """Seven times less power in one muscle, and the two curves are as
        tall as their shapes make them."""
        ax = Figure().add_subplot(111)
        draw_psd_panel(ax, _resultado())
        curvas = _curvas(ax)
        assert set(curvas) == {"FCR", "ECR"}
        for ln in curvas.values():
            x, y = ln.get_xdata(), ln.get_ydata()
            assert float(trapezoid(y, x)) == pytest.approx(1.0, rel=1e-9)
        assert ax.get_ylabel() == tr("Relative spectral density (area 1)")

    def test_the_relative_spectrum_keeps_the_median_where_it_was(self) -> None:
        psd = _campana(90.0, 3e-4)
        rel = relative_spectrum(F, psd)
        for p in (psd, rel):
            acumulada = np.cumsum(p) / np.sum(p)
            assert F[np.searchsorted(acumulada, 0.5)] == pytest.approx(90.0, abs=2.5)

    def test_the_legend_carries_the_mdf_and_the_total_power(self) -> None:
        ax = Figure().add_subplot(111)
        r = _resultado()
        draw_psd_panel(ax, r)
        etiquetas = [ln.get_label() for ln in _curvas(ax).values()]
        assert any("MDF 90 Hz" in e for e in etiquetas)
        assert any("MDF 120 Hz" in e for e in etiquetas)
        potencia = spectrum_power(F, r["psd"])
        assert all("mV²" in e for e in etiquetas)
        assert any(f"{potencia:.2g}" in e for e in etiquetas)

    def test_a_working_but_weaker_muscle_is_not_called_noise(self) -> None:
        """One bench pair sat at 13 % of the other's power, and was a muscle."""
        ax = Figure().add_subplot(111)
        draw_psd_panel(ax, _resultado(3e-4, 3e-4 * 0.13))
        for ln in _curvas(ax).values():
            assert ln.get_alpha() in (None, 1.0)
            assert "?" not in ln.get_label()

    @pytest.mark.parametrize("idioma, aviso", [("en", "noise?"), ("es", "¿ruido?")])
    def test_a_noise_spectrum_is_drawn_faint_and_said_to_be(self, idioma, aviso) -> None:
        anterior = get_language()
        try:
            set_language(idioma)
            ax = Figure().add_subplot(111)
            draw_psd_panel(ax, _resultado(3e-4, 3e-4 * PSD_FAINT_RATIO * 0.5))
            curvas = _curvas(ax)
        finally:
            set_language(anterior)
        assert curvas["ECR"].get_alpha() < 1.0
        assert aviso in curvas["ECR"].get_label() and "FCR" in curvas["ECR"].get_label()
        assert curvas["FCR"].get_alpha() in (None, 1.0)

    def test_one_muscle_draws_the_raw_spectrum_relative_too(self) -> None:
        ax = Figure().add_subplot(111)
        f_raw = np.linspace(0.0, 500.0, 251)
        psd = _campana(90.0, 3e-4)
        bruto = 3e-4 * np.exp(-((f_raw - 90.0) ** 2) / 2000.0) + 1e-2 * np.exp(-((f_raw - 50.0) ** 2) / 2)
        draw_psd_panel(ax, {
            "frequencies": F, "psd": psd, "mnf": 95.0, "mdf": 90.0,
            "frequencies_raw": f_raw, "psd_raw": bruto, "f_high": 450.0,
        })
        solidas = [ln for ln in ax.lines if ln.get_linestyle() == "-"]
        assert len(solidas) == 2
        for ln in solidas:
            assert float(trapezoid(ln.get_ydata(), ln.get_xdata())) == pytest.approx(1.0, rel=1e-9)
        # The axis follows the filtered spectrum; the mains line goes off the top.
        assert ax.get_ylim()[1] == pytest.approx(1.35 * float(np.max(relative_spectrum(F, psd))), rel=1e-6)

    def test_the_raw_alone_is_scaled_to_the_filtered_ones_area(self) -> None:
        ax = Figure().add_subplot(111)
        f = np.linspace(0, 500, 251)
        psd = np.exp(-((f - 90) ** 2) / 2000)
        draw_spectrum_before_filter(ax, {"frequencies_raw": f, "psd_raw": psd, "psd": psd})
        assert len(ax.lines) == 1
        assert float(trapezoid(ax.lines[0].get_ydata(), f)) == pytest.approx(1.0, rel=1e-9)
