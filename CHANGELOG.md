- **The event log says when a channel never left its baseline.** A muscle that stayed silent is a finding worth naming rather than leaving the reader to infer it from a flat line. Decided with the application's own onset detector, so "a contraction happened" means one thing throughout.
- **The amplitude arrows in the MVC tab scale the trace instead of moving it.** The ▲▼ sidebar held the *midpoint* of the view fixed, and panels 2 and 3 carry non-negative signals drawn from zero — so halving the range about its midpoint lifted the floor off zero and slid the trace upwards rather than making it taller. It now anchors on zero, which is what the analysis tab had always done; a view that does not straddle zero keeps its own centre, since there is no baseline to hold.
- **A recording is judged against its reference by the same measure the reference was made with.** The MVC reference is the strongest 0.5 s the subject actually held, so comparing an *instantaneous* envelope against it inflates the ratio for free: on the second bench recording that difference alone turned an honest 234 % into an alarming 384 %. The implausible-reference warning now smooths the same way before judging, and the window itself moved into `SignalProfile` so the acquisition, the analysis and the rehearsal cannot drift apart on what "the strongest sustained window" means.
- **"Best of 3" is offered in every practical, and a weak calibration ends on the panel.** Repeating the maximum and keeping the strongest is not a refinement — it is how a maximum is measured: the first maximal effort of a session is genuinely submaximal, and one attempt has nothing to fall back on when it goes wrong. It had been behind the advanced flag, so the agonist/antagonist practical — the one that needs *two* good references — could not reach it at all. The third bench session showed both halves of why it matters: with a warm-up and a resistance the flexor reference reached **38 times its resting level**, and the recording's strongest half-second came to 111 % of it, which is what a correct MVC looks like; the extensor, in the same session, landed **below its own resting level**. The warning that said so went only to the event log, which scrolls, so it now ends the wizard on the cue panel — the one thing nobody must scroll past, because a bad reference makes every later percentage wrong by the same factor.
- **A maximum has to be made against a resistance, and the wizard now says so.** The bench session found that the contraction after calibration always exceeded the calibration itself, with every set-up — and the explanation is the force-velocity relationship the application teaches in another practical. With nothing to push against, the muscle shortens at its fastest and therefore develops its least force, so it recruits few motor units: a maximum performed in mid-air is **submaximal by construction**, and every later percentage comes out too high in the same proportion. The countdown now reads "push as hard as you can — against a fixed resistance, without letting the joint move", the MVC tab's entry panel explains why, and the forearm guide says how to resist each channel. An immediate check for the bench: after calibrating, ask for any strong contraction — if the live load bar passes 100 %, the calibration was not maximal.
- **Accepting "use this recording itself" now does it.** Reported from the bench as "I tell it yes and it does not do it": the answer was recorded but the result stayed behind a second press of Compute, and the load distribution was withheld altogether. Agreeing to a known-imperfect option is a decision, not a request for another dialogue, so it computes straight away. And the **distribution of effort is now drawn** — it is a fair description of how a recording's time is spread across effort levels, which is the shape the offer promises — while the Jonsson limits stay off it, since a self-normalised signal exceeds them by construction. The axis says "% of this recording's own maximum".
- **Trimming a recording is offered in every practical.** Keeping the part that came out well is hygiene, not a fine adjustment: a first attempt in a teaching laboratory arrives with a movement artefact, a loose electrode or a false start more often than not. The numeric "from"/"to" boxes stay advanced — they ask for two figures the student does not have — but the editor, which shows the recording and lets them point at what to keep, no longer hides behind the free analysis.
- **The application now notices when a "maximum" was not a maximum, and when a recording has no baseline.** Both came out of the first real forearm session, and neither was an error in the maths: the guided calibration recorded faithfully what the subject did, and what the subject did was contract at about a tenth of their true maximum. The reference stored was 0.027 mV against an envelope that later reached 0.405 mV in the same recording, so the analysis reported a peak of **1509 % MVC** and spent 29 % of its time above 100 %, the live load bars sat in the red from the first contraction, and the co-activation index was computed on numbers wrong by a factor of fifteen. Nothing said so.

  Two checks, one at each end. **At the bench**, the wizard now records the muscle's resting level during its own countdown — which is rest by construction and costs nothing — and warns when the captured reference is less than `mvc_min_rest_ratio` times it: the application cannot know whether someone pushed, but it can compare what it captured against the same muscle doing nothing three seconds earlier. **At analysis**, a reference that was never a maximum shows up as a recording spending much of its time above 100 % MVC; that is reported in the log with the real figures and printed on the panel itself, so a file already on disk is diagnosed when it is opened.

  The same session exposed a message that was simply **false**: a channel with no detected onsets was reported as never leaving its baseline, when in fact the recording had begun with the muscle still letting go, so the opening second held the transition rather than rest and the threshold came out at 0.0804 mV on a recording whose maximum was 0.0707. "The muscle stayed silent" and "the recording has no rest to measure" look identical to the detector but only one is a statement about the subject. They are now told apart, and the second says to record a couple of quiet seconds first.

- **Automatic onset markers no longer open co-activation windows.** With auto-onset on, every burst writes a marker; the table grew one row per burst — seventeen in a 56-second recording — and each row read as a measured condition. Automatic onsets are events the program found; phases are what the operator declared with MARK. Both languages' labels carry "(auto)", which is what the exclusion keys on.
- **Agonist/antagonist co-activation, by the Falconer-Winter index.** Of all the activity recorded in the pair, what fraction is exerted by both at once — from 0 to 100 %. New Qt-free `emgteach.coactivation`, sibling of `apda.py`, computing it from the two envelopes in % MVC of **their own** muscle, which is why it had to wait for the reference to start travelling in the file. Presented as a table under the panels and in the PDF, with **the two mean activations always beside the index, never the index alone**: a bare 86 % reads as "both muscles worked hard" when it may equally mean "both were equally quiet", and in this practical the antagonist's mean *is* the finding.

  The index measures similarity of *shape*, not amount of activation, so it has a silent failure of the same family as auto-normalisation: two muscles at rest have similar baseline noise and the raw formula returns **over 85 %** on a recording where nothing happened. Three safeguards, each with a test that states the danger rather than assuming it: each envelope's resting level is subtracted first (which on its own only brings that 85 % down to about 50); below `coact_floor_pct` mean activation in *either* channel the index is **not reported at all** — a reason in words, never a greyed or parenthesised number; and it is computed **per marked phase**, since one figure spanning rest, flexion and grip measures nothing, with a visible warning when a recording has no phase markers. On the forearm protocol that gives 16 % for the flexion, 12 % for the extension and **95 % for the grip** — and the two "not reported" rows are part of the demonstration, not a defect of it. `coact_floor_pct` defaults to 5 % MVC and is **an estimate, not a measurement**: it needs checking against a real forearm baseline.

  Also fixed on the way: the MVC-reference annotations were being read as phases, opening a window of their own in the table and drawing a marker line across every panel. They are facts about the session, not phases of it, and are dropped once read — as are the force-velocity loads.
- **The MVC reference now travels inside the recording, and the agonist/antagonist panel speaks % MVC.** It is the one panel that puts two *different* muscles on a single axis, and it did so in millivolts — where millivolts mean nothing, since surface amplitude depends on the skin and fat between muscle and electrode, so a biceps can sit above a triceps by anatomy rather than by activation. The application teaches exactly this in the MVC tab's entry panel and then contradicted it in the figure the student copies into their report. It could not do better, because the reference lived only in memory: it died with the session, and the offline analysis starts from the file. It is now written into the EDF as an annotation (`MVC ref ch=1 value=0.4213 mV`) and read back in analysis — the same device the guided force-velocity wizard already used for its loads, and the same design rule, that the file carries the raw signal plus the facts of the session. References calibrated **before** recording started are dumped as the recording opens, which is the order the MVC wizard itself encourages. With a reference for both muscles the panel draws them in % MVC; with one or none it stays in millivolts and **says so in the figure**, not in a tooltip, because the figure travels alone inside the PDF. Units are never mixed on the one axis. The same rule and the same warning in the PDF report, decided once in `mvc.overlay_curves()` so screen and report cannot disagree. New `mvc_ref_marker()` / `parse_mvc_ref_markers()`; `tests/test_units.py` covers the round trip and all five cases.
# Changelog

All notable changes to **emgteach** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Work on branch `feat/ui-levels`, not yet exercised against hardware. See
[`docs/NOVEDADES-rama-feat-ui-levels.md`](docs/NOVEDADES-rama-feat-ui-levels.md)
for the user-facing summary the manuals are written from.

### Added
- **The application is configured by choosing the practical, not by setting controls.** Three recording modes — **single-muscle contraction** (1 channel), **agonist/antagonist contraction** (2 channels) and **muscle kinematics** (1 channel + accelerometer) — are selected from a combo box in the window's top-right corner, applied without restarting. The mode *drives* what is recorded rather than filtering the view of it: it fixes the channel count and whether the accelerometer is used, and every tab offers only the measurements that suit that practical. The channel-count selector and the accelerometer checkbox are therefore **gone from the interface**, since they could only ever contradict the chosen mode — hiding the selector while leaving the count alone was a real defect, letting a two-muscle set-up survive into a screen that could neither show nor change it. Orthogonal to the mode, an **"Advanced options"** tick reveals the fine controls shared by all three (filter cut-offs, region of interest, fatigue thresholds, onset detection). Two rules that fell out of testing: what a mode hides it also **unticks**, restoring the selection on the way back, because a panel left ticked would still be drawn with no visible way to turn it off; and a feature that is **already running is never hidden**, since an automatic marker nobody can stop is worse than one extra widget. The connection box is revealed regardless of the flag while no device is saved, so a fresh install can still connect. Opening a single-channel recording in the agonist/antagonist mode now **warns and names the mode that fits the file** instead of silently behaving as a one-channel analysis. New `emgteach.modes` module; `tests/test_gui_modes.py` (29 cases).
- **Guided tour over the interface itself.** A walkthrough that pins each explanation to the control it describes, dimming the rest of the window and ringing the target, and changing tabs on its own. It carries the teaching layer the modes do not: what every control *measures*, and the physiology behind it. **The tour follows the mode** — 14 steps for a single muscle, 15 for agonist/antagonist, 17 for kinematics — explaining the accelerometer only in the practical that uses it and agonist/antagonist coordination only in its own. Offered at start-up with an **"Offer this guide next time"** tick box on by default, rather than shown once: a teaching machine sees a different student most sessions, so the decision to turn it off belongs to whoever owns the machine. A **"Guide"** button reopens it at any time, and it refuses to start while a recording is running. New `CoachMark` widget and `emgteach.gui.tour`; `tests/test_gui_tour.py` (15 cases).
- **Entry panel in the MVC tab**, once per session, explaining what a maximum voluntary contraction is and why a reference recording is needed. The abbreviation appeared in the tab title, in two file pickers, on the compute button and on the plot axes, and was never expanded anywhere.
- **The MVC tab gets its own event log.** The shared `LoggerWidget` can only live in one layout, which was the analysis tab's, so everything this tab logged was written where it could not be seen — including the flat-channel (disconnected electrode) and saturated-channel (bad contact) warnings, which are the most common mistake a student makes.
- **A rehearsal of the guided force-velocity acquisition.** The longest procedure in the application runs on a timer with a subject already holding a weight, which is a bad moment to discover what comes next. **"Rehearse"**, beside the guided button and deliberately never disabled — you rehearse *before* connecting anything — plays the whole protocol with no hardware and no subject: the real plan dialog, then the real cue panel showing the same prompts in the same order over a synthetic recording, with the event log filling as the application would fill it, and ending in the **real force-velocity study** opened on the rehearsal's own EDF. Each step is narrated with what is happening and, more usefully, *why* — why the maximum comes first and unloaded, why it is held while the loaded lifts are quick, what the marker written at the "Lift!" cue is for. It can be paused, stepped and replayed at ×1 to ×10, which the real procedure cannot. Almost nothing in it is a mock-up: the plan dialog, the cue panel, the log wording and the study are the application's own, and the synthetic subject is fed through the real analysis pipeline rather than having idealised curves drawn for it — so the curves at the end are the study's output, not a picture of what it should produce. The synthetic subject obeys Hill (heavier loads move slower) and Henneman (heavier loads recruit more), so the power curve peaks at an intermediate load as it should. New `emgteach.fv_rehearsal` and `ForceVelocityRehearsalDialog`, plus a tour step; `tests/test_fv_rehearsal.py` (19 cases) and `tests/test_gui_fv_rehearsal.py` (19 cases). The load-bearing test drives the **real** state machine and compares its order and timing to the script the rehearsal plays: a rehearsal that quietly teaches last year's procedure is worse than no rehearsal.
- **An i18n test that walks the source for `tr()` literals** and fails on any without a catalogue entry, ported from ecgteach. Every "this bit is still in English" over the past few days was a key the catalogue did not have, or did not have under the exact spelling the source uses; this catches the next one in a second. A companion test closes the other half of the same hole: it walks the source for strings written **straight into a widget** — a `QLabel("…")`, a `setToolTip("…")` — that never reached `tr()` at all. Those are never reported as a missing key; they simply come out in English in both languages, and the only way they used to get noticed was somebody reading the Spanish interface and spotting a word. The strings that are untranslated on purpose ("Español" in the language picker, product names, «EMG») are listed one by one with their reason rather than pattern-matched away, so a new arrival has to be looked at.

### Changed
- **The classroom broadcast is offered at every level.** Following the recording on their own phones is what the practical is for, not a fine adjustment: a teaching laboratory usually has one sensor between the whole group, and this is what turns a single recording into something they all read at the same time. The controls no longer sit behind the advanced flag, the checkbox reads **"Broadcast to phones (in the laboratory)"**, and the feature is named **"phone-following mode"** consistently — five places still called it a "classroom mode", so it had two names depending on where it was mentioned.
- **Auto-normalisation is no longer offered unless the fine controls are on**, and where it is used the result is **marked as such**: on screen, in the panel titles and in the PDF report, which is what the student hands in. The APDF chart is **not drawn at all** against an auto-normalised reference. Dividing a signal by the 95th percentile of itself makes the Jonsson limits meaningless — a sustained contraction exceeds them by construction — so the tab painted a whole recording red and it looked like a finding. The worker reports this as a flag rather than the interface inferring it from a translated string.
- **The Spanish interface settles on "usted", or the impersonal.** It addressed the user both ways, roughly half and half and sometimes inside one sentence. About fifty strings, enclitic imperatives included. The verbs were changed one at a time rather than by pattern, since most matches for a form like "marca" or "usa" are third person describing what the application does.
- **Qt's own dialog buttons are translated.** "Yes / No / OK / Cancel / Save" are drawn by Qt from its own catalogue, so a translated application that installs no `QTranslator` asked a Spanish user to press *Yes*. PySide6 ships `qtbase_es`; loading it at start-up is the whole fix.
- **The tutorial text is the author's.** Ángel's pass over the tour, applied as given, in both languages: four places said a conclusion without its reasoning, and the English had drifted from the Spanish. One physiological correction — motor units are recruited, not muscles.
- **Documentation: the BITalino backend needs no extra and no Python ceiling.** The "Hardware backends" section claimed `pip install "emgteach[bitalino]"` and Python ≤ 3.11 because of PyBluez. Neither has been true since the migration to `pyserial`: there is no such extra, and both backends run on 3.10–3.12. It appeared in seven places (README, CONTRIBUTING, packaging ×2, both manuals, both cheat sheets). `packaging/README.md` additionally claimed a MAC address *cannot* be used and a COM port is required, the opposite of what the application recommends.

### Fixed
- **BITalino: divide out the front-end gain when converting to mV.** The conversion treated the EMG channel as if the ADC read the biopotential directly, which is the voltage at the ADC input, in volts, labelled as millivolts. The ADC sees the output of a differential amplifier of gain 1009, so the transfer function has to divide by it: `EMG(mV) = (ADC / 2**10 − 0.5) · VCC · 1000 / G`. Full excursion is **±1.635 mV**, not ±1.65 mV, and recorded amplitudes were **0.90 % high**. The error stayed unnoticed because the gain is close to 1000 and a volt is 1000 mV, so the two mistakes very nearly cancelled; the Arduino backend already divided by its own gain of 200, so the two disagreed by that 0.9 % on the same signal. **Anything expressed as a ratio is unaffected** — %MVC values, the APDF load levels and the fatigue slopes are unchanged. Recordings already on disk carry their own physical range in the EDF header and are read back with it, so they keep the scale they were written with; 1.65 mV identifies an earlier recording and 1.635 mV a corrected one.
- **The flow map's text is measured and made to fit its boxes.** It was sized by eye, so several strings ran out of their box — mostly in Spanish, which is longer than English: the band title "Contracción agonista / antagonista", both force-velocity headings and the arrow labels along the spine. Every string is now measured with `get_window_extent` and shrunk until it fits. Two of the three causes were not width at all: box text is **centred vertically** rather than hanging at a fixed offset from the top, which had left the second line of the shorter branch boxes sitting on the bottom border; and the spine labels moved **above** the row of boxes, since 95 units of gap does not hold a phrase and shrinking one only makes it illegible instead of cramped. A new test draws all four practicals in both languages and fails on any string that hits the minimum body size — overflow can only be introduced by a translation, which is exactly what nobody rereads.
- **A muscle that never contracted is not drawn as if it had.** The flip side of normalising each channel to its own maximum: a channel that stayed silent has no maximum, so dividing by its largest noise peak sends baseline noise to full height and reads as co-contraction — the opposite of the finding, and exactly what a clean single-direction movement produces. The analysis worker now decides per channel whether a contraction happened, using the application's **own onset detector** rather than a threshold invented for the purpose, so "a contraction" means one thing throughout. A silent channel is drawn faint and dashed and named in the legend as baseline noise, and the event log says so. Same in the PDF report. Covered in `tests/test_units.py`, including that the guard does **not** fire on the normal alternating protocol.
- **The agonist/antagonist overlay no longer compares two muscles in millivolts.** It is the one panel that puts two *different* muscles on a single axis, and their millivolts are not comparable: the amplitude depends on where each pair of electrodes sat and how much skin and fat lay between them and the fibres — the very thing the MVC tab exists to cancel out. Read in millivolts, a thicker biceps looks like co-contraction, and the weaker muscle is squashed against the axis: on a test recording where the antagonist is a tenth of the agonist it spanned **0.040 against 0.393**, about a tenth of the plot, with its timing unreadable — and timing is what the practical actually asks about. Both curves are now drawn against **each muscle's own maximum**, the axis says "Normalised amplitude (0-1)" and the legend says "each ÷ its own maximum". The worker was already computing both normalised envelopes; nobody was using the second one. Same fix in the PDF report, and the lab guides now say what "dominates" means once the amplitudes are relative. New `tests/test_units.py` reads the axis labels off rendered figures rather than the source, so it sees what the student sees.
- **The guided tour's panel is sized to the text it has to show.** Every step was cut off, all 46 across the three modes and both languages; the two with a second paragraph showed less than half of what they said.
- **Three `tr()` calls with no catalogue entry** — "E", "A" and "Error:" — fell through to the English key. All three happen to read correctly in Spanish, which is why nobody noticed; their sibling "R" *is* translated, to "B" for Bruto, which gives the intent away. Declared now, identity included.
- **Thirty-three dead translations removed** (666 entries down to 633). Rewriting the tutorial changed the keys, and since the dictionary keys on the English string, each rewrite left its previous version behind. The set came from a reachability pass over `src`, `tests` and the dashboard HTML using the AST rather than a text search, because deleting a key that turns out to be live would silently show English in the Spanish interface. Seven orphans were kept deliberately.

## [2.0.0] — 2026-07-19

A major release adding a **kinematic dimension** to emgteach through the
BITalino accelerometer: guided force-velocity acquisition and study, a
movement-versus-EMG analysis panel, a selectable ACC channel with a live
channel diagnostic, and several accelerometer-plot and window fixes.

### Added
- **Guided force-velocity acquisition** *(branch `feat/accelerometer`)*. A **"Guided F-V…"** button in the Acquisition tab — placed under **Calibrate MVC**, with the chosen contractions and loads shown next to it (mirroring "Best of 3") — enabled as soon as a BITalino is connected with the accelerometer on (no need to be recording first, any placement). It **first asks for the list of known loads (kg)**, then, **starting the recording itself if one is not already running**, runs an overlay wizard like the MVC calibration: **an MVC maximum first (no load)** — "prepare / contract at maximum", held a few seconds — which sets the load-monitor reference, and then, for **each load and each repetition**, a **discrete quick-lift cue** (prepare countdown → a big **"Lift <kg>!"** with no hold timer or effort bar → **"Relax!"**) so it is always clear *when* and *with which load* to lift, and — because force-velocity is about *shortening velocity* — the movement is a **fast concentric lift, not an isometric hold** (a hold shows no velocity and the accelerometer barely moves). **Every lift is auto-marked in the EDF** (annotation `FV load=<kg> kg`), and the **Force-velocity study now takes its repetition windows straight from those markers** (robust to the amplitude gap between the MVC maximum and the light loads, which used to make burst auto-detection miss the loaded reps), pre-filling the load column instead of the operator typing it (a free recording still auto-detects bursts and starts blank). The loads field accepts **commas or spaces** as separators (a dot for decimals); the plan dialog warns if the accelerometer is on the muscle rather than the moving segment. There is a **longer recovery pause between the MVC maximum and the first load**. In the Force-velocity **study**, each contraction now has a **"Use" checkbox** so a clearly-invalid repetition can be excluded, and **repetitions of the same load are averaged** to one point per load; a **warning** appears when the accelerometer barely moved (flat / pinned at a rail — the case where every velocity reads 0.000). New `ForceVelocityPlanDialog`, an `action` cue in the overlay, and `emgteach.force_velocity` helpers (`fv_load_marker`, `parse_fv_load_markers`, `assign_loads_to_reps`, `windows_from_markers`).
- **Movement-vs-EMG panel** *(branch `feat/accelerometer`)*. A new Analysis panel (**"12. Movement vs EMG"**) for the **"on the moving segment"** accelerometer placement overlays a **movement trace** (kinematic envelope from the accelerometer — high-pass, integrate to velocity, rectify, smooth; arbitrary units) with the **EMG envelope**, showing that limb movement follows the contraction. It is **default-selected for the limb placement** (as EMG-vs-MMG is for the muscle placement), so the moving-segment recording now gets its own reference trace, not only the muscle placement. Also in the PDF report. New `dsp.movement_envelope`.
- **Selectable accelerometer channel + a channel diagnostic** *(branch `feat/accelerometer`)*. The accelerometer is no longer hard-wired to analogue **A4**: an **"ACC ch:"** selector (A1-A6, default A4) sets which input it is read from, because the BITalino packs the *enabled* inputs consecutively and different boards/sensors land the accelerometer on different channels (e.g. the on-board sensor on A1). A **"Find ACC channel…"** button opens a diagnostic that reads **all six analogue inputs live** and flags the one whose range grows when you tilt the sensor — one click sets the ACC channel to it. The **EMG channels automatically skip the ACC's channel** (so with the ACC on A1 the EMG lands on A2; the mapping is logged), and the device now always exposes the **accelerometer as the trailing column whatever input it is on** (the rest of the app relies on that). The live ACC plot has its own **▲▼ vertical-zoom buttons** in the sidebar (magnifying around the trace), with the sidebar slots **aligned to their plots** — previously, with the ACC plot shown, the envelope's ▲▼ drifted down next to the accelerometer and the accelerometer had none. New `BitalinoDevice(acc_channel=…)` / `read_raw`, `ChannelDiagnosticDialog`.
- **Force-velocity study** *(branch `feat/accelerometer`)*. A **"Force-velocity study…"** button in the Analysis tab (enabled when the recording has an accelerometer channel) opens a dialog that turns **one recording of several known loads lifted** into the classic muscle-function curves: **load-velocity**, normalised **force-velocity** (Hill-shaped), **power** (load × velocity) and **recruitment** (load vs EMG amplitude — the electrophysiological angle a plain force-velocity curve lacks). The repetitions are auto-detected from the EMG envelope; the user types the known load (kg) of each and redraws. Velocity is derived from the accelerometer by high-pass + integration (arbitrary units — the ACC is uncalibrated), and force is the entered external load (emgteach has no force cell; isotonic assumption). New `emgteach.force_velocity` module and `ForceVelocityDialog`.
- **Accelerometer analyses — EMG vs MMG and tremor** *(branch `feat/accelerometer`)*. When a recording has an accelerometer channel, the Analysis tab offers two new panels: **"EMG vs MMG"** overlays the electrical envelope (EMG, mV) and the mechanical envelope (MMG, computed from the accelerometer on the muscle) — the electromechanical coupling; and **"Tremor"** shows the accelerometer's frequency spectrum with the tremor peak marked (physiological ~8–12 Hz). A **placement selector** in the Acquisition tab ("on the muscle (MMG)" / "on the moving segment (tremor)") is stored in the ACC channel label so the Analysis tab pre-selects the relevant panel; both panels are locked when the file has no accelerometer. The EMG-vs-MMG panel names the paired EMG channel in its legend and notes that the MMG belongs to the muscle carrying the accelerometer; choosing the **"on the muscle (MMG)"** placement **locks acquisition to a single EMG channel** (an MMG accelerometer measures one muscle, so two channels would be ambiguous), while the "moving segment" placement — a shared joint movement — keeps two channels available. Also in the PDF report. New `dsp.mmg_envelope` / `dsp.tremor_spectrum` (the ACC is read with pyedflib to keep its `g` units, avoiding MNE's mV rescaling).
- **Channel-quality warning on load.** When an EDF is opened in the Analysis or MVC tab, each EMG channel is checked and a warning is logged if it is **flat** (no signal — a disconnected electrode or a channel declared but never wired) or **saturated** (pinned at the ADC rails — bad electrode contact or too much gain); a low-amplitude channel gets a "weak signal" note. This makes it obvious when a two-channel recording actually only has data in one channel. New `emgteach.dsp.assess_channel_quality` / `emgteach.io.assess_edf_channels`.

### Changed
- **Clearer channel selection in Analysis and MVC.** On loading an EDF the app now detects whether it has one or two **EMG** channels (the accelerometer channel is never offered): with one channel the "Compare channels" option (Analysis) and the channel picker (MVC) are disabled; with two, you pick **EMG1** or **EMG2** and every panel, the report and the whole normalisation use **only that channel**. Comparing is **off by default** and, when turned on, the partner channel is set **automatically** to the other one (pick EMG1 → partner EMG2, and vice versa); the overlaid-envelopes panel (9) can only be ticked while comparing. Default acquisition channel labels are now **EMG1 / EMG2**.

### Added
- **Accelerometer (ACC) channel — prototype** *(branch `feat/accelerometer`)*. The Acquisition tab has an **ACC** checkbox (BITalino only) that additionally records the accelerometer on analogue **A4** in its own auto-scaled plot and as a separate EDF channel (unit `g`, normalised/uncalibrated). A4 is wired for the ACC so it keeps the **same 10-bit resolution** as the EMG channels (EMG on A1/A2 at most). It is converted apart from the EMG (`BitalinoDevice(acc=True)` / `raw_to_acc`) and kept out of the EMG machinery (filtering, envelope, load monitor, MVC wizard) so it stays a plain movement/vibration trace. Foundation for movement-context, motion-artefact and MMG/tremor teaching uses.

- **Agonist/antagonist envelope overlay in Analysis.** The Analysis tab can now analyse a **second channel** at the same time: a "Compare 2nd channel" picker (enabled and ticked automatically for 2-channel recordings) adds a new panel that **overlays both channels' envelopes** — shown by default for two-channel files. The second envelope is computed over the same region/fragment selection and is also available in the PDF report.
- **Scan-to-join QR code for classroom mode.** Next to the existing "Copy link" button, a **QR** button shows a code students scan with their phone camera to open the follower page instantly — no need to email the URL. New pure-Python `segno` dependency.

### Changed
- **Post-calibration auto-scale.** Once the MVC calibration finishes, the live plots resize to the subject: the envelope top is set to a headroom multiple of the MVC reference (so >100 %MVC phasic bursts stay on screen) and the raw plot to ±(measured peak), with a margin above and below. The ▲▼ reset returns to this calibrated scale. Fixes signals going off-window for stronger or weaker individuals.
- **More representative MVC reference.** The MVC reference is now taken from the **strongest sustained window** of the calibration effort (`mvc_peak_hold`) instead of the percentile of the whole held contraction, which was diluted by the ramp-up and fatigue decay. This reduces the case where brief individual contractions overshoot 100 %MVC after calibrating with a sustained one.
- **Neutral protocol example.** The Acquisition protocol field's placeholder no longer names a specific muscle ("Isometric contraction 30 s").
- **Bilingual follower dashboard.** The classroom follower page (`web/dashboard.html`) now follows the app language — it renders in English when the app is in English (it was Spanish-only) — with the operator's language injected into the served page.
- **Docs: two live plots.** The user-manual section on the Acquisition tab now says two real-time plots (raw + envelope), matching the removal of the intermediate filtered trace.
- **About-box affiliation.** The "?" About dialog now reads "Physiology Department, Complutense University of Madrid" ("Departamento de Fisiología…" in Spanish) instead of naming the Faculty of Pharmacy.

## [1.4.1] — 2026-07-14

### Fixed
- **Packaging metadata version.** `.zenodo.json` and `CITATION.cff` still
  declared version `1.3.0` after the 1.4.0 release; both now match the
  packaged version, so the Zenodo archive and the citation record show the
  correct version and feature list.

## [1.4.0] — 2026-07-14

### Added
- **Classroom mode — students follow on their phones.** A new "Broadcast to phones" toggle in the Acquisition tab serves a read-only live dashboard over the local network: students open a URL in their phone/tablet browser (no install) and follow the session in real time — the envelope, the %MVC load bars, the guided-calibration steps and the markers. The operator PC keeps the single Bluetooth link to the BITalino (Bluetooth Classic is point-to-point) and re-broadcasts the already-computed data through Qt-native WebSocket + HTTP servers, so any number of students can watch at once. New `emgteach.broadcast` module and `web/dashboard.html` follower page; no extra runtime dependency. A `python -m emgteach.broadcast` demo mode previews the follower page with synthetic data, and the HTTP server resets TLS handshakes so a phone browser that auto-upgrades to `https://` falls back to `http://` on its own. Students can **download the live session as CSV** from the dashboard, and when the operator runs the offline analysis its **metrics and the PDF report / CSV are pushed to the followers to download** as well (the broadcast server is shared with the Analysis tab).
- **Per-session access code for the classroom broadcast.** Every time the
  broadcast is switched on, a fresh random code is minted and embedded in the
  follower URL (`?k=...`); the HTTP and WebSocket servers reject requests
  without the current code. Links shared for one practical die as soon as
  that broadcast stops — students from a past session cannot reconnect, and
  being on the same institutional network is no longer enough to watch.
- **"Copy link" button.** Next to the classroom-mode toggle, copies the full
  follower link to the clipboard so the instructor can paste it into an
  email to the students.
- **On-demand Windows build in CI.** A `Build Windows exe` workflow packages
  the standalone `emgteach.exe` (PyInstaller one-file, gated on the frozen
  `--selftest`) and, on a published GitHub release, attaches it to the
  release automatically.

### Fixed
- **Start-up crash in the v1.4 test builds** (never in a published release):
  the main window passed itself positionally into `BroadcastServer`, landing
  in the `http_port` parameter and raising `TypeError` before the window
  showed. A new GUI test constructs the real main window so start-up wiring
  regressions fail in CI instead of on launch.

## [1.3.0] — 2026-07-10

### Added
- **Guided MVC-calibration wizard.** A floating on-screen guide walks the subject through the live-MVC calibration one muscle at a time: a "get ready" countdown, a "contract at maximum" phase with a window-progress bar and a live effort bar, then a relax pause — with an optional **Best of 3** mode that repeats each muscle three times and keeps the strongest contraction. New `MvcOverlay` widget and `emgteach.mvc.mvc_from_reps` helper. (Restored from the unmerged `feat/guided-mvc-calibration` branch and ported onto the current teaching build.)

## [1.2.1] — 2026-07-10

### Changed
- **Device backend selectable again.** The BITalino (Bluetooth) / Arduino + MyoWare 2.0 (USB) selector is shown again, so both interchangeable backends can be chosen — matching the documented, published feature set. BITalino remains the default.
- **Neutral splash subtitle.** The start-up splash now reads "Surface EMG acquisition" instead of naming a single backend.

### Fixed
- **Muscle-load tooltip layout.** The APDF chart's hover tooltip now word-wraps into a compact box instead of forcing a line break after each sentence.

## [1.2.0] — 2026-07-09

### Changed
- **Teaching-focused live view.** The Acquisition tab now plots only the raw signal and the envelope; the intermediate filtered trace is no longer shown (it is still computed for the envelope, and the EDF keeps the raw channel). This drops a step that is not relevant for physiology students.
- **BITalino-only interface.** The Arduino + MyoWare backend is hidden in the device selector (its code path is unchanged), matching how the teaching lab is equipped.
- **Teaching panel selection.** The Analysis "Panels to show" now defaults to the three panels used in class — raw signal, normalised envelope and PSD — renumbered 1A / 2 / 3; the remaining panels follow as 4–8, unchecked but still selectable. The numbering is consistent on screen and in the PDF report.
- **Author credit.** The splash and About box now read "Dr. Agis-Torres et al.".
- **APDF legend key.** The muscle-load distribution chart (MVC tab and PDF report) now labels the red out-of-range ring in its legend.

### Added
- **Choose where recordings are saved.** Starting a recording opens a "Save as…" dialog to pick the EDF file name and folder (pre-filled with a timestamped default), like the figure and CSV export dialogs.
- **Choose where reports are saved.** The Analysis and MVC PDF reports are written through a "Save as…" dialog (name + folder) instead of an automatic name.
- **iEMG hint.** A short tooltip explains the integrated-EMG value in the analysis summary.
- **Didactic tooltips.** Hovering the "Panels to show" options, the envelope cut-off and each analysis-summary metric shows a one-line explanation of what it reports; the muscle-load (APDF) chart explains its physiological meaning on hover.

### Fixed
- **Complete Spanish interface.** Translated the strings that still showed in English in the Spanish UI — the fragment editor, CSV export, region-of-interest controls, the Protocol metadata field, CSV column headers, fatigue verdicts, marker deletion and the fragment "reason" labels — plus a hard-coded Spanish axis label in the PDF report.
- **Quieter console.** Suppressed a benign `QFont::setPointSize: Point size <= 0` warning emitted by pyqtgraph while drawing axis labels.

## [1.1.2] — 2026-07-05

### Added
- **Numerical metric validation.** `validation/validate_metrics.py` checks MNF/MDF against analytic ground truth and an independent reference implementation, recovers an imposed fatigue slope, and verifies the MVC and APDF percentile levels; it runs in continuous integration.

## [1.1.1] — 2026-07-04

### Fixed
- **Package version string.** `emgteach.__version__` still reported `1.0.0` in the
  1.1.0 release; it now matches the packaged version. This corrects the frozen
  build's `--selftest` banner and the PDF-report footer, both of which read from
  `__version__`.

## [1.1.0] — 2026-07-04

### Added
- **Assisted selection of significant fragments.** A new `selection` core
  module and a `fragment_selection` GUI widget detect and let the user curate
  the significant EMG fragments of a recording, with **editable detection
  parameters** and **editable envelope-filter cut-offs** that are then applied
  to the analysis.
- **Region-of-interest (ROI) windowing** for offline analysis.
- **CSV export of analysis results** (new Qt-free `emgteach.exports` module).
- **Live signal-quality check** during acquisition.
- **ECG signal profile and a profile registry.** A second `SignalProfile` (ECG)
  alongside `EMG_PROFILE`, selectable through a registry — extending the
  biopotential extension point to a new modality.
- **Editable marker list** with delete-before-save on the acquisition tab.
- **Student / protocol metadata** written into the EDF+ header.
- **Cancel button** for long analysis and MVC runs.

### Changed
- **Linear MDF-vs-time regression** is now the primary fatigue index.
- **Deep notch comb** that removes the mains fundamental and its harmonics.

### Fixed
- **Device-aware EDF physical range** so Arduino + MyoWare signals (5 V) are no
  longer clipped.

### Internal
- Test suite grows to **216** passing tests on Python 3.10–3.12; `ruff` clean.

## [1.0.0] — 2026-06-28

### Added
- **Standalone Windows executable (PyInstaller).** A reproducible packaging
  recipe under `packaging/` (`emgteach.spec` + `run_emgteach.py`) builds a
  single windowed `dist/emgteach.exe` (~132 MB) that runs on any Windows 10/11
  PC with no Python install — for the critical-testing phase. The frozen entry
  point has a headless `--selftest` mode (imports the full runtime, builds the
  window off-screen, writes the outcome to `emgteach_selftest.log`) used to
  validate the binary after each build. Both hardware backends talk over
  `pyserial` (the BITalino over its **Windows Bluetooth virtual COM port**); no
  PyBluez or external `bitalino` package is bundled. Build artefacts stay
  git-ignored; see `packaging/README.md`.

### Changed
- **BITalino backend rewritten on `pyserial` (no PyBluez, no `bleak`, no
  external `bitalino`).** `BitalinoDevice` now opens the Windows Bluetooth
  **virtual COM port** and speaks the BITalino wire protocol directly (version,
  set sampling rate, start live mode, CRC-checked frame decode, stop→idle). The
  `(r)evolution` is Bluetooth **Classic** (SPP), so `bleak` (BLE-only) cannot
  reach it; the COM-port path over `pyserial` does, and freezes/imports on every
  supported Python including 3.13/3.14. The public `AcquisitionDevice` API and
  the watchdog (`force_close`) contract are unchanged. The `[bitalino]` optional
  extra is removed. See ADR 2026-06-28.
- **MAC stays the stable, zero-config address.** The device field accepts a
  **MAC** (default `98:D3:91:FE:44:E4` — resolved to the local COM port via the
  port `hwid`, identical on every PC), an explicit **`COMx`**, or **empty** to
  **autodetect** the BITalino by handshake. A MAC that is not paired, or a
  failed autodetect, raises an actionable bilingual message. The serial open
  retries with a short backoff to absorb the Bluetooth SPP port-release lag
  (`WinError 1168`). Persistence key `adquisicion/mac` → `adquisicion/port`.

### Removed
- **`bitalino` optional dependency / extra.** The protocol is now implemented
  in-tree over `pyserial`, so `pip install "emgteach[bitalino]"` is gone and no
  external Bluetooth library is required.

## [0.3.0] — 2026-06-13

### Added
- **Bilingual interface (English / Spanish).** A lightweight `tr()` layer
  (`emgteach.i18n`) with English-canonical source strings and a Spanish
  translation map (~210 entries). The start-up language is detected from the
  system locale (Spanish → `es`, otherwise `en`) and can be switched
  (English / Español) from the tab-bar corner; the choice is stored in
  `QSettings` and applied on the next launch.
- **Stacked two-channel live view.** With two channels, the raw and filtered
  acquisition plots stack into one vertical lane per channel (instead of
  overlapping on a shared zero), with per-lane reference ticks, a coloured
  zero baseline and the muscle label drawn in each lane. The envelope stays
  overlaid (non-negative → directly comparable). Single-channel behaviour is
  unchanged.
- **Per-channel vertical zoom** (▲ / ▼) that scales an independent gain per
  channel in stacked mode, leaving the lane positions fixed.
- **Report graph picker.** Generating a PDF report now opens a dialog to choose
  which analysis panels are rendered into the document; each selected panel is
  drawn as its own graph (`build_session_report(..., panels=...)`).
- **Live muscle-load monitor (online APDA).** During acquisition, a quick MVC
  calibration (a few seconds of maximum contraction) enables a per-channel load
  bar with tiredness (warning) and fatigue (danger) zones plus the running
  static / median / peak levels, computed GUI-side from the streamed envelope.
  New `OnlineLoad` in `emgteach.apda` and a `LoadBar` widget; the zone
  thresholds and calibration duration live in `SignalProfile`.
- **Muscle-load analysis (Jonsson APDF).** The MVC tab now computes the
  Amplitude Probability Distribution Function of the % MVC envelope and reports
  the **static** (P10), **median** (P50) and **peak** (P90) load levels against
  configurable recommended limits, with a dedicated distribution panel and a
  colour-coded summary. New Qt-free `emgteach.apda` module
  (`compute_apdf`); limits live in `SignalProfile`.
- **MVC / muscle-load PDF report.** A one-click "Generate PDF report" button
  in the MVC tab writes a report (panels + APDF + a metrics table with the
  load levels vs limits) next to the source EDF (`build_mvc_report`).
- **New-session reset.** A "New session" button in the tab-bar corner clears
  all three tabs back to their just-opened state — the live view, markers,
  local log and MVC calibration, plus the loaded analysis/MVC files, results
  and student name·code — so you can switch students without restarting the
  app. The EDF files already saved on disk are not deleted; the button is
  disabled while recording.
- **Adjustable live-load thresholds.** The warning and danger zone limits
  (% MVC) of the live muscle-load monitor can be tuned from the acquisition tab
  once an MVC is calibrated; the values are remembered across sessions.
- **Teaching documentation (bilingual).** A full doc set under `docs/` in
  English and Spanish — user manual, 5-practical lab guide, evaluation rubric
  and a one-page cheat sheet — plus `tools/md2pdf.py`, a small generator that
  renders the Markdown sources to PDF using only existing dependencies
  (`reportlab` + matplotlib's DejaVu fonts; no pandoc/LaTeX).

### Changed
- **Compact, themed GUI.** The acquisition tab was reorganised into two compact
  rows. A centralised application stylesheet (`_APP_STYLESHEET` in
  `gui/app.py`) gives all three tabs a consistent steel-blue look with white
  plot areas. The author attribution moved from a permanent status bar to an
  "About" (?) button in the tab-bar corner, freeing vertical space for the
  plots.
- **Analysis / MVC polish.** The Analysis tab gained mouse-wheel zoom over the
  panels, alongside a time-window minimap navigator with a smoother
  move/resize drag — a narrow selection now always pans instead of accidentally
  resizing, and the resize handles are capped and shown as edge grips. The
  drawn window defaults to the whole recording. Typography was unified across
  the MVC tab.
- **MVC tab redesign.** The muscle-load APDF moved to its own chart with a
  structured data panel beside it (replacing the old summary box); the
  display-window navigator was made Analysis-style (bottom minimap bar +
  compact controls, no title, no reset button); the visualisation area now
  scrolls vertically.
- **Report time range.** PDF reports now plot a chosen time range instead of
  always the whole recording (unreadable for long sessions): the Analysis
  graph-picker dialog gained editable start/duration fields pre-filled with the
  on-screen window, and the MVC report gained the same range dialog.
- **Muscle-load readout polish.** The APDF marks each level
  (static / median / peak) in its own colour, with a red ring when out of
  range; the data panel shows each value (red if out of range) with its normal
  range and a short explanation (mean activation included). The MVC report no
  longer overlaps panel titles and puts the metrics on a second page.

### Fixed
- A few user-facing strings (the analysis progress bar, the fatigue-summary
  verdicts, the MVC-source fallback label and the vertical-zoom sidebar
  letters) bypassed the translation layer and stayed in Spanish in English
  mode; they now follow the selected language.

### Internal
- Test suite grows to 126 passing tests on Python 3.10–3.12.
- The developer layer (code comments and docstrings) is now fully English.

## [0.2.0] — 2026-06-11

### Added
- **Two-channel acquisition** (e.g. agonist / antagonist) with an editable
  label per channel; the data layer is generic over N channels. EDF stores
  raw-only, one channel per sensor (filtered / envelope are recomputed on
  analysis).
- **Automatic contraction-onset detection** (`dsp.OnsetDetector`): baseline
  mean + k·SD threshold with a min-duration debounce and refractory period,
  stored as EDF+ annotations. An enable checkbox and sensitivity (k) control
  were added to the acquisition tab.
- **One-click PDF session reports** (`emgteach.reports`, reportlab +
  matplotlib-Agg, Qt-free): header, signal plot with annotations, metrics
  table (RMS / MNF / MDF / fatigue / IEMG / duration), configuration used and
  a reproducible footer (version + git commit + timestamp).
- **Open-source Arduino firmware** (`firmware/emgteach_arduino/`, 1–2 channels,
  configurable `N_CHANNELS`) shipped in the sdist.
- Mouse-wheel zoom on the Analysis / MVC plots; live event markers drawn on the
  acquisition plots.

### Changed
- **Architectural refactor (non-breaking).** Two extension points were added:
  `SignalProfile` (`profiles.py`, with `EMG_PROFILE`) for new biopotential
  modalities, and a device factory (`devices/factory.py`,
  `create_device` / `register_device`) for new hardware backends. Workers now
  read their defaults from the active profile.

### Deprecated
- Legacy EDF helpers `create_edf_writer` and `write_edf_block`, superseded by
  `BufferedEdfWriter`. Kept for backward compatibility, not removed.

## [0.1.0] — 2026-05-10

### Added
- First public release. A Qt-free analytic core (`io`, `dsp`, `fatigue`,
  `mvc`, `devices`) and a three-tab PySide6 GUI (Acquisition, Analysis, MVC
  normalisation).
- Two interchangeable hardware backends behind a common `AcquisitionDevice`
  interface: **BITalino (revolution)** over Bluetooth and an **Arduino
  RedBoard Plus + MyoWare 2.0** over USB serial.
- **EDF+ output** with the buffered-write pattern that avoids the silent
  corruption artefact characterised in Agis-Torres (2026).
- Reproducible synthetic signals for class assignments and hardware-free CI.
- A BITalino watchdog that releases blocked Bluetooth reads in ~50 ms after
  disconnection.

[Unreleased]: https://github.com/aagisto-maker/emgteach/compare/v1.4.1...HEAD
[1.4.1]: https://github.com/aagisto-maker/emgteach/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/aagisto-maker/emgteach/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/aagisto-maker/emgteach/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/aagisto-maker/emgteach/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/aagisto-maker/emgteach/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/aagisto-maker/emgteach/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/aagisto-maker/emgteach/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/aagisto-maker/emgteach/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/aagisto-maker/emgteach/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/aagisto-maker/emgteach/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/aagisto-maker/emgteach/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aagisto-maker/emgteach/releases/tag/v0.1.0
