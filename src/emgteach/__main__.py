"""Entry point for ``python -m emgteach`` and the ``emgteach`` console script.

Launches the PySide6 desktop application with three tabs (Acquisition,
Analysis, MVC). The GUI implementation lives in :mod:`emgteach.gui`;
this module is a thin shim so the package can be invoked from the
command line.
"""

from __future__ import annotations


def main() -> int:
    """Launch the emgteach desktop application.

    Returns
    -------
    int
        Process exit code.
    """
    from emgteach.gui import main as gui_main

    return gui_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
