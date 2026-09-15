"""Entry point of the connection diagnostic's executable, ``diagnostico_bitalino.exe``.

Double-clicked, it reads the address from ``bitalino.txt`` next to it (or
autodetects the board), runs the checks and keeps its window open until
Enter is pressed. From a console it takes the address as an argument —
``diagnostico_bitalino.exe simulada``, ``… COM5``, ``… 98:D3:91:FE:44:E4`` —
and ``--seconds`` for a longer or shorter acquisition. The exit code is 0 when
the station is ready to record.
"""

from __future__ import annotations

import sys


def main() -> int:
    from emgteach.diagnostics import main as diagnose
    from emgteach.i18n import tr

    # A console that cannot show a character («, →) must not stop the diagnosis.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    code = diagnose(sys.argv[1:])
    if getattr(sys, "frozen", False):
        try:
            input("\n" + tr("Press Enter to close."))
        except (EOFError, OSError):
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
