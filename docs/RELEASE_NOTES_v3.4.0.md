# emgteach 3.4.0 — the analysis panels say how to read them

A minor version, not a patch, because it changes what the Analysis tab shows
and how it numbers it. Nothing computed changes: the MVC reference, the
co-activation index and its floor, the task maximum, the contraction table
and the fatigue analysis are those of 3.3.0.

## Changed

- **Every title says how to read its panel.** On a second line, what it
  means that the curve rises or falls — panel 7's «a decrease indicates
  muscle fatigue» was the model — and, when the panel shows one muscle, the
  muscle's name after the title. Panels that draw two muscles name them on
  their axes or in their legend.
- **The two raw panels are one.** In the agonist/antagonist practical,
  panel 1 draws the raw trace of each muscle against its own vertical axis,
  painted in the muscle's colour and carrying its name — the pattern panels
  10 and 12 already used. Two muscles in millivolts on one axis invite a
  comparison of heights that surface EMG cannot support; with an axis each,
  what the panel shows is when each muscle fires. Both axes are symmetric
  about zero and the amplitude buttons scale both. Panel 1B is gone.
- **Panel 6 draws both muscles in the pair,** each against its own axis, as
  panel 1 does: RMS is in millivolts. With one muscle it is drawn as before.
- **Panel 2 is not offered in the pair.** The normalised envelope scales each
  muscle to its own maximum within the window; panel 9 shows the same time
  course in % MVC, the yardstick the practical is about, and two yardsticks
  for one thing teach worse than one. It is not offered there even under
  «More panels…», nor in the report dialog. The other practicals keep it.
- **Panel 8 is a path through time.** It joins, in time order and with an
  arrowhead at the end, the windows in which the chosen muscle was
  contracting — the windows the fatigue trend is fitted on — with the points
  darkening as time goes on. Fatigue moves the path up and to the left: more
  amplitude, less frequency. The fitted curve is no longer drawn: it read as
  the time trend of panel 7, and time is on no axis of this plane. It is
  still computed. In a task of brief, separate contractions the windows
  alternate between efforts and the path zigzags; it reads cleanly in a
  sustained contraction, which is what the panel is for. It stays outside
  every practical's own set, under «More panels…».
- **Choosing another muscle re-runs the analysis at once.** The panels went
  on showing the previous muscle until Analyse was pressed, and none of them
  said whose they were.
- **«More panels…» is drawn like the mode buttons and says what it will
  do.** It was an auto-raise button with no colour of its own, drawn with
  faded text on Windows; open, it now reads «Fewer panels».
- **Everything that names a panel comes from one table,** `emgteach.panels`:
  the plot titles on screen and in the report, the checkboxes and their
  tooltips, the report dialog and the «P#» beside each panel. No number is
  typed anywhere else. The two muscles' colours are likewise imported from
  one place wherever something is drawn.
- **A label that showed in English now has its Spanish.** The checkbox of
  panel 12 never had a catalogue entry; a test now checks every text of the
  panel table.

## The numbering

1 to 12, the same in every practical; a practical that does not offer a
panel leaves its number unused rather than renumbering the rest. Panels 5
and 9 keep the numbers they had.

| # | Panel | Opens with |
|---|---|---|
| 1 | Raw signal (in the pair, both muscles, an axis each) | every practical |
| 2 | Normalised envelope | one muscle, kinematics; never in the pair |
| 3 | PSD with MNF/MDF | every practical |
| 4 | Filtered + rectified | «More panels…» |
| 5 | Envelope vs RMS (the «RMS envelope» curve) | «More panels…» |
| 6 | RMS per window | «More panels…» |
| 7 | MDF vs time (fatigue) | pair; elsewhere «More panels…» |
| 8 | RMS vs MDF (a path through time) | «More panels…» |
| 9 | Overlaid envelopes (agonist/antagonist) | pair |
| 10 | EMG vs MMG | kinematics |
| 11 | Tremor | kinematics |
| 12 | Movement vs EMG | kinematics |

## What the example recordings give

Nothing cited changes, and that is measured, not assumed: every figure the
example recordings give — the MVC references and task maxima of the
three-manoeuvre and pair recordings, the co-activation and contraction
tables, the tuned recording and the kinematics recording — was computed
again with this version and comes out identical, line by line, to 3.3.0's.
The panels draw what the analysis computes; none of them computes anything.

## Unchanged, on purpose

The MVC reference (the envelope's peak, best of the repetitions kept), the
150 % limit, the 5× rest-to-reference ratio, the 4.5 % co-activation floor,
the task maximum read on the recording phase, the envelope chain, the
calibration protocol, the file format, and the co-activation and
contractions boxes at the foot of the tab.

## Meta

- Bumped to 3.4.0 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- New `tests/test_panel_bruto.py`, `tests/test_panel_rms.py` and
  `tests/test_paneles_titulos.py`. **1121 automated tests.**
- The version-specific Zenodo DOI is to be minted at release.
