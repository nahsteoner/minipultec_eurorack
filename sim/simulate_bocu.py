#!/usr/bin/env python3
"""OnerLAB BoCu — AC + saturation simulations of the solid-state Pultec-style EQ.

Linear AC uses nodal analysis (gyrator = inductor). Saturation uses ngspice.
"""
from __future__ import annotations

import math
import os
import subprocess
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "plots"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Locked analog values (also used by the KiCad generator)
# ---------------------------------------------------------------------------
RS = 4.7e3
RFLOOR = 4.7e3
RMAKE = 10e3

# Low-boost gyrator: L = Rgyr^2 * Cgyr
RGYR_LOW = 33.2e3
CGYR_LOW = 10e-9
L_LOW = RGYR_LOW * RGYR_LOW * CGYR_LOW  # 11.022 H
RBOOST_MAX = 50e3
RBOOST_MIN = 2.7e3
CBOOST = {40: 1.5e-6, 80: 390e-9, 120: 150e-9}

# Low-cut: series (Rcut || Ccut). Corner ~3–4× f_boost so the trick scoops mud.
RCUT_MAX = 50e3
CCUT = {40: 82e-9, 80: 39e-9, 120: 27e-9}

# Mid cut: SERIES LC to ground ~500 Hz (notch / scoop)
RGYR_MID = 10e3
CGYR_MID = 10e-9
L_MID = RGYR_MID * RGYR_MID * CGYR_MID  # 1.0 H
CMID = 100e-9
RMID_SERIES = 1.0e3
RMID_MAX = 50e3

# Makeup: RLC (low) and RC (high) hang from inverting node to GND
RF = 15e3
RG1 = 2.2e3
RG2 = 10e3
CHI = 8.2e-9
RH_SERIES = 2.2e3
RHI_MAX = 50e3

F_MIN, F_MAX, N_F = 10.0, 30000.0, 1400


def zc(c, w):
    return 1.0 / (1j * w * c)


def zl(l, w):
    return 1j * w * l


def par(*zs):
    acc = 0j
    for z in zs:
        acc += 1.0 / z
    return 1.0 / acc


def rheo_short(alpha: float, rmax: float, rmin: float = 40.0) -> float:
    """Rheostat where alpha=1 shorts the branch (max boost / mid / high)."""
    a = min(max(alpha, 0.0), 1.0)
    return rmin + (1.0 - a) * rmax


def rheo_open(alpha: float, rmax: float, rmin: float = 40.0) -> float:
    """Rheostat where alpha=1 opens the bypass (max low-cut)."""
    a = min(max(alpha, 0.0), 1.0)
    return rmin + a * rmax


def makeup_gain(w, hi_alpha: float, boost_alpha: float, fsel: int) -> complex:
    """Non-inverting makeup. Low-boost RLC and high-boost RC from ninv to GND."""
    z_dc = RG1 + RG2
    z_low = RBOOST_MIN + rheo_short(boost_alpha, RBOOST_MAX) + zl(L_LOW, w) + zc(CBOOST[fsel], w)
    z_hi = RH_SERIES + rheo_short(hi_alpha, RHI_MAX) + zc(CHI, w)
    zg = par(z_dc, z_low, z_hi)
    return 1.0 + RF / zg


def channel_tf(f, fsel, boost=0.0, cut=0.0, mid=0.0, high=0.0) -> complex:
    """Vout / Vbuf at frequency f (Hz)."""
    w = 2 * math.pi * f
    c_c = CCUT[fsel]

    z_mid = RMID_SERIES + rheo_short(mid, RMID_MAX) + zl(L_MID, w) + zc(CMID, w)
    z_cut = par(rheo_open(cut, RCUT_MAX), zc(c_c, w))

    # Node EQ: pad + mid notch. Low boost lives in the makeup, not as a shunt.
    y11 = 1 / RS + 1 / RFLOOR + 1 / z_mid + 1 / z_cut
    y12 = -1 / z_cut
    y21 = -1 / z_cut
    y22 = 1 / z_cut + 1 / RMAKE
    i1 = 1 / RS
    det = y11 * y22 - y12 * y21
    vpost = (y11 * 0 - y21 * i1) / det
    return makeup_gain(w, high, boost, fsel) * vpost


def sweep(fsel, **knobs):
    freqs = np.logspace(math.log10(F_MIN), math.log10(F_MAX), N_F)
    h = np.array([channel_tf(f, fsel, **knobs) for f in freqs])
    mag = 20 * np.log10(np.maximum(np.abs(h), 1e-12))
    phase = np.unwrap(np.angle(h)) * 180 / math.pi
    return freqs, mag, phase, h


def style():
    plt.rcParams.update(
        {
            "figure.facecolor": "#101216",
            "axes.facecolor": "#161b22",
            "axes.edgecolor": "#8b949e",
            "axes.labelcolor": "#e6edf3",
            "xtick.color": "#c9d1d9",
            "ytick.color": "#c9d1d9",
            "text.color": "#e6edf3",
            "grid.color": "#30363d",
            "legend.facecolor": "#1f242c",
            "legend.edgecolor": "#30363d",
            "font.size": 10,
        }
    )


def plot_family(path, title, curves, ylabel="Amplitude (dB)", ylim=None):
    style()
    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=140)
    freqs_ref = None
    for label, freqs, mag, color, ls in curves:
        ax.semilogx(freqs, mag, label=label, color=color, lw=2.0, ls=ls)
        freqs_ref = freqs
    ax.set_xlim(20, 20000)
    if ylim:
        ax.set_ylim(*ylim)
    y_top = ax.get_ylim()[1]
    ax.axhline(0, color="#484f58", lw=0.8)
    for f0, name in [(40, "40"), (80, "80"), (120, "120"), (500, "500"), (8000, "8k")]:
        ax.axvline(f0, color="#21262d", lw=0.7, ls="--")
        ax.text(f0, y_top - 0.02 * (y_top - ax.get_ylim()[0]), f" {name}", fontsize=8, color="#8b949e")
    ax.set_xlabel("Fréquence (Hz)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, which="both", ls=":", alpha=0.7)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


def db_at(freqs, mag, f0):
    return float(np.interp(f0, freqs, mag))


def main():
    # Reference (all off) — insertion + makeup
    f0, mag0, _, _ = sweep(80, boost=0, cut=0, mid=0, high=0)
    print(f"flat 1 kHz = {db_at(f0, mag0, 1000):.2f} dB   Lgyr={L_LOW:.3f} H")

    colors = {
        40: "#58a6ff",
        80: "#3fb950",
        120: "#d2a8ff",
    }

    # Low boost
    curves = [("flat", f0, mag0 - mag0, "#8b949e", "--")]
    for fs in (40, 80, 120):
        f, mag, _, _ = sweep(fs, boost=1.0)
        mag = mag - mag0
        print(f"boost {fs} Hz  peak@fsel={db_at(f, mag, fs):.1f} dB  @1k={db_at(f, mag, 1000):.1f} dB")
        curves.append((f"low boost max  {fs} Hz", f, mag, colors[fs], "-"))
    plot_family(OUT / "01_low_boost.png", "OnerLAB BoCu — Low BOOST (relatif au plat)", curves, ylim=(-6, 16))

    # Low cut
    curves = [("flat", f0, mag0 - mag0, "#8b949e", "--")]
    for fs in (40, 80, 120):
        f, mag, _, _ = sweep(fs, cut=1.0)
        mag = mag - mag0
        print(f"cut {fs} Hz  @fsel={db_at(f, mag, fs):.1f} dB  @200={db_at(f, mag, 200):.1f} dB")
        curves.append((f"low cut max  {fs} Hz", f, mag, colors[fs], "-"))
    plot_family(OUT / "02_low_cut.png", "OnerLAB BoCu — Low CUT (relatif au plat)", curves, ylim=(-20, 6))

    # Pultec trick
    curves = [("flat", f0, mag0 - mag0, "#8b949e", "--")]
    for fs in (40, 80, 120):
        f, mag, _, _ = sweep(fs, boost=1.0, cut=1.0)
        mag = mag - mag0
        print(
            f"trick {fs} Hz  @fsel={db_at(f, mag, fs):.1f} dB  "
            f"@200={db_at(f, mag, 200):.1f}  @400={db_at(f, mag, 400):.1f}"
        )
        curves.append((f"boost+cut  {fs} Hz (Pultec trick)", f, mag, colors[fs], "-"))
    plot_family(
        OUT / "03_pultec_trick.png",
        "OnerLAB BoCu — Pultec trick : low BOOST + CUT simultanés",
        curves,
        ylim=(-14, 14),
    )

    # Mid cut
    curves = [("flat", f0, mag0 - mag0, "#8b949e", "--")]
    for a, col in ((0.4, "#79c0ff"), (0.7, "#58a6ff"), (1.0, "#1f6feb")):
        f, mag, _, _ = sweep(80, mid=a)
        mag = mag - mag0
        print(f"mid α={a}  @500={db_at(f, mag, 500):.1f} dB")
        curves.append((f"mid cut  {int(a*100)}%", f, mag, col, "-"))
    plot_family(OUT / "04_mid_cut.png", "OnerLAB BoCu — Mid CUT ~500 Hz", curves, ylim=(-14, 6))

    # High boost
    curves = [("flat", f0, mag0 - mag0, "#8b949e", "--")]
    for a, col in ((0.4, "#ff9b70"), (0.7, "#f0883e"), (1.0, "#ff7b72")):
        f, mag, _, _ = sweep(80, high=a)
        mag = mag - mag0
        print(f"high α={a}  @8k={db_at(f, mag, 8000):.1f} dB  @16k={db_at(f, mag, 16000):.1f}")
        curves.append((f"high boost  {int(a*100)}%", f, mag, col, "-"))
    plot_family(OUT / "05_high_boost.png", "OnerLAB BoCu — High BOOST shelf ~8 kHz", curves, ylim=(-4, 12))

    # Magic combo
    f, mag, _, _ = sweep(40, boost=0.85, cut=0.75, mid=0.45, high=0.7)
    mag = mag - mag0
    plot_family(
        OUT / "06_magic_combo.png",
        "OnerLAB BoCu — Recette type : trick 40 Hz + mid cut + air",
        [
            ("flat", f0, mag0 - mag0, "#8b949e", "--"),
            ("boost 85% + cut 75% @40 Hz, mid 45%, high 70%", f, mag, "#f2cc60", "-"),
        ],
        ylim=(-12, 14),
    )

    # Overlay all families at 80 Hz
    families = []
    for name, kn, col in [
        ("low boost max", dict(boost=1.0), "#3fb950"),
        ("low cut max", dict(cut=1.0), "#ff7b72"),
        ("Pultec trick", dict(boost=1.0, cut=1.0), "#58a6ff"),
        ("mid cut max", dict(mid=1.0), "#d2a8ff"),
        ("high boost max", dict(high=1.0), "#f0883e"),
        ("magic", dict(boost=0.85, cut=0.75, mid=0.45, high=0.7), "#f2cc60"),
    ]:
        f, mag, _, _ = sweep(80, **kn)
        families.append((name, f, mag - mag0, col, "-"))
    families.insert(0, ("flat", f0, mag0 - mag0, "#8b949e", "--"))
    plot_family(OUT / "07_all_80Hz.png", "OnerLAB BoCu — Vue d'ensemble (fréquence basse = 80 Hz)", families, ylim=(-16, 16))

    spice_saturation()
    write_report(mag0, f0)


def spice_saturation():
    """Transfer curve + harmonic spectrum of the diode makeup stage."""
    cir = r"""
* OnerLAB BoCu — makeup non-inverting + saturation asymétrique
.param vin_amp = 1.0
Vin in 0 SIN(0 {vin_amp} 100)

* Non-inverting makeup
Eop 1 0 in tap 200k
Ro 1 out 25
Rf out tap 15k
Rg1 tap midg 2.2k
Rg2 midg 0 10k

* 3x 1N4148 + 22k  (soft +)
D1 out d1 1N4148
D2 d1 d2 1N4148
D3 d2 d3 1N4148
Rsatp d3 tap 22k

* LED + 22k  (soft −, even harmonics)
Dled tap dled LEDRED
Rsatn dled out 22k

.model 1N4148 D(IS=2.52n N=1.752 RS=0.568 BV=75 IBV=10u CJO=4p TT=5.76n)
.model LEDRED D(IS=3e-21 N=1.8 RS=8)

.control
set units=degrees
dc Vin -8 8 0.02
wrdata transfer.dat out
tran 20u 80m 20m
linearize v(out) v(in)
wrdata tran.dat v(out) v(in)
quit
.endc
.end
"""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "sat.cir").write_text(cir)
        r = subprocess.run(
            ["ngspice", "-b", "sat.cir"],
            cwd=td,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print("ngspice failed:\n", r.stdout[-2000:], r.stderr[-2000:])
            return
        xf = np.loadtxt(td / "transfer.dat")
        vin, vout = xf[:, 0], xf[:, 1]
        style()
        fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=140)
        ax.plot(vin, vout, color="#f2cc60", lw=2, label="makeup + diodes")
        ax.plot(vin, vin * (1 + RF / (RG1 + RG2)), color="#8b949e", ls="--", lw=1.2, label="linéaire (sans diodes)")
        ax.set_xlabel("Vin makeup (V)")
        ax.set_ylabel("Vout (V)")
        ax.set_title("OnerLAB BoCu — saturation asymétrique (Si + LED)")
        ax.grid(True, ls=":", alpha=0.7)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "08_saturation_transfer.png")
        plt.close(fig)
        print("wrote", OUT / "08_saturation_transfer.png")

        # Spectrum at a few amplitudes
        amps = [0.5, 1.5, 3.0, 5.0]
        thd_rows = []
        style()
        fig, ax = plt.subplots(figsize=(10.5, 5.6), dpi=140)
        palette = ["#8b949e", "#58a6ff", "#f2cc60", "#ff7b72"]
        for amp, col in zip(amps, palette):
            spec_cir = cir.replace(".param vin_amp = 1.0", f".param vin_amp = {amp}")
            spec_cir = spec_cir.replace(
                "dc Vin -8 8 0.02\nwrdata transfer.dat out\n",
                "",
            )
            (td / "sat2.cir").write_text(spec_cir)
            subprocess.run(["ngspice", "-b", "sat2.cir"], cwd=td, capture_output=True, text=True)
            tr = np.loadtxt(td / "tran.dat")
            # wrdata: time, vout, time, vin
            t = tr[:, 0]
            vo = tr[:, 1]
            n = len(vo)
            dt = t[1] - t[0]
            spec = np.fft.rfft(vo * np.hanning(n))
            freqs = np.fft.rfftfreq(n, dt)
            mag = 20 * np.log10(np.maximum(np.abs(spec) * 2 / n, 1e-12))
            ax.plot(freqs, mag, color=col, lw=1.6, label=f"Vin = {amp:.1f} Vpk @ 100 Hz")
            # THD from harmonics of 100 Hz
            fund_i = np.argmin(np.abs(freqs - 100))
            harms = []
            for k in range(1, 9):
                idx = np.argmin(np.abs(freqs - 100 * k))
                harms.append(np.abs(spec[idx]))
            fund = harms[0]
            thd = 100 * math.sqrt(sum(h * h for h in harms[1:])) / fund if fund else 0
            even = 100 * math.sqrt(sum(h * h for h in harms[1::2])) / fund if fund else 0
            thd_rows.append((amp, thd, even))
            print(f"sat {amp:.1f} Vpk  THD={thd:.2f}%  even≈{even:.2f}%")
        ax.set_xlim(0, 1200)
        ax.set_ylim(-80, 10)
        ax.set_xlabel("Fréquence (Hz)")
        ax.set_ylabel("Amplitude FFT (dB, rel.)")
        ax.set_title("OnerLAB BoCu — spectre 100 Hz (harmoniques paires type lampes)")
        ax.grid(True, ls=":", alpha=0.7)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / "09_saturation_spectrum.png")
        plt.close(fig)
        print("wrote", OUT / "09_saturation_spectrum.png")
        (OUT / "thd.txt").write_text(
            "Vin_pk_V  THD_%  even_harm_%\n" + "\n".join(f"{a:.1f}  {t:.2f}  {e:.2f}" for a, t, e in thd_rows)
        )


def write_report(mag0, f0):
    lines = ["# OnerLAB BoCu — résultats de simulation\n"]
    lines.append(f"- Gyrator low L = {L_LOW:.3f} H (R={RGYR_LOW:.0f} Ω, C={CGYR_LOW*1e9:.0f} nF C0G)")
    lines.append(f"- Gyrator mid L = {L_MID:.3f} H → ~{1/(2*math.pi*math.sqrt(L_MID*CMID)):.0f} Hz")
    lines.append(f"- Niveau plat @1 kHz = {db_at(f0, mag0, 1000):.2f} dB (pad passif + makeup)")
    lines.append("")
    lines.append("| Réglage | 40 Hz | 80 Hz | 200 Hz | 500 Hz | 1 kHz | 8 kHz |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    rows = [
        ("plat (abs dB)", dict()),
        ("boost 40 max", dict(fsel=40, boost=1.0)),
        ("cut 40 max", dict(fsel=40, cut=1.0)),
        ("trick 40", dict(fsel=40, boost=1.0, cut=1.0)),
        ("trick 80", dict(fsel=80, boost=1.0, cut=1.0)),
        ("trick 120", dict(fsel=120, boost=1.0, cut=1.0)),
        ("mid max", dict(mid=1.0)),
        ("high max", dict(high=1.0)),
        ("magic", dict(fsel=40, boost=0.85, cut=0.75, mid=0.45, high=0.7)),
    ]
    for name, kn in rows:
        fs = kn.pop("fsel", 80)
        f, mag, _, _ = sweep(fs, **kn)
        if name != "plat (abs dB)":
            mag = mag - mag0
        cols = [f"{db_at(f, mag, x):+.1f}" for x in (40, 80, 200, 500, 1000, 8000)]
        lines.append("| " + " | ".join([name] + cols) + " |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("wrote", OUT / "summary.md")


if __name__ == "__main__":
    main()
