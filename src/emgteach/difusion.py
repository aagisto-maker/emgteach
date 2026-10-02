"""The classroom broadcast's two ports, written in a text file next to the application.

The broadcast opens two ports on the operator PC: one serves the page the
phones load, the other carries the live data. Which ports get through depends
on the network the phones are on, and that varies from one building to
another. So the ports are not fixed in the application: a laboratory writes
them once in ``difusion.txt``, next to the application, and every station
reads them from there::

    # Ports of the broadcast to the phones
    pagina = 8080
    datos = 8443

Without the file, the defaults are used (8080 for the page, 8443 for the
data). The ports are the laboratory's, the same on every station; the board's
address, which changes from one station to the next, stays in
``bitalino.txt`` (see :mod:`station`).

A value that cannot be used — not a number, outside 1-65535, the two ports
equal, or a line that is not one of the two names — puts back both defaults,
and the offending line is returned so the application can say which one it
was.

Qt-free and with no import from the rest of the package but ``station``, so
the same file serves the three applications of the family.
"""

from __future__ import annotations

from pathlib import Path

from .station import app_folder

#: The file's name, next to the application.
PORTS_FILE = "difusion.txt"

#: The port of the page the phones load, and the port of the live data.
DEFAULT_PAGE_PORT = 8080
DEFAULT_DATA_PORT = 8443

_PAGE_KEYS = ("pagina", "página")
_DATA_KEYS = ("datos",)


def ports_file(folder: Path | None = None) -> Path:
    """Where ``difusion.txt`` is looked for."""
    return (app_folder() if folder is None else Path(folder)) / PORTS_FILE


def _port(value: str) -> int | None:
    try:
        port = int(value.strip())
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


def read_broadcast_ports(folder: Path | None = None) -> tuple[int, int, str | None]:
    """The page port and the data port, and the line that could not be used.

    Returns ``(page, data, None)`` when the file is missing or all its lines
    are good; a name the file leaves out keeps its default. When a line
    cannot be used, returns both defaults and that line as written, so it can
    be reported once.
    """
    defaults = (DEFAULT_PAGE_PORT, DEFAULT_DATA_PORT)
    try:
        text = ports_file(folder).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return (*defaults, None)
    page, data = defaults
    last = ""
    for line in text.splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry:
            continue
        name, sep, value = entry.partition("=")
        name = name.strip().lower()
        port = _port(value) if sep else None
        if port is None or name not in _PAGE_KEYS + _DATA_KEYS:
            return (*defaults, line.strip())
        if name in _PAGE_KEYS:
            page = port
        else:
            data = port
        last = line.strip()
    if page == data:
        return (*defaults, last)
    return page, data, None
