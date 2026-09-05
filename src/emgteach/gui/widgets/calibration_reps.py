"""CalibrationRepsDialog — keep or discard calibration repetitions.

The calibration is not continuous signal: it is a handful of discrete maximal
efforts, each already delimited in the file by its own ``CAL`` span. Editing
that with the free fragment editor would treat as continuous something that
arrives already cut, and would open the door to trimming a repetition down to
its peak — which inflates the reference and every %MVC after it.

So the choice offered is the one that actually happened: **this repetition
counts, that one does not**. Marking and unmarking over spans the wizard drew.

Two numbers sit beside each repetition, because "was this one any good" has two
halves and only one of them is visible in the value:

* what it was worth, in mV and as a share of the best — a repetition well below
  the others is a subject still warming up, or one that slipped;
* **what the other muscle reached during it**, as a share of *its* own
  reference. On the bench, the extensor's first repetition carried 41 % of the
  flexor while its second and third carried 23 % and 20 %: same value, quite
  different repetition.

Nothing is discarded automatically and nothing is forbidden except emptying a
channel: a channel with no repetition kept is not a calibration with a smaller
reference, it is no calibration at all, and that is done by not calibrating.

The dialog only decides *which*; the reference is recomputed by
:func:`emgteach.phases.mvc_reference`, which is the one place that knows how.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
)

from emgteach.i18n import tr

__all__ = ["CalibrationRepsDialog"]

_AVISO = "color: #8a5000;"
_FLOJA = "color: #8a5000; font-weight: bold;"
_TENUE = "color: #666666; font-size: 11px;"

#: A repetition this far below the best one is worth a second look. Not a
#: verdict and not a default: nothing is unticked for the operator.
_FLOJA_PCT = 70.0
#: And one whose neighbour was this active during it. Same threshold the
#: acquisition wizard warns at, for the same reason.
_DIAFONIA_PCT = 50.0


class CalibrationRepsDialog(QDialog):
    """Pick which calibration repetitions the reference is computed from."""

    def __init__(
        self,
        rep_values: dict[int, tuple],
        labels: dict[int, str],
        references: dict[int, float] | None = None,
        keep: dict[int, set[int]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Calibration repetitions"))
        self._valores = rep_values
        self._labels = labels
        self._refs = references or {}
        self._casillas: dict[tuple[int, int], QCheckBox] = {}
        self._resumen: dict[int, QLabel] = {}
        self._build(keep or {})
        self._refrescar()

    # ------------------------------------------------------------------

    def _build(self, keep: dict[int, set[int]]) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(tr(
            "Each maximal effort the wizard recorded. Unticking one leaves it "
            "out of the reference — and out of every % MVC computed from it."
        ))
        intro.setWordWrap(True)
        root.addWidget(intro)

        for canal, valores in sorted(self._valores.items()):
            if not valores:
                continue
            titulo = QLabel(f"<b>{self._labels.get(canal, str(canal + 1))}</b>")
            root.addWidget(titulo)

            rejilla = QGridLayout()
            rejilla.setContentsMargins(12, 0, 0, 0)
            rejilla.setHorizontalSpacing(14)
            mejor = max((v.value_mv for v in valores), default=0.0)
            for fila, v in enumerate(valores):
                guardadas = keep.get(canal)
                caja = QCheckBox(tr("rep {n}").format(n=v.rep))
                caja.setChecked(guardadas is None or v.rep in guardadas)
                caja.toggled.connect(self._refrescar)
                self._casillas[(canal, v.rep)] = caja
                rejilla.addWidget(caja, fila, 0)

                cuota = 100.0 * v.value_mv / mejor if mejor > 0 else 0.0
                valor = QLabel(f"{v.value_mv:.4f} mV")
                cuota_lbl = QLabel(tr("{pct:.0f} % of the best").format(pct=cuota))
                if cuota < _FLOJA_PCT:
                    cuota_lbl.setStyleSheet(_FLOJA)
                rejilla.addWidget(valor, fila, 1)
                rejilla.addWidget(cuota_lbl, fila, 2)

                if v.crosstalk_pct is not None:
                    cruce = QLabel(tr("other muscle at {pct:.0f} %").format(
                        pct=v.crosstalk_pct))
                    cruce.setStyleSheet(
                        _AVISO if v.crosstalk_pct >= _DIAFONIA_PCT else _TENUE
                    )
                    cruce.setToolTip(tr(
                        "What the other channel reached during this effort, as "
                        "a share of its own reference. Some of it is the "
                        "antagonist steadying the joint and some is this "
                        "muscle's own signal conducted through the tissue; "
                        "neither can be separated from two bipolar channels, "
                        "and around 20 % is normal."
                    ))
                    rejilla.addWidget(cruce, fila, 3)
            root.addLayout(rejilla)

            resumen = QLabel()
            resumen.setContentsMargins(12, 2, 0, 8)
            self._resumen[canal] = resumen
            root.addWidget(resumen)

            linea = QFrame()
            linea.setFrameShape(QFrame.Shape.HLine)
            linea.setStyleSheet("color: #dddddd;")
            root.addWidget(linea)

        self._botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._botones.accepted.connect(self.accept)
        self._botones.rejected.connect(self.reject)
        root.addWidget(self._botones)

    # ------------------------------------------------------------------

    def keep(self) -> dict[int, set[int]]:
        """``{channel_index: {rep numbers kept}}`` for the current ticks."""
        salida: dict[int, set[int]] = {}
        for (canal, rep), caja in self._casillas.items():
            if caja.isChecked():
                salida.setdefault(canal, set()).add(rep)
        return salida

    def reference_for(self, canal: int) -> float:
        """The reference the current selection gives: best of what is kept.

        The same rule :func:`emgteach.mvc.mvc_from_reps` applies, on the same
        numbers, so what this dialog promises is what the analysis delivers.
        """
        marcadas = self.keep().get(canal, set())
        return max(
            (v.value_mv for v in self._valores.get(canal, ()) if v.rep in marcadas),
            default=0.0,
        )

    def _refrescar(self) -> None:
        """Say what the current ticks are worth, and refuse to empty a channel."""
        vacio = False
        for canal, valores in self._valores.items():
            if not valores:
                continue
            antes = self._refs.get(canal) or max(
                (v.value_mv for v in valores), default=0.0)
            ahora = self.reference_for(canal)
            etiqueta = self._resumen.get(canal)
            if etiqueta is None:
                continue
            if ahora <= 0:
                vacio = True
                etiqueta.setText(tr(
                    "Keep at least one repetition: a channel with none is not a "
                    "calibration with a smaller reference, it is no calibration."
                ))
                etiqueta.setStyleSheet(_AVISO)
                etiqueta.setWordWrap(True)
                continue
            cambio = (
                tr("unchanged") if abs(ahora - antes) < 1e-9
                else tr("was {before:.4f} mV, {pct:+.0f} %").format(
                    before=antes, pct=100.0 * (ahora - antes) / antes)
            )
            etiqueta.setText(tr(
                "Reference with this selection: {value:.4f} mV — {change}"
            ).format(value=ahora, change=cambio))
            etiqueta.setStyleSheet("" if abs(ahora - antes) < 1e-9 else _AVISO)
        self._botones.button(
            QDialogButtonBox.StandardButton.Ok
        ).setEnabled(not vacio)
