# emgteach 3.2.0 — the MVC reference is the envelope's peak

A minor version, not a patch, because it changes the numbers the program
produces for the same signal: **a recording reanalysed with 3.2.0 gives % MVC
figures different from those of 3.1.2**, for the reasons below. Nothing about
the acquisition, the file format or the envelope changes.

## Changed

- **The MVC reference is the envelope's peak.** Each calibration repetition
  was worth the highest 0.2 s running mean of its envelope; it is now worth
  the highest point the envelope reaches, and the reference is still the best
  of the repetitions kept. The MVC is the top of the scale, the largest
  contraction the muscle can be expected to make, so what stands for it is a
  maximum and not the mean of a stretch that takes in the rise and the fall of
  the peak. What keeps a noise sample from setting it is the envelope's own
  5 Hz low-pass, which leaves a one-sample spike at 1000 Hz at 1/90 of its
  height. Everything judged against the reference is measured the same way:
  the task maximum, each contraction's peak, the per-repetition values and
  cross-talk, and the live bars' reference. On the bench recordings the peak
  is 1.16 times the running mean (80 channels, 1.02 to 1.50), and a task
  maximum moves by +3 points on average (median +1.5, from −37 to +78): what
  the reference gains, the task gains too, because the same statistic is
  applied to both. The 19 channels whose task maximum lay between 90 and
  125 % with the old reference lie between 91 and 125 % with the new one.
- **The co-activation floor is 4.5 % MVC.** The index is not reported when
  either muscle's mean activation above rest in the window is under the
  floor. The floor is a level of activation above rest expressed as a share
  of the reference; it was 5 % of the 0.2 s running mean, and the same level
  is 4.3 % of the new reference on average, so it is set at 4.5 %, the nearest
  half point. With it, 33 of 34 whole-recording windows of the bench
  recordings and the three manoeuvres of the example recording keep the
  reported / not-reported state they had. The reason in the table writes the
  floor with its decimal, the chart draws it from the profile, and the help
  of the co-activation box says when the index is not reported.
- **Each fatigue segment's MDF is computed over the analysis band**
  (20–450 Hz), as the summary's MDF and each contraction's already were. The
  segments took the median of the whole spectrum, 0 Hz to half the sampling
  rate. On the example recordings a segment's MDF moves by 0.4 Hz on average,
  in no consistent direction; of 52 stretches, one fatigue verdict changes,
  from inconclusive to no fatigue, on a fit whose R² crosses the 0.30
  threshold from 0.295 to 0.301.
- **The agonist/antagonist task's flexions and extensions are made freely,
  with no resistance** (documentation): if the wrist pushes against
  something, the antagonist comes in to stabilise it and the reciprocal
  pattern is blurred. Only the grip is made against something.

## What the example recordings give now

Measured with the application, before → after.

| Recording | Muscle | Reference (mV) | Task maximum |
|---|---|---|---|
| Three manoeuvres | flexor | 0.1468 → 0.1870 | 73.3 → 68.4 % |
| Three manoeuvres | extensor | 0.3558 → 0.4226 | 40.7 → 41.2 % |
| Pair | flexor | 0.2175 → 0.2705 | 109.3 → 100.5 % |
| Pair | extensor | 0.1734 → 0.1967 | 74.9 → 81.5 % |

Co-activation by manoeuvre on the three-manoeuvre recording (index; flexor /
extensor means, % MVC): flexion 28.3; 14.1 / 5.8 → 29.4; 11.1 / 4.9;
extension not reported; 4.2 / 6.2 → not reported; 3.3 / 5.2; grip 75.7;
14.5 / 9.1 → 78.6; 11.4 / 7.7.

## Unchanged, on purpose

The 150 % limit past which a reference is called implausible, the 5×
rest-to-reference ratio, the envelope chain (notch, 20–450 Hz band-pass,
rectification, 5 Hz low-pass), the calibration protocol and the file format.

## Meta

- Bumped to 3.2.0 (`pyproject.toml`, `__init__`, `.zenodo.json`,
  `CITATION.cff`).
- **1081 automated tests.**
- The version-specific Zenodo DOI is to be minted at release.
