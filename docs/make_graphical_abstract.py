"""Draw the HP-Pilot graphical abstract: problem, pipeline, results, use. Output: graphical_abstract.png."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK, MUTED, SURFACE = "#0b0b0b", "#5a5955", "#fcfcfb"
BLUE, ORANGE, PALE_BLUE, PALE_ORANGE = "#0072B2", "#E69F00", "#e6f0f8", "#fbf1dc"
OUT = Path(__file__).resolve().parent / "figures" / "graphical_abstract.png"

fig, ax = plt.subplots(figsize=(16, 9), facecolor=SURFACE)
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis("off")


def box(x, y, w, h, title, body="", fc=SURFACE, ec=INK, tc=INK, size=12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.15",
                                fc=fc, ec=ec, lw=1.8))
    ax.text(x + w / 2, y + h - 0.38, title, ha="center", va="top", fontsize=size, weight="bold", color=tc)
    if body:
        ax.text(x + w / 2, y + h - 0.95, body, ha="center", va="top", fontsize=size - 2.5, color=INK,
                linespacing=1.45)


def arrow(x1, y1, x2, y2, color=INK):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=18, lw=2, color=color))


# Title
ax.text(0.4, 8.55, "HP-Pilot", fontsize=30, weight="bold", color=INK, va="center")
ax.text(3.35, 8.55, "Find high-pressure crystal structures, and know when your fast ML model is wrong",
        fontsize=15, color=MUTED, va="center")

# 1. Problem (left)
box(0.4, 4.6, 3.3, 3.5, "The problem",
    "High pressure makes new\nmaterials, but search is\n\nDFT: accurate, but slow\n\nML: fast, but trained at\nambient pressure, so it can\nbe wrong without warning",
    fc=PALE_ORANGE, ec=ORANGE, size=13)

arrow(3.75, 7.4, 4.35, 7.4)

# 2. Pipeline (middle): stages 1-4 across the top, then the trust branch
box(4.4, 6.6, 3.6, 1.6, "1-2  Generate & relax",
    "Random candidates, relaxed\nby ML (MACE) at your pressure", fc=PALE_BLUE, ec=BLUE, size=12)
box(8.4, 6.6, 3.2, 1.6, "3  Trust check",
    "Committee of 3 models\nplus physics checks", fc=PALE_BLUE, ec=BLUE, size=12)
arrow(8.0, 7.4, 8.4, 7.4)

# Branch
box(4.4, 4.6, 3.6, 1.5, "Trusted", "ML answer kept.\nFast screening.", fc=SURFACE, ec=BLUE, tc=BLUE, size=12)
box(8.4, 4.6, 3.2, 1.5, "Needs DFT", "Reason written down.\nSent to VASP.", fc=SURFACE, ec=ORANGE, tc=ORANGE, size=12)
arrow(9.0, 6.6, 6.3, 6.1, color=BLUE)
arrow(10.9, 6.6, 10.9, 6.1, color=ORANGE)

box(4.4, 2.6, 7.2, 1.5, "4-5  VASP inputs, SLURM jobs, DFT vs ML",
    "High-pressure settings, checked inputs, job plan\nsized to the cluster's free cores", fc=PALE_BLUE, ec=BLUE, size=12)
arrow(10.9, 4.6, 10.9, 4.2, color=ORANGE)

# 3. Results (right)
box(12.0, 4.6, 3.6, 3.5, "What we found",
    "NaCl: rocksalt to CsCl\nat 24.6 GPa (DFT)\n\nTrust limits differ\nper material\n\nMgVH5, 32-90 GPa:\nML wrong at every pressure",
    fc=PALE_BLUE, ec=BLUE, size=13)
arrow(11.6, 7.4, 12.0, 7.4)
arrow(11.6, 3.9, 12.6, 4.6, color=BLUE)

# 4. Use (bottom)
box(0.4, 0.4, 15.2, 1.8, "For experimentalists",
    "Compare your measured diffraction pattern with the simulated pattern of each predicted phase.\n"
    "Check the literature (Valency).  Use DFT where ML is flagged.  Simulation and experiment check each other.",
    fc=SURFACE, ec=INK, size=13)

ax.text(15.6, 0.1, "Open source (MIT) · github.com/k-abhikeern/hp-pilot", fontsize=10, color=MUTED, ha="right")

fig.savefig(OUT, dpi=200, facecolor=SURFACE, bbox_inches="tight")
print(f"wrote {OUT}")
