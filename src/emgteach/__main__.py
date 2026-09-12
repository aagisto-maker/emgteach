"""Entry point for ``python -m emgteach`` and the ``emgteach`` console script.

Launches the PySide6 desktop application with three tabs (Acquisition,
Analysis, MVC), unless a copy is already running — then that copy is brought
to the front and this one exits (see :mod:`emgteach.instancia`). The GUI
implementation lives in :mod:`emgteach.gui`; this module is a thin shim so
the package can be invoked from the command line.
"""

from __future__ import annotations


def main() -> int | None:
    """Launch the emgteach desktop application.

    Returns
    -------
    int or None
        Process exit code.
    """
    from emgteach.instancia import lanzar

    return lanzar()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
