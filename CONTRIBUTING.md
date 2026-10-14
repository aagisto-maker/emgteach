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
has no wheels for 3.13+ yet). Both hardware backends work on all three: they
speak their device over `pyserial`, with no PyBluez and no compiler needed.

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

To work on the documentation or the Windows executables, install the matching
extras: `".[dev,docs]"`, `".[dev,build]"`, or `".[all]"`. Both hardware backends
(Arduino and BITalino) need nothing beyond the core dependencies.

## Running the checks

```bash
# Test suite (skip tests that need real hardware)
pytest -m "not hardware" -q

# On a headless machine (CI, servers) force Qt's offscreen platform:
QT_QPA_PLATFORM=offscreen pytest -m "not hardware" -q

# Lint
ruff check .

# Type check (enforced in CI)
mypy src/emgteach
```

All pull requests must keep the test suite green and pass `ruff check` and
`mypy src/emgteach` with no errors; the CI fails on any of the three. A value
read from `QSettings` is `object` to mypy: give it its type with
`typing.cast`, as the tabs do.

Tests are marked with `hardware` (needs a physical device), `gui` (needs a
`QApplication`, via `pytest-qt`) and `slow`. The default CI run excludes
`hardware`.

## Comparing with the sibling apps

emgteach, ecgteach and eegteach keep hand-made copies of the same modules:
`devices/` (`base`, `bitalino`, `bitalino_sim`, `arduino`, `factory`),
`broadcast`, `crash`, `recovery`, `difusion` and the `logger` and
`help_button` widgets. Before each release, check how far this app's copies
have drifted from its siblings':

```bash
# From the root of this repository, with the siblings cloned next to it
python tools/comparar_hermanos.py ../ecgteach ../eegteach

# One module only, with the whole diff
python tools/comparar_hermanos.py ../ecgteach ../eegteach --modulo bitalino.py --completo
```

For each shared module it prints how many lines differ from each sibling and
a trimmed diff, and then a summary table. Package names (`emgteach`, ...) and
signal names (`EMG`, `ECG`, `EEG`) are normalised first, so a difference that
is only the app's name does not count. That also hides a difference that is
about the signal, such as which sensor gain a class falls back to:
`--sin-normalizar-senal` keeps the signal names.

The script only reads. It compares the files as they are on disk, and its
header names the branch and commit it read in each repository, so bring each
sibling to an up-to-date `main` first. It is not a pytest test and the CI
does not run it. The list of shared modules is at the top of the script;
keep it the same in the three copies.

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

## Releasing a version

The release publishes the Windows executable that was tried at the bench, not
a new build: PyInstaller does not reproduce a file byte for byte, so two builds
of the same commit differ (`.github/workflows/build-windows-exe.yml`).

1. Prepare the version on `main`: the version in `pyproject.toml`,
   `src/emgteach/__init__.py`, `CITATION.cff` and `.zenodo.json`, the
   `CHANGELOG.md` heading with its date, and `docs/RELEASE_NOTES_vX.Y.Z.md`.
2. Run the workflow on that commit: *Actions → Build Windows exe → Run
   workflow*, on `main`. The run builds `emgteach.exe` and
   `diagnostico_bitalino.exe`, self-tests both and attests where they were
   built. Note its number.
3. Try that run's executable at the bench (artifact `emgteach-windows-exe`),
   and note its SHA-256.
4. If it is good, tag **that same commit** and push the tag:
   `git tag -a vX.Y.Z -m "emgteach X.Y.Z" <commit>` and
   `git push origin vX.Y.Z`. If anything has to change, it is a new commit:
   back to step 2.
5. The tag's run builds nothing. It finds the latest successful manual run on
   the tag's commit, verifies the attestation of its executable (this
   workflow, this repository, this commit), checks that the executable says
   the tag's version, and creates a **draft** release with the notes, the
   run's number, the SHA-256 and `emgteach-vX.Y.Z-windows-x64.exe`. Without
   such a run it fails and creates nothing: run the workflow on the commit
   (step 2) and re-run the failed job.
6. Download the draft's executable and check that its SHA-256 is the one noted
   in step 3, and that `gh attestation verify emgteach-vX.Y.Z-windows-x64.exe
   --repo aagisto-maker/emgteach` passes. Put it through VirusTotal, then
   publish the draft by hand: publishing is what Zenodo archives.
7. Afterwards, the version DOI that Zenodo assigns goes into `CITATION.cff`
   (the previous one to the history comment).

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
