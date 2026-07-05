"""Numerical validation of emgteach's core sEMG metrics.

Each metric produced by the analytic core is checked against (a) an analytic
ground truth (signals whose theoretical MNF/MDF, fatigue slope and amplitude
percentiles are known in closed form) and (b) an independent reference
implementation built directly on scipy/numpy, so the check does not reuse
emgteach's own integration choices.

Run:  python validation/validate_metrics.py
Exit code 0 if every check passes, 1 otherwise.
"""
from __future__ import annotations

import os
import sys
import types

import numpy as np
from scipy.integrate import trapezoid
from scipy.signal import welch

SEED = 12345
FS = 1000.0
F_LO, F_HI = 20.0, 450.0

# --- import the Qt-free analytic core without running the package __init__
# (which pulls in the PySide6 workers/devices layers). We register a stub
# package so the submodule imports resolve, then import only the core modules.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "..", "src")
if os.path.isdir(os.path.join(_SRC, "emgteach")):
    sys.path.insert(0, _SRC)
    _pkg = types.ModuleType("emgteach")
    _pkg.__path__ = [os.path.join(_SRC, "emgteach")]
    sys.modules.setdefault("emgteach", _pkg)
from emgteach.apda import compute_apdf  # noqa: E402
from emgteach.dsp import compute_psd_mnf_mdf, compute_segments  # noqa: E402
from emgteach.fatigue import fit_mdf_vs_time  # noqa: E402
from emgteach.mvc import compute_mvc, normalise_to_mvc  # noqa: E402


def shaped_noise(shape_fn, n, fs, seed):
    """White Gaussian noise shaped in frequency so its PSD follows shape_fn(f)."""
    rng = np.random.default_rng(seed)
    spectrum = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, d=1.0 / fs)
    gain = np.sqrt(np.clip(shape_fn(f), 0.0, None))
    return np.fft.irfft(spectrum * gain, n=n)


def theoretical_mnf_mdf(shape_fn, f_lo=F_LO, f_hi=F_HI):
    """Exact MNF/MDF of a target PSD shape over [f_lo, f_hi] by dense integration."""
    f = np.linspace(f_lo, f_hi, 200001)
    s = np.clip(shape_fn(f), 0.0, None)
    total = trapezoid(s, f)
    mnf = trapezoid(f * s, f) / total
    cum = np.cumsum((s[:-1] + s[1:]) / 2 * np.diff(f))
    mdf = float(f[1:][np.searchsorted(cum, total / 2.0)])
    return float(mnf), mdf


def ref_mnf_mdf(sig, fs=FS, f_lo=F_LO, f_hi=F_HI):
    """Independent reference: Welch + trapezoid MNF and interpolated MDF."""
    f, p = welch(sig, fs=fs, nperseg=int(fs), noverlap=int(fs) // 2)
    mask = (f >= f_lo) & (f <= f_hi)
    f, p = f[mask], p[mask]
    total = trapezoid(p, f)
    mnf = trapezoid(f * p, f) / total
    cum = np.concatenate([[0.0], np.cumsum((p[:-1] + p[1:]) / 2 * np.diff(f))])
    mdf = float(np.interp(total / 2.0, cum, f))
    return float(mnf), mdf


_rows = []


def check(metric, case, got, ref, tol, unit="", rel=False):
    err = abs(got - ref)
    ok = (err / abs(ref) <= tol) if rel else (err <= tol)
    _rows.append((metric, case, got, ref, err, tol, "rel" if rel else "abs", unit, ok))


def run():
    # 1) MNF / MDF vs analytic ground truth and independent reference
    shapes = {
        "flat band [30,440]": lambda f: ((f >= 30) & (f <= 440)).astype(float),
        "rising PSD ~f": lambda f: np.where((f >= 30) & (f <= 440), f, 0.0),
        "falling PSD ~1/f": lambda f: np.where(
            (f >= 30) & (f <= 440), 1.0 / np.maximum(f, 1.0), 0.0
        ),
    }
    n = int(180 * FS)
    for name, shp in shapes.items():
        sig = shaped_noise(shp, n, FS, SEED)
        out = compute_psd_mnf_mdf(sig, FS, F_LO, F_HI)
        mnf_th, mdf_th = theoretical_mnf_mdf(shp)
        mnf_ref, mdf_ref = ref_mnf_mdf(sig)
        check("MNF", f"{name} vs analytic", out["mnf"], mnf_th, 0.02, "Hz", rel=True)
        check("MDF", f"{name} vs analytic", out["mdf"], mdf_th, 0.02, "Hz", rel=True)
        check("MNF", f"{name} vs indep ref", out["mnf"], mnf_ref, 0.01, "Hz", rel=True)
        check("MDF", f"{name} vs indep ref", out["mdf"], mdf_ref, 0.02, "Hz", rel=True)

    for f0 in (80.0, 250.0):
        t = np.arange(int(60 * FS)) / FS
        out = compute_psd_mnf_mdf(np.sin(2 * np.pi * f0 * t), FS, F_LO, F_HI)
        check("MNF", f"pure tone {f0:.0f} Hz", out["mnf"], f0, 2.0, "Hz")
        check("MDF", f"pure tone {f0:.0f} Hz", out["mdf"], f0, 2.0, "Hz")

    # 2) Fatigue slope recovery (end-to-end): impose a linear MDF ramp
    dur, f_start, f_end = 60.0, 150.0, 90.0
    t = np.arange(int(dur * FS)) / FS
    inst_f = f_start + (f_end - f_start) * (t / dur)
    rng = np.random.default_rng(SEED)
    sig = np.sin(2 * np.pi * np.cumsum(inst_f) / FS) + 0.02 * rng.standard_normal(t.size)
    seg = compute_segments(sig, FS, seg_len_s=1.0, overlap=0.5)
    fit = fit_mdf_vs_time(seg["t_seg"], seg["mdf_seg"], degree=2)
    check("Fatigue slope", "linear MDF ramp", fit["slope"],
          (f_end - f_start) / dur, 0.10, "Hz/s", rel=True)

    # 3) MVC + APDF vs a known amplitude distribution (uniform on [0, A])
    amp = 40.0
    env = np.linspace(0.0, amp, 500001)
    mvc = compute_mvc(env, percentile=95.0)
    check("MVC (P95)", "uniform[0,A]", mvc, 0.95 * amp, 1e-3, "mV", rel=True)
    ap = compute_apdf(normalise_to_mvc(env, mvc))
    got = {"static P10": ap.static.value, "median P50": ap.median.value,
           "peak P90": ap.peak.value}
    for lvl, k in (("static P10", 10), ("median P50", 50), ("peak P90", 90)):
        check(f"APDF {lvl}", "uniform[0,A]", got[lvl], k / 100.0 * amp / mvc * 100.0,
              0.01, "%MVC", rel=True)


def main():
    run()
    print(f"emgteach metric validation  (seed={SEED}, fs={FS:.0f} Hz)\n")
    hdr = (f"{'metric':<16}{'case':<32}{'emgteach':>11}{'reference':>11}"
           f"{'err':>9}{'tol':>7}   result")
    print(hdr)
    print("-" * len(hdr))
    n_pass = 0
    for metric, case, got, ref, err, tol, kind, _unit, ok in _rows:
        n_pass += ok
        tols = f"{tol * 100:.0f}%" if kind == "rel" else f"{tol:g}"
        print(f"{metric:<16}{case:<32}{got:>11.3f}{ref:>11.3f}"
              f"{err:>9.3f}{tols:>7}   {'PASS' if ok else 'FAIL'}")
    print("-" * len(hdr))
    print(f"{n_pass}/{len(_rows)} checks passed")
    return 0 if n_pass == len(_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
