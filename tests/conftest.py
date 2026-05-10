"""Shared pytest fixtures and Qt setup.

The Qt offscreen platform plugin is selected at import time so the
GUI-touching tests (workers and, eventually, tabs) can run on a
headless CI runner without a display server.
"""

from __future__ import annotations

import os

# Must be set before any PySide6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
