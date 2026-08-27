"""The flow map, shown for wherever the user currently is.

Picks the picture that matches the practical and the open tab, so the map
answers "where am I" without being asked. The images are rendered ahead of
time by ``tools/generar_mapa.py``; see :mod:`emgteach.gui.mapa`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from emgteach.gui.mapa import ruta_mapa
from emgteach.i18n import tr
from emgteach.modes import mode_label

__all__ = ["MapaDialog"]


class MapaDialog(QDialog):
    """Where this recording is in the process, and what is left."""

    def __init__(self, mode: str, estacion: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Where you are"))
        self.setModal(False)      # a map is for consulting, not for answering

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 12)
        lay.setSpacing(10)

        encabezado = QLabel(
            tr("{practical} — the lit path is the one this practical uses.")
            .format(practical=mode_label(mode))
        )
        encabezado.setWordWrap(True)
        encabezado.setStyleSheet("font-size: 12px; color: #4A5A68;")
        lay.addWidget(encabezado)

        lienzo = QLabel()
        lienzo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ruta = ruta_mapa(mode, estacion)
        pix = QPixmap(str(ruta)) if ruta.exists() else QPixmap()
        if pix.isNull():
            # Rather than an empty frame: the map is generated, so a missing
            # file means the generator has not been run for this build.
            lienzo.setText(
                tr("The map for this practical has not been generated.")
            )
            lienzo.setStyleSheet("color: #8a5000; padding: 40px;")
        else:
            lienzo.setPixmap(
                pix.scaledToWidth(940, Qt.TransformationMode.SmoothTransformation)
                if pix.width() > 940 else pix
            )
        lay.addWidget(lienzo)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botones.rejected.connect(self.reject)
        botones.accepted.connect(self.accept)
        lay.addWidget(botones)
