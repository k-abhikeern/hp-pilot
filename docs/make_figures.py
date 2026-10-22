"""Video figures 01, 03 and 05 for HP-Pilot, drawn from the project's results (no new calculations).

    python docs/make_figures.py   (needs the stage 8 DFT runs for the XRD figure)

01_ml_error_vs_pressure.png      MgVH5: ML energy error vs DFT, 32-90 GPa (external test series)
03_nacl_transition_pressure.png  NaCl: which phase is more stable at each pressure (stage 8 scan)
05_simulated_xrd_patterns.png    NaCl rocksalt vs CsCl-type simulated XRD at 30 GPa (DFT-relaxed structures)
"""
import csv
import glob
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = Path(__file__).resolve().parents[1]
IMAGES = HERE / "figures"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#6b6a66", "#e1e0d9", "#fcfcfb"
BLUE, ORANGE = "#0072B2", "#E69F00"  # colourblind-safe pair: blue = DFT / rocksalt, orange = ML / CsCl-type
plt.rcParams.update({"font.size": 13, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.titlesize": 16, "axes.titleweight": "bold"})


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def fig_ml_error():
    rows = list(csv.DictReader(open(PROJECT / "3_stage_trust_check/external_tests/MgVH5_series/outputs/series_results.csv")))
    p = [float(r["pressure_GPa"]) for r in rows]
    err = [float(r["error_ML_minus_DFT_meV"]) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=SURFACE)
    style(ax)
    ax.axhspan(-50, 50, color=BLUE, alpha=0.12, lw=0)
    ax.axhline(0, color=INK, lw=1.2)
    ax.text(91, 4, "  ML = DFT", va="bottom", fontsize=12, color=INK)
    ax.text(91, 50, "  acceptable\n  (±50 meV/atom)", va="top", fontsize=11, color=BLUE)
    ax.plot(p, err, "-o", color=ORANGE, lw=3, ms=11, mec=SURFACE, mew=1.5, zorder=3)
    for x, y in zip(p, err):
        ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, -22), ha="center", fontsize=12, color=INK)
    ax.set_xlim(28, 100)
    ax.set_ylim(-270, 80)
    ax.set_xticks(p)
    ax.set_xlabel("Pressure (GPa)")
    ax.set_ylabel("ML energy error compared with DFT\n(meV per atom)")
    ax.set_title("The fast ML model is far off at every pressure", loc="left", pad=34)
    ax.text(0, 1.01, "MgVH$_5$ structure from the HPCSD database. Below zero: ML thinks the structure is "
            "more stable than DFT does.", transform=ax.transAxes, fontsize=11, color=MUTED, va="bottom")
    fig.tight_layout()
    fig.savefig(IMAGES / "01_ml_error_vs_pressure.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def crossing(p, dh):
    for (p1, d1), (p2, d2) in zip(zip(p, dh), zip(p[1:], dh[1:])):
        if d1 > 0 >= d2:
            return p1 + d1 * (p2 - p1) / (d1 - d2)
    return None


def fig_transition():
    rows = [r for r in csv.DictReader(open(PROJECT / "8_stage_pressure_scan/outputs/scan_NaCl_40GPa.csv"))
            if r["phase"] == "CsCl"]
    p = [float(r["pressure_GPa"]) for r in rows]
    dft = [float(r["dft_dH_meV_per_atom"]) for r in rows]
    ml = [float(r["ml_dH_meV_per_atom"]) for r in rows]
    t_dft, t_ml = crossing(p, dft), crossing(p, ml)
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=SURFACE)
    style(ax)
    ax.axhspan(0, 100, color=BLUE, alpha=0.07, lw=0)
    ax.axhspan(-130, 0, color=ORANGE, alpha=0.09, lw=0)
    ax.text(49.5, 88, "Rocksalt (B1) is stable", ha="right", fontsize=13, color=BLUE, weight="bold")
    ax.text(49.5, -120, "CsCl-type (B2) is stable", ha="right", fontsize=13, color="#9a6a00", weight="bold")
    ax.axhline(0, color=INK, lw=1.2)
    ax.plot(p, dft, "-o", color=BLUE, lw=3, ms=9, mec=SURFACE, label="DFT (accurate)", zorder=3)
    ax.plot(p, ml, "--o", color=ORANGE, lw=3, ms=9, mec=SURFACE, label="ML (fast)", zorder=3)
    ax.axvline(t_dft, color=BLUE, lw=1.5, ls=":")
    ax.annotate(f"DFT transition\n{t_dft:.1f} GPa", (t_dft, 0), xytext=(t_dft + 2.5, 45), fontsize=12, color=BLUE,
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.5))
    ax.annotate(f"ML transition\n{t_ml:.1f} GPa", (t_ml, 0), xytext=(t_ml - 12, -55), fontsize=12, color="#9a6a00",
                arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.5))
    ax.set_xlim(8, 52)
    ax.set_ylim(-130, 100)
    ax.set_xlabel("Pressure (GPa)")
    ax.set_ylabel("Enthalpy of CsCl-type minus rocksalt\n(meV per atom)")
    ax.set_title("NaCl changes structure at about 25 GPa", loc="left", pad=34)
    ax.text(0, 1.01, "Below zero, the CsCl-type phase has the lower enthalpy and wins. 0 K, quick DFT settings.",
            transform=ax.transAxes, fontsize=11, color=MUTED, va="bottom")
    ax.legend(loc="lower left", frameon=False, fontsize=12)
    fig.tight_layout()
    fig.savefig(IMAGES / "03_nacl_transition_pressure.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


def fig_xrd():
    from pymatgen.analysis.diffraction.xrd import XRDCalculator
    from pymatgen.core import Structure
    calc = XRDCalculator(wavelength="CuKa")
    x = np.linspace(20, 90, 4000)
    phases = [("rocksalt_Fm-3m_30GPa", "Rocksalt (B1), stable below about 25 GPa", BLUE),
              ("CsCl_Pm-3m_30GPa", "CsCl-type (B2), stable above about 25 GPa", ORANGE)]
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), facecolor=SURFACE, sharex=True)
    for ax, (tag, label, color) in zip(axes, phases):
        contcar = sorted(glob.glob(str(PROJECT / f"8_stage_pressure_scan/runs/scan_*/calcs/{tag}/CONTCAR")))[-1]
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        cubic = SpacegroupAnalyzer(Structure.from_file(contcar), symprec=0.1).get_conventional_standard_structure()
        pattern = calc.get_pattern(cubic, two_theta_range=(20, 90))
        # Gaussian peaks (0.25 degree wide) so the pattern looks like a measurement, not bare sticks.
        y = sum(i * np.exp(-0.5 * ((x - t) / 0.12) ** 2) for t, i in zip(pattern.x, pattern.y))
        y = 100 * y / y.max()
        style(ax)
        ax.fill_between(x, y, color=color, alpha=0.25, lw=0)
        ax.plot(x, y, color=color, lw=2)
        for t, i, hkls in zip(pattern.x, pattern.y, pattern.hkls):
            if i > 5:
                hkl = "".join(str(abs(v)) for v in hkls[0]["hkl"])
                height = 100 * i / max(pattern.y)
                ax.text(t, height + 4, f"({hkl})", ha="center", fontsize=12, color=INK)
        ax.set_ylim(0, 128)
        ax.set_yticks([])
        ax.set_ylabel("Intensity")
        ax.text(0.99, 0.93, label, transform=ax.transAxes, fontsize=13, weight="bold", color=color, va="top", ha="right")
    axes[-1].set_xlabel("Diffraction angle 2θ (degrees, Cu Kα X-rays)")
    axes[0].set_title("Two NaCl phases give different diffraction patterns (30 GPa)", loc="left")
    fig.text(0.01, 0.005, "Simulated from the DFT-relaxed structures. An experimentalist compares a measured pattern "
             "with these to identify the phase.", fontsize=10.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(IMAGES / "05_simulated_xrd_patterns.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    fig_ml_error()
    fig_transition()
    fig_xrd()
    print("wrote 01, 03 and 05 in", IMAGES)
