"""Guided force-velocity acquisition — the load-plan dialog.

Shown before the guided wizard starts recording. The operator lists the known
loads (kg) to lift and the timing; the wizard then walks the subject through
each load (a "prepare the load" countdown, then a short recording window) and
auto-marks each window with its load, so the force-velocity study reads the
loads directly instead of the operator typing them afterwards.
"""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from emgteach.i18n import tr

# Loads are separated by any run of commas, whitespace, semicolons or newlines
# — so "2,4,6,8", "2 4 6 8" and "2; 4; 6" all work. The decimal separator is
# the dot (e.g. "7.5"); a lone comma is a list separator, not a decimal, so
# gym-style integer lists with commas parse as expected.
_SEP_RE = re.compile(r"[,\s;]+")


def parse_loads(text: str) -> list[float]:
    """Parse the loads field into a list of positive kg values, in order.

    Commas, spaces, semicolons and newlines all separate loads; the decimal
    separator is the dot. Blank and non-numeric tokens are ignored, and
    non-positive values are dropped. Duplicates and order are preserved (the
    subject lifts them in the order listed).
    """
    loads: list[float] = []
    for tok in _SEP_RE.split(text.strip()):
        if not tok:
            continue
        try:
            value = float(tok)
        except ValueError:
            continue
        if value > 0:
            loads.append(value)
    return loads


class ForceVelocityPlanDialog(QDialog):
    """Collect the load list and timing for the guided force-velocity wizard."""

    def __init__(self, parent=None, placement: str = "limb") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Guided force-velocity acquisition"))
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        intro = QLabel(tr(
            "List the known loads (kg) the subject will lift, lightest to "
            "heaviest. The wizard first guides an MVC maximum (no load), then "
            "for each load cues a quick lift ('Lift!' → 'Relax!', no hold), "
            "marking each so the force-velocity study reads the loads "
            "automatically."
        ))
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#555; font-size:11px;")
        root.addWidget(intro)

        # The force-velocity study derives velocity from the accelerometer, so
        # it must be on the moving segment. Warn (do not block) otherwise.
        if placement != "limb":
            warn = QLabel(tr(
                "⚠ The accelerometer is set to the muscle. For force-velocity "
                "put it on the moving segment (set the placement to \"on the "
                "moving segment\"), or the velocity will be near zero."
            ))
            warn.setWordWrap(True)
            warn.setStyleSheet("color:#b00020; font-size:11px;")
            root.addWidget(warn)

        form = QFormLayout()
        self._edit_loads = QLineEdit()
        self._edit_loads.setPlaceholderText(tr("e.g.  2, 4, 6, 8"))
        self._edit_loads.setToolTip(tr(
            "Separate loads with commas or spaces; use a dot for decimals "
            "(e.g. 7.5)."
        ))
        form.addRow(tr("Loads (kg):"), self._edit_loads)

        self._spin_reps = QSpinBox()
        self._spin_reps.setRange(1, 5)
        self._spin_reps.setValue(1)
        self._spin_reps.setToolTip(tr(
            "Contractions to perform at each load. The wizard prompts one at a "
            "time; keep it low (1-3) so fatigue does not bias the heavier loads."
        ))
        form.addRow(tr("Contractions per load:"), self._spin_reps)

        self._spin_prep = QDoubleSpinBox()
        self._spin_prep.setRange(1.0, 20.0)
        self._spin_prep.setValue(5.0)
        self._spin_prep.setSuffix(" s")
        self._spin_prep.setToolTip(tr("Countdown to prepare before each contraction."))
        form.addRow(tr("Prepare time:"), self._spin_prep)

        self._spin_window = QDoubleSpinBox()
        self._spin_window.setRange(0.5, 5.0)
        self._spin_window.setSingleStep(0.5)
        self._spin_window.setValue(1.5)
        self._spin_window.setSuffix(" s")
        self._spin_window.setToolTip(tr(
            "Time given for each loaded lift — a quick concentric movement, not "
            "a hold (the MVC maximum is held separately)."
        ))
        form.addRow(tr("Lift time:"), self._spin_window)
        root.addLayout(form)

        self._error = QLabel("")
        self._error.setStyleSheet("color:#b00020; font-size:11px;")
        self._error.setWordWrap(True)
        root.addWidget(self._error)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        root.addWidget(self._buttons)

    def _on_accept(self) -> None:
        if len(self.loads()) < 2:
            self._error.setText(tr(
                "Enter at least two positive loads (kg), separated by spaces."
            ))
            return
        self.accept()

    # -- results -------------------------------------------------------------

    def loads(self) -> list[float]:
        return parse_loads(self._edit_loads.text())

    def reps(self) -> int:
        return int(self._spin_reps.value())

    def prep_seconds(self) -> float:
        return float(self._spin_prep.value())

    def window_seconds(self) -> float:
        return float(self._spin_window.value())
