# Surface-EMG lab practicals with emgteach

> **Course:** Physiology (teaching laboratory).
> **Software:** emgteach (branch `feat/ui-levels`, September 2026).
> **Hardware:** BITalino with surface electrodes; the single-muscle practical
> also runs on an Arduino with a MyoWare 2.0 sensor.
>
> This guide has **three practicals**, one for each practical the application
> offers in its selector. Each holds several **exercises**, each with what is
> done, what the application computes on its own, what to write down and what
> to reason about. Instructors pick the exercises that fit the time; each stands
> on its own.

---

## How this is organised, and why

The application is configured **by choosing the practical**, not by setting
controls. The drop-down in the top-right corner has three options, and from that
choice follow the channel count, the accelerometer, what the recording asks for
and which panels the analysis offers. The coloured band beside it names the
level.

| Practical in this guide | Selector option | Level | Channels | What is learnt |
|---|---|---|---|---|
| 1 | **Single-muscle contraction** | basic (green) | 1 | from the signal to the number: amplitude, spectrum, fatigue, load |
| 2 | **Agonist / antagonist contraction** | intermediate (amber) | 2 | comparing two muscles in % MVC; co-activation |
| 3 | **Muscle kinematics** | advanced (purple) | 1 + accelerometer | force-velocity, electromechanical delay, tremor |

The window's three tabs are always the same: **Acquisition** (record), **Analysis**
(read a recording) and **MVC normalisation** (express the task as a share of the
maximum and measure the load). What changes with the practical is what each tab
shows.

---

## General objectives

By the end, students should be able to:

1. Place the electrodes and obtain a clean surface-EMG signal, and tell a good
   signal from a spoiled one on the screen.
2. Explain the processing chain (filtering, rectification, envelope) and which
   question each measure answers: RMS and iEMG (how much the muscle activates),
   MNF and MDF (at which frequencies), % MVC (how much, relative to its own
   maximum).
3. Calibrate a **maximum voluntary contraction** that really is maximal, and
   recognise in the analysis when it was not.
4. Read the **contraction table** and the **summary cards** against the reference
   ranges, and say what is usual and what is a question.
5. Detect **fatigue** from the spectral shift, and tell «not detected» from «not
   conclusive».
6. Compare an **agonist and its antagonist** in % MVC and measure their
   **co-activation**.
7. Assess the **muscle load** of a task with Jonsson's method.
8. In the advanced practical, obtain a muscle's **force-velocity relationship**,
   measure its **electromechanical delay** and see **physiological tremor**.

---

## Safety and hygiene

- **Very low-voltage** equipment, battery or USB powered; no electrical risk to
  the subject.
- **Disposable** electrodes, one set per person; clean the skin with alcohol and
  let it dry. Do not reuse electrodes between subjects.
- Subjects with skin lesions in the area should abstain.
- Maximal efforts are brief (four seconds) and are made against the table, never
  against another person. Anyone who feels joint pain stops.

---

## Before starting (common to the three practicals)

### 0 · Choose the practical

In the drop-down in the top-right corner, before anything else. The application
remembers the last choice; check it every session. The quick guide (**«Guide»**
button) walks through what follows in five steps, and every box of the
application has a **«?»** in its corner explaining what it does.

### 1 · Place the electrodes

General rule: two active electrodes over the **muscle belly**, aligned with the
fibres and **2 cm apart centre to centre**; the reference over **bone** (olecranon
or ulnar styloid). Clean, dry skin, no cream. If the signal comes out small, move
the pair one or two centimetres towards the tendon.

The pair this guide uses in practicals 1 and 2 is the forearm pair: **flexor carpi
radialis** (FCR, anterior side) and **extensor carpi radialis** (ECR, posterior
side). Exactly where, with which palpation check and which mistake is easy to
make, is in [`colocacion_electrodos_antebrazo_es.md`](colocacion_electrodos_antebrazo_es.md)
(Spanish). Practical 3 uses the biceps brachii, with the accelerometer on the
wrist.

### 2 · Connect

**Acquisition** tab, **Device configuration** box:

- In the single-muscle practical the device is chosen (BITalino over Bluetooth or
  Arduino + MyoWare over USB). In the other two the box reads **«Device:
  BITalino»** with no drop-down, because they need two channels or the
  accelerometer, which only the BITalino has. In every case the address (MAC or
  port) can be changed; the BITalino is best identified by its **MAC**, which is
  the same on every computer.
- **Output path and file**: the folder the EDF will be saved to.
- **Labels**: each muscle's name, in the order of the board's channels (**Muscle
  1 is the one recorded on A1**). In the pair, the boxes start empty with a hint
  («Agonist, e.g. FCR»). What is typed here is what the lanes, the tables and the
  report will say.
- **Test identifier**: a student, a pair, a bench or an attempt; it goes into the
  EDF header and the report.
- Press **Connect**. The indicator turns yellow (connected) and green when data
  arrives.

### 3 · Test the signal before recording

With the connection made, ask for a brief contraction and watch the two plots:
the raw signal should burst into symmetric spikes and the envelope rise and
return to baseline. At rest the baseline is almost flat. The event log warns of
two frequent faults: a **flat channel** (electrode loose or not connected) and
**saturation** (poor contact, or an electrode over the tendon).

### 4 · How a recording with calibration runs

Measurements in **% MVC** need to know that muscle's maximum in that session. The
application asks for it with a wizard that writes everything into the same file,
without stopping the recording:

1. **Warm-up (10 s).** Two or three easy contractions of each muscle. The first
   maximal contraction of a session is never the strongest one, and this corrects
   that in part.
2. **Three sustained maximal contractions**, 4 s each, with a 3 s countdown and
   2 s of rest between them. The screen says «Contract FCR at maximum!».
3. **Three brief maximal squeezes**, 1.5 s each. The screen says «Make a single,
   brief muscle contraction (a twitch) with the greatest force you can».
4. With two muscles, the same for the second one.
5. In the pair practical a 5 s **preparation** follows and the **recording** of
   the task begins. In the other two practicals the calibration is launched with
   the **«Calibrate MVC»** button while recording, and the recording goes on.

The reference is **the best 0.2 s across the six repetitions**. Why six, and why
squeezes? Because a sustained contraction shows a peak at its start and then a
plateau, and a task's brief efforts reach that peak. Measured on the plateau, the
reference fell short and the task beat it: 135 % of "maximum" on the bench of 1
September.

> **The manoeuvre of the maximum decides the practical.** Checked at the bench on 3
> September with four consecutive recordings:
>
> - **Against something that does not give.** The underside of the table edge,
>   not a hand. Forearm fully rested. Without resistance the muscle shortens at
>   its fastest and, by the force-velocity relationship, gives its least force: a
>   "maximum" in mid-air is submaximal by construction.
> - **Flexor (FCR): fist closed**, palm up under the table edge, wrist about 20° in
>   extension, pushing upwards. With the hand open the reference came out at half
>   of what the task produced afterwards (178 %); with the fist closed the task
>   ended at 109 %.
> - **Extensor (ECR): back of the hand** against the table top, forearm pronated,
>   wrist about 20° in flexion, fingers relaxed.
> - **Hold the four seconds.** If the envelope spikes and drops, the repetition is
>   no good; the application lets you discard it afterwards.
> - **Immediate check:** when the task is over, the analysis summary states the
>   **task maximum** in % MVC. Above 150 % it is flagged in red, «not a maximum»,
>   and the calibration has to be repeated. Between 90 and 125 % is what
>   well-calibrated sessions give.

### 5 · What happens on stopping

On **Stop recording**, the Acquisition tab shows the **whole session** with its
phases shaded (warm-up, each calibration repetition, preparation, recording), and
the **Analysis** tab analyses the recording **on its own**, with nothing to
press. On switching to Analysis a box points at the next step:

1. **«Calibration repetitions…»**: the six repetitions of each muscle with their
   values. Untick the weak ones and accept; the reference is recomputed. This
   goes first because **every percentage is measured against that reference**.
2. **«Select fragments…»**: one row per contraction found, with its start, end,
   duration and, with two muscles, which one led it. Untick those not worth
   analysing (a badly made movement, a cable tug) and press **«Use these
   fragments»** even if nothing changed. In the single-muscle practical, if the
   calibration was made with the button, also untick the six calibration efforts
   to keep the task.
   The dialogue is adjusted by looking: two sliders, the **sensitivity** (how
   many contractions it finds; the dashed line over the envelope is the
   threshold it sets) and, in the pair, the **co-activation threshold** (from
   what share of the stronger muscle the weaker one counts as co-activating).
   Every move redraws the shading and the rows at once, and a click on a shaded
   stretch drops or restores it. The **fine adjustment** (minimum duration, gap
   joining, split between contractions) stays folded and is rarely needed.

Then read. The tab has three areas: the **panels** (top; the mouse wheel scrolls
them; the ▲▼ and ▶◀ buttons on the left change the scales), the **contraction
chart** and the **summary** (bottom) and, in the pair, the **co-activation
chart**. The contraction chart shows one view at a time, chosen on its title
line, and opens on the **relation**, which is the one a conclusion is read
from. With one muscle it is **amplitude against MDF**, contraction by
contraction and joined in order: a drift towards more amplitude and less
frequency is fatigue, towards more of both is more force, and the other two
quadrants are their opposites. With two muscles it is **one muscle against the
other**, with the wedge in which the application calls a contraction
co-activation: a flexion falls on one axis, an extension on the other and a grip
inside the wedge. With two muscles there are also **«Category»**, each muscle's
mean per manoeuvre with every contraction as a dot, and **«Who leads»**, one bar
per contraction to the right when the first muscle led and to the left when the
second did, with the co-activation band in the middle. **«Series»** follows the
contractions in order with the fitted trend and the MDF on the right axis, and in
kinematics **«By load»** groups amplitude, velocity and electromechanical delay by the
load the wizard marked. **«Table»** is the numbers, which are the ones copied
into the tables of this guide. The co-activation chart is one line per window:
the name on the left, the seconds on the right and, between them, the index as
a purple bar or, when it is not reported, a gold block and a small square in
the colour of the muscle that worked alone; the legend above says what each
colour is, and the means in % MVC are in its «Table».
**«Generate PDF report»** produces the deliverable with the
figures, the calibration, the charts, the tables and the cards.

### 6 · Following the session on a phone

In a group practical, **one person drives the equipment** and the rest follow the
signal in their phone's browser. In Acquisition, tick **«Broadcast to phones (in
the laboratory)»**; an address `http://…:8070/?k=…` and a **QR** button appear.
Everyone on the same Wi-Fi, and the address typed with `http://`. The phone only
watches and downloads: the session as CSV while recording and, when the operator
analyses, the PDF report and the results. Each activation generates a new code;
links from a previous practical expire.

---

## Practical 1 — Single-muscle contraction (basic level)

**Set-up.** One channel over the FCR (or over the biceps if a large muscle is
preferred), reference on the olecranon. Selector on **Single-muscle contraction**.

**What the application shows in this practical.** Three panels by default: **1A.
Raw**, **2. Env. norm.** (the envelope scaled to its maximum) and **3. PSD** (the
spectrum, with the spectrum *before* the filter in grey behind). Below, the
**contraction table** with one row per effort (start, duration, RMS, peak in %
MVC, MDF) and the **summary cards** (MNF, MDF, MDF slope, fatigue, task maximum,
global RMS, iEMG, duration, MVC). **«More panels…»** reveals the rest for anyone
who wants to look further.

### Exercise 1a · First recording: from the signal to the number

**Objective.** Obtain a clean recording and recognise the representations of the
signal.

**Procedure.**
1. **Start recording**. Sequence: 5 s rest, light contraction 4 s, rest 5 s,
   strong contraction 4 s, rest 5 s. The application marks each contraction's
   onset by itself (**Auto-onset**, threshold = rest + k × noise, with k = 3).
2. **Stop**. Go to **Analysis** and accept the fragments it proposes.

**Data to record.** From the contraction table:

| Contraction | Duration (s) | RMS (mV) | MDF (Hz) |
|---|---|---|---|
| light | | | |
| strong | | | |

**Questions.**
- Why is the raw signal positive and negative and the envelope positive only?
  What does rectification do?
- In panel 3, the grey spectrum is the signal before the filter and the blue one
  after. What has gone? At which frequency was it? And below 20 Hz?
- Is the RMS of the strong contraction larger than that of the light one? By how
  many times? Which two nervous mechanisms explain the growing amplitude?
- Do the automatic onsets agree with what the envelope shows?

### Exercise 1b · Graded effort: more force, more signal, but not twice as much

**Objective.** Check that amplitude grows with activation monotonically but
**not linearly**, and see what normalisation is for.

**Procedure.**
1. **Start recording** and press **«Calibrate MVC»** at once: the wizard asks for
   the warm-up and the six maximal efforts (section 4). Afterwards the **load
   bars** in the «Muscle load» box show % MVC live.
2. Guided by the bar, make four 4 s isometric contractions against the table at
   **25, 50, 75 and 100 %** of the bar, with 5 s of rest between them.
3. **Stop**. In Analysis, review the calibration repetitions and, in the
   fragments, keep only the four steps.

**Data to record.** From the contraction table:

| Step asked for | RMS (mV) | Peak (% MVC) |
|---|---|---|
| 25 % | | |
| 50 % | | |
| 75 % | | |
| 100 % | | |

**Questions.**
- Does the RMS rise at each step? Does it double from 25 to 50 %? And from 50 to
  100 %? Comment on the shape of the relationship and on why sEMG is a good
  indicator of activation and a poor dynamometer.
- Compare your RMS at 100 % with a classmate's. Who "makes more force"? Why is
  that comparison invalid, while the % MVC column is valid?
- What does the **«Task maximum»** card say? If it is above 100 %, what happened
  in the calibration?

### Exercise 1c · Sustained contraction: the signature of fatigue

**Objective.** Detect fatigue from the shift of the spectrum towards lower
frequencies, and understand what it takes to be able to claim it.

**Background.** Holding a contraction lowers the pH and the conduction velocity
of the fibres; the spectrum compresses downwards and **the MDF falls**. At the
same time the RMS usually **rises**, because more units are recruited to keep the
force. The specific proof is the fall of the MDF, not the rise of the RMS.

**Procedure.**
1. **Start recording**, **Calibrate MVC**, then hold an isometric contraction
   against the table at **50 %** of the bar **for 30 to 60 s**, or until it cannot
   be held. 5 s of rest before and after.
2. **Stop**. In Analysis, review the repetitions and, in the fragments, keep
   **only the sustained contraction**. Tick panel **7. MDF/time** (in «More
   panels…»).

**How the application decides.** It fits a line to the MDF of the one-second
windows in which the muscle was working. It says **«Fatigue detected»** if the
slope is negative and the line explains something (R² ≥ 0.30, at least four
windows); **«Not detected»** if the MDF holds or rises with a line that fits; and
**«Not conclusive»** if the line does not fit, which is the norm in a series of
brief contractions. Not conclusive is not "no": the recording does not answer the
question.

**Data to record.**

| Quantity | First 5 s | Last 5 s |
|---|---|---|
| MDF (Hz) (panel 7) | | |
| RMS (mV) (panel 6, in «More panels…») | | |

MDF slope: ____ Hz/s (R² = ____). Verdict: ______________.

**Questions.**
- Did the MDF fall? By what percentage? What explains it in the fibres?
- Did the RMS rise at the end? Why would the nervous system do that? What part
  of that rise may not be recruitment?
- A classmate held for 15 s and got «not conclusive». Fatigued or not? What is
  the recording missing?

### Exercise 1d · The load of a task (Jonsson's method)

**Objective.** Express a task in % MVC and describe its load with three levels.

**Background.** The **APDF** sorts every instant of the task from least to most
effort and reads three points: **P10 (static)**, the load the muscle never lets
go of; **P50 (median)**, the typical effort; **P90 (peak)**, the moments of
highest demand. Jonsson recommended not exceeding 2–5 % for the static level,
10–14 % for the median and 50–70 % for the peak; the application uses the upper
end of each range (5, 14 and 70 %). The risk usually comes not from the peaks but
from a high, sustained static level.

**Procedure.**
1. **Start recording**, **Calibrate MVC**, and do a task for **60 s**: hold a
   bottle of water with the wrist neutral, or type with the hand raised, or lift
   and put down a weight every 10 s. Each group a different one.
2. **Stop**. In **MVC normalisation** the result appears on its own. With **«Select
   fragments…»** keep only the task (without the calibration), or the peak will
   be the maximum itself.

**Data to record.** From the data panel:

| Level | Value (% MVC) | Limit | Within? |
|---|---|---|---|
| Static (P10) | | 5 % | |
| Median (P50) | | 14 % | |
| Peak (P90) | | 70 % | |
| Mean activation | | 10 % | |

**Questions.**
- Which level exceeds its limit? Compare with another group's task: which has
  the higher peak and which the higher static level? Which is worse for the
  muscle, and why?
- The live bars warned in amber above 40 % and in red above 70 %. Does that
  impression match the APDF? Explain why they measure different things.
- Propose a change to the task that lowers the static level without lowering
  the peak.

---

## Practical 2 — Agonist / antagonist contraction (intermediate level)

**Set-up.** Two channels: **FCR** on channel 1 (A1) and **ECR** on channel 2 (A2),
common reference on the olecranon or one on each styloid. Selector on **Agonist /
antagonist contraction**. Labels: FCR and ECR.

**What the application shows in this practical.** On **Start recording** the
wizard calibrates **both muscles** (section 4) and then opens the recording. The
analysis offers **1A. Raw**, **1B. Raw (2nd)**, **3. PSD** with both curves, **7.
MDF/time** of both and **9. Env. overlay**, the two envelopes in % MVC on the same
axis. The contraction table says **which muscle led each one** (FCR, ECR or
«Co-activation» when the smaller exceeds half of the larger, each measured
against its own maximum) and the **co-activation table** gives, per window, the
mean activation of each muscle and the **Falconer-Winter index**.

**Why in % MVC and not in millivolts.** The millivolts of two different muscles do
not compare: they depend on where the electrodes ended up and how much skin and
fat lies beneath. On the bench of 3 September the flexor's reference was a third
of the extensor's; a flexion at 100 % of the flexor read *fewer millivolts* than
the extensor at 42 %. Everything that compares two muscles in this practical
does so as a percentage of each one's maximum.

### Exercise 2a · Flexion, extension and grip

**Objective.** See the reciprocal pattern of an antagonist pair and measure its
co-activation.

**Why the grip works.** The finger flexors are extrinsic: their bellies are in the
forearm and their tendons cross the wrist. Closing the fist therefore produces,
besides the closing of the fingers, a flexor moment on the wrist that would bend
it; the radial wrist extensors counter it and hold the wrist in slight extension,
which is the length at which those flexors are strongest. That is why grip force
falls when the wrist flexes, and why the extensors are continuously active
throughout a grip, without the silences they show in a reciprocal movement. Here
they are not antagonists but stabilisers. It is also the mechanism of lateral
epicondylitis, an injury of repeated gripping and not of extending the wrist.

**Procedure.**
1. **Start recording**. Calibrate both muscles as in section 4 (fist closed for
   the FCR, back of the hand for the ECR).
2. In the recording, always in this order, with 2 s of stillness between
   manoeuvres: **six wrist flexions** (1 s each, against the table), **six
   extensions**, and finally the **grip**.
3. **The grip in detail**, because it is the manoeuvre that yields a number and
   the easiest one to get wrong:
   - Forearm on the table as far as the wrist, elbow at 90°, thumb up, and **the
     wrist beyond the edge, in the air**. If the wrist rests on the table, the
     table does the stabilising, the extensor relaxes and the manoeuvre measures
     nothing.
   - Squeeze something that does not deform and gives a repeatable posture: a
     rolled-up blood-pressure cuff, a tennis ball or a tightly rolled towel. A
     hand dynamometer is better still, since it also quantifies the effort.
   - «Close the fist hard and hold it» for **5 s**, firm but submaximal, guided by
     the load bar towards 50–60 %. **Never say «extend the wrist»**: the extensors
     have to come in on their own.
   - Three 5 s grips 2 s apart give more signal and still count as one window,
     since consecutive rows with the same name are grouped.
   - It goes last, so its fatigue does not contaminate the flexions or the
     extensions.
4. **Stop**. In Analysis, review the repetitions and accept the fragments: the
   **Muscle** column comes filled in with who led each contraction; correct only
   if the trace says otherwise. Consecutive rows with the same name form one
   window of the co-activation table.

**Data to record.**

| Window | FCR (mean % MVC) | ECR (mean % MVC) | Co-activation index |
|---|---|---|---|
| Flexions | | | |
| Extensions | | | |
| Grip | | | |

From the event log or the PDF, the **channel separation** during calibration:
ECR during the FCR maximum ____ %; FCR during the ECR maximum ____ %.

**What each manoeuvre teaches.** The three in this exercise, plus the one in 2b,
form a progression worth reading whole before answering:

| Manoeuvre | What the two muscles do | What the index gives |
|---|---|---|
| Flexions | the FCR works; the ECR stays under the 5 % floor | not reported |
| Extensions | the roles swap | not reported |
| Grip | both work at once | a high number, of the order of 60–95 % |
| Fast alternation (2b) | both work, but by turns | a low number |

The grip is the only manoeuvre of this montage that produces a number, and the
comparison with the fast alternation of exercise 2b closes the argument: in both
manoeuvres the two muscles work, but only in the grip do they work **at the same
time**, which is what the index measures. Co-activation is a property of the task,
not of the muscle.

**Questions.**
- During the flexions, what does the ECR do? If its row says «not reported», why
  is that the right answer and not a fault?
- During the grip, who works? Explain why the wrist extensors contract hard when
  the hand closes although nobody extends anything, and what it has to do with
  lateral epicondylitis.
- The channel separation during the maxima: is it below 25 %? Above 50 % the
  application says «channels not separated». What does that number measure and
  what can be done with the electrodes?
- Compare the two muscles' MDFs in panel 3. Are they different? What can an MDF
  well above the usual range mean?

### Exercise 2b · Voluntary co-activation and fatigue of a pair

**Objective.** See that co-activation depends on the task, not on the muscle.

**Procedure.** Without recalibrating, record again: 10 s of **fast alternating
flexions and extensions** (like shaking the hand), then a **grip held for 30 s**.

**Data to record.** Co-activation index of the alternation window and of the grip;
fatigue verdict of each muscle in the grip (panel 7 draws both).

**Questions.**
- Is there more co-activation in the fast alternation or in the grip? Why does
  the index compare the *shape* of the two envelopes and not their size?
- In the held grip, which of the two muscles shows the MDF fall first? Propose an
  explanation.

---

## Practical 3 — Muscle kinematics (advanced level)

**Set-up.** One channel over the **biceps brachii**, reference on the olecranon,
and the BITalino **accelerometer** taped to the **back of the wrist** (the moving
segment). Selector on **Muscle kinematics**. The wiring is a convention the
accelerometer box states: **muscle on A1, accelerometer on A2**. In that box,
placement «on the moving segment», and under «Labels» the muscle's name (biceps),
which goes into the EDF header.

**What the application shows in this practical.** The fine controls appear
(envelope cut-off, region, refined EDF, force-velocity study). The analysis offers
the three basic panels plus **10. EMG vs MMG**, **11. Tremor** and **12. Movement
vs EMG**. The contraction table adds the **electromechanical delay (EMD)** of each
effort: the time between the onset of the electrical signal and the onset of the
movement in the accelerometer. The **«Rehearse…»** button runs the whole
force-velocity procedure with no hardware, on a simulated signal, to learn it
before strapping anyone to anything.

### Exercise 3a · The force-velocity relationship

**Objective.** Obtain the biceps' force-velocity curve with known loads.

**Background.** The more load, the slower the muscle shortens; against a load
equal to its maximum it does not move (isometric). Power (force × velocity) is
greatest at intermediate loads. The accelerometer gives the velocity of the lift
and the EMG the activation.

**Procedure.**
1. Prepare four known loads (for instance 0, 1, 2 and 3 kg: a bottle and
   dumbbells or filled bottles).
2. The **«Force-velocity study»** box is the sequence, in its order. **«1 ·
   Rehearse…»** runs the procedure with no hardware; optional, to learn it
   before anyone holds a weight. **«2 · F-V parameters…»** asks for the **plan**
   (the loads in order, the lifts per load, two or three, and the preparation
   seconds) and keeps it. Then **«Start recording»** runs the session by itself:
   it names the file, **calibrates the maximum first** (warm-up, three held
   maxima and three brief squeezes, against the table), announces the study and,
   for each load, cues the repetitions of **one quick lift**, each with its
   countdown and marked in the file with its load. No isometric maximum without
   load in between: the calibration was that. Just follow the screen; «Cancel
   guide (Esc)» stops it without stopping the recording.
3. **Stop**. In Analysis, the contraction table holds one row per lift with
   its load, and **«Force-velocity study…»** reads those rows and returns four
   curves: load-velocity, force-velocity (normalised hyperbola), power and
   recruitment (EMG amplitude against load).

**Data to record.**

| Load (kg) | Peak velocity (rel. u.) | Biceps RMS (% MVC) |
|---|---|---|
| 0 | | |
| 1 | | |
| 2 | | |
| 3 | | |

Load of maximum power: ____ kg.

**Questions.**
- Does velocity fall as load rises? With what shape? Where does maximum power
  fall?
- Does the EMG amplitude rise with load although velocity falls? Which mechanism
  explains it?
- Why is the isometric maximum calibrated with the elbow locked?

### Exercise 3b · The electromechanical delay

**Objective.** Measure the time between the electrical command and the movement.

**Background.** Between the fibre depolarising and the segment starting to move
some tens of milliseconds pass: calcium release, cross-bridge formation,
tensioning of the series elastic elements. In healthy adults the delay lies
between **30 and 100 ms** in voluntary contractions.

**Procedure.** With the same set-up, **Start recording** and make **eight quick
elbow flexions** without load, from the arm relaxed and hanging, with 3 s of rest
between them. **Stop**. In the contraction table, column **EMD (ms)**.

**Data to record.** EMD of the eight flexions; mean and deviation.

**Questions.**
- Are your values within range? Which physiological steps take up that time?
- Repeat three flexions **with 2 kg in the hand**. Does the delay change? Why does
  the segment take longer to start moving when there is a load to overcome?

### Exercise 3c · Physiological tremor

**Objective.** See physiological tremor in the accelerometer and locate its
frequency.

**Procedure.** **Start recording** and hold the arm **extended forward,
horizontal, for 30 s**, unsupported; then another 30 s holding 2 kg. **Stop**.
Panel **11. Tremor**: the accelerometer's spectrum.

**Data to record.** Frequency of the tremor peak without load ____ Hz; with load
____ Hz.

**Questions.**
- Does the peak fall between 8 and 12 Hz? Does it change with load?
- Physiological tremor arises partly from synchronised motor-unit discharge and
  partly from the mechanics of the segment. Which part would change with load
  and which would not?

---

## Reference ranges for interpreting

The numbers in the table are **orientative**, not limits: they hold for surface
EMG in healthy adults, and depend on the muscle, the electrodes and the subject. A
value outside the range is a question, not an error. These same ranges appear in
grey under the summary cards and in the «?» of the tables.

| Measure | Orientative range | Where it comes from |
|---|---|---|
| Mean frequency (MNF) | 80–170 Hz | most of the surface-EMG power lies between 50 and 150 Hz; MNF is always a little above MDF because of the spectrum's tail |
| Median frequency (MDF) | 60–150 Hz; in the forearm rather 90–150 | the same band; at the bench (FCR and ECR) 86–127 Hz with a good montage, 176 Hz with a misplaced electrode |
| MDF fall with fatigue | clear negative slope; no universal magnitude threshold | the application requires not an amount but a trend that fits (R² ≥ 0.30, ≥ 4 one-second windows) |
| RMS at rest | ≈ 0.005–0.02 mV | background noise of amplifier and skin (≥ 8 µV peak to peak at best) |
| RMS in firm effort | 0.1–1 mV; maxima up to ~1.5 mV | surface electrodes over limb muscles |
| Task effort | 20–80 % MVC | a typical submaximal effort; > 100 % sustained says the calibration was not maximal |
| Task maximum with a sound calibration | 90–125 % MVC | bench sessions with a correct calibration; the application warns in red from 150 % |
| Antagonist co-activation | 5–10 % MVC in light efforts; 25–35 % in maxima | triceps during maximal elbow flexion ≈ 26 %; finger extensor during wrist flexion at 75 % ≈ 15 % |
| Co-activation index (Falconer-Winter) | reciprocal movement: «not reported»; firm grip: 60–95 % | the index measures shared activity; in a clean flexion the antagonist stays below the 5 % floor |
| Channel separation (cross-talk) | ≤ 20–25 % of its own reference | bench with well-placed electrodes; > 50 %, «channels not separated» |
| Static load (P10) | ≤ 2–5 % MVC (the application uses 5) | Jonsson 1978, 1982 |
| Median load (P50) | ≤ 10–14 % MVC (the application uses 14) | Jonsson 1978, 1982 |
| Peak load (P90) | ≤ 50–70 % MVC (the application uses 70) | Jonsson 1978, 1982 |
| Electromechanical delay | 30–100 ms; voluntary, 35–80 ms | Cavanagh and Komi 1979: biceps 41 ± 13 ms, triceps 26 ± 11 ms |
| Physiological tremor | peak at 8–12 Hz | accelerometry of maintained posture in healthy adults |
| Contraction-onset threshold | rest + 3 standard deviations | Hodges and Bui 1996 |

---

## Appendix — Student report template

For each practical, submit:

1. **Identification**: test identifier, muscle(s), device, practical and
   exercises done.
2. The **PDF report** the application generates (it holds the figures, the
   calibration with its repetitions, the contraction table and the cards). With
   the broadcast on, it can be downloaded on the phone itself.
3. The **data tables** of the exercises, copied from the report.
4. The **reasoned answers** to the questions, citing the numbers.
5. A brief **conclusion** relating what was observed to the physiology: motor
   unit, recruitment, conduction velocity, force-velocity relationship,
   ergonomic risk.

> **Note for instructors.** What decides the quality of a practical is the
> calibration: a maximum that was not one makes every percentage false, and the
> application says so in red on the «Task maximum» card. It is worth checking
> before letting the group go on. The questions that compare across groups work
> best if each group does a different task in 1d. The ranges in the table above
> are also in the application, so the student has something to interpret against
> without opening the guide.
