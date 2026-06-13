# Contributing to emgteach

Thanks for your interest in improving **emgteach**, an open-source teaching
platform for surface electromyography. Contributions of all kinds are
welcome: bug reports, documentation, tests, hardware backends and features.

This project is developed and maintained at the Departmental Section of
Physiology, Faculty of Pharmacy, Universidad Complutense de Madrid.

## Ways to contribute

- **Report a bug** or request a feature on the
  [issue tracker](https://github.com/aagisto-maker/emgteach/issues). Please
  include your OS, Python version, the hardware backend (if any) and the
  steps to reproduce.
- **Improve the documentation** — typos, clarifications, examples.
- **Submit code** via a pull request (see the workflow below).

## Development setup

`emgteach` targets **Python 3.10, 3.11 or 3.12** (the pinned scientific stack
has no wheels for 3.13+ yet). The **BITalino** backend additionally requires
**Python ≤ 3.11** (its PyBluez dependency does not work on 3.12). When in
doubt, use **Python 3.11**.

```bash
git clone https://github.com/aagisto-maker/emgteach.git
cd emgteach
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

To work on the documentation or the optional backends, install the matching
extras: `".[dev,docs]"`, `".[bitalino]"`, or `".[all]"`.

## Running the checks

```bash
# Test suite (skip tests that need real hardware)
pytest -m "not hardware" -q

# On a headless machine (CI, servers) force Qt's offscreen platform:
QT_QPA_PLATFORM=offscreen pytest -m "not hardware" -q

# Lint
ruff check .

# Type check (advisory; not enforced in CI)
mypy src/emgteach
```

All pull requests must keep the test suite green and pass `ruff check`.
`mypy` is run for guidance but is **not** blocking — there are known,
pre-existing Qt/`QSettings` typing gaps in the GUI layer.

Tests are marked with `hardware` (needs a physical device), `gui` (needs a
`QApplication`, via `pytest-qt`) and `slow`. The default CI run excludes
`hardware`.

## Documentation PDFs

The manuals, lab guide, rubric and cheat sheet under `docs/` are written in
Markdown (`.md`, the source of truth). Hand-out **PDFs** are generated from
them with a small in-repo tool that uses only existing dependencies
(`reportlab` + the DejaVu fonts bundled with `matplotlib`) — no pandoc or
LaTeX needed:

```bash
# Regenerate every docs/*.md -> docs/*.pdf
python tools/md2pdf.py

# Or only specific files (paths relative to docs/)
python tools/md2pdf.py manual_emgteach_es.md cheatsheet.md
```

The generated `docs/*.pdf` are git-ignored; regenerate them after editing the
`.md` sources.

## Pull-request workflow

1. Create a feature branch off `main` (e.g. `feature/onset-export`,
   `fix/edf-label-length`). Do not commit directly to `main`.
2. Keep commits focused and write them in **English**. Messages follow a
   [Conventional Commits](https://www.conventionalcommits.org/) style with a
   scope, e.g. `feat(reports): ...`, `fix(io): ...`, `docs: ...`,
   `style(ui): ...`, `test(dsp): ...`, `ci: ...`.
3. Add or update tests for any behaviour change, and update `CHANGELOG.md`
   under the `[Unreleased]` / next-version heading.
4. Open a pull request describing the change and how you verified it. Link
   the issue it closes.

## Code and language conventions

- **Code, comments and docstrings are written in English** (the developer
  layer). Keep the analytic core (`io`, `dsp`, `fatigue`, `mvc`, `devices`,
  `profiles`, `reports`, `i18n`) free of Qt imports so it stays testable
  without a display.
- **User-facing UI text is bilingual.** Source strings are English-canonical
  and wrapped in `tr("...")` from `emgteach.i18n`; the Spanish translation
  lives in the `_ES` map in `src/emgteach/i18n.py`. To add or change a
  user-visible string:
  1. Write the English text inside `tr("...")` at the call site.
  2. Add the same English key with its Spanish value to `_ES` in `i18n.py`.
  3. Keep technical tokens (EDF, CVM/MVC, PSD, MNF/MDF, RMS, Hz) and brand
     names untranslated.
- Line length is 100 characters (`ruff` config); `E501` is not enforced, but
  keep lines reasonable.
- **Do not modify the buffer-then-flush pattern in `io.py`** unless strictly
  necessary — it is the core of the silent-corruption fix and is covered by
  round-trip tests.

## Reporting security or data-integrity issues

For anything that could silently corrupt recordings or affect data integrity,
please open an issue marked **[data-integrity]** so it can be triaged first.

## Code of conduct

Be respectful and constructive. This is a small academic project; assume good
faith, keep discussion focused on the work, and help newcomers. Harassment or
discrimination of any kind is not tolerated.

## License

By contributing, you agree that your contributions are licensed under the
project's **GPL-3.0-or-later** license. See [`LICENSE`](LICENSE). Authorship
and contribution roles are recorded in [`AUTHORS.md`](AUTHORS.md) using the
[CRediT](https://credit.niso.org/) taxonomy.
