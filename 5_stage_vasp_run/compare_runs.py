"""Compare two VASP runs of the same structures, e.g. quick vs standard settings.

    ~/miniconda3/envs/osi/bin/python compare_runs.py runs/run_A runs/run_B --names quick standard

For every structure in both runs: enthalpy above the best structure in each run, the change, and the ML value.
Outputs (in outputs/):
    compare_<A>_vs_<B>.csv    one row per structure
    compare_<A>_vs_<B>.png    run A vs run B, coloured by trust label
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR))
from run_stage5 import INK, MUTED, GRID, SURFACE, STYLES, read_calc  # noqa: E402


def load(run_dir):
    rows = {}
    for d in sorted((Path(run_dir) / "calcs").iterdir()):
        r = read_calc(d) if d.is_dir() else None
        if r and "dft_enthalpy_eV_per_atom" in r:
            rows[r["name"]] = r
    best = min(r["dft_enthalpy_eV_per_atom"] for r in rows.values())
    ml_best = min(r["ml_enthalpy_eV_per_atom"] for r in rows.values())
    for r in rows.values():
        r["dH"] = 1000 * (r["dft_enthalpy_eV_per_atom"] - best)
        r["ml_dH"] = 1000 * (r["ml_enthalpy_eV_per_atom"] - ml_best)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Compare two VASP runs of the same structures.")
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--names", nargs=2, default=["A", "B"], help="short names for the two runs")
    args = parser.parse_args()
    a_name, b_name = args.names
    a, b = load(args.run_a), load(args.run_b)
    common = sorted(set(a) & set(b), key=lambda n: b[n]["dH"])

    out_dir = STAGE_DIR / "outputs"
    out_dir.mkdir(exist_ok=True)
    stem = f"compare_{a_name}_vs_{b_name}"
    rows = []
    for n in common:
        rows.append({"name": n, "id": b[n]["id"], "label": b[n]["label"],
                     "space_group": b[n]["dft_space_group"], "ml_dH_meV": round(b[n]["ml_dH"], 1),
                     f"{a_name}_dH_meV": round(a[n]["dH"], 1), f"{b_name}_dH_meV": round(b[n]["dH"], 1),
                     "change_meV": round(b[n]["dH"] - a[n]["dH"], 1),
                     f"{a_name}_steps": a[n]["ionic_steps"], f"{b_name}_steps": b[n]["ionic_steps"],
                     f"{b_name}_status": b[n]["dft_status"]})
    with open(out_dir / f"{stem}.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'id':5} {'label':9} {'space group':12} {'ML':>7} {a_name:>9} {b_name:>9} {'change':>7}")
    for r in rows:
        print(f"{r['id']:5} {r['label']:9} {r['space_group']:12} {r['ml_dH_meV']:7.1f} "
              f"{r[f'{a_name}_dH_meV']:9.1f} {r[f'{b_name}_dH_meV']:9.1f} {r['change_meV']:+7.1f}")
    changes = np.array([abs(r["change_meV"]) for r in rows])
    print(f"\nmean |change| {changes.mean():.1f} meV/atom, largest {changes.max():.1f} meV/atom")
    best_a = min(common, key=lambda n: a[n]["dH"])
    best_b = min(common, key=lambda n: b[n]["dH"])
    print(f"best in {a_name}: {a[best_a]['id']} ({a[best_a]['dft_space_group']}); "
          f"best in {b_name}: {b[best_b]['id']} ({b[best_b]['dft_space_group']})")
    rank_a = [a[n]["id"] for n in sorted(common, key=lambda n: a[n]["dH"])]
    rank_b = [b[n]["id"] for n in common]
    from scipy.stats import spearmanr
    print(f"rank agreement (Spearman) {a_name} vs {b_name}: {spearmanr([rank_a.index(i) for i in rank_b], range(len(rank_b)))[0]:.2f}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    top = max(max(r[f"{a_name}_dH_meV"], r[f"{b_name}_dH_meV"]) for r in rows) * 1.5 + 5
    fig, ax = plt.subplots(figsize=(5.5, 5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.plot([0, top], [0, top], ls="--", lw=1, color=MUTED, zorder=1)
    for label, (color, marker) in STYLES.items():
        pts = [r for r in rows if r["label"] == label]
        if pts:
            ax.scatter([r[f"{a_name}_dH_meV"] for r in pts], [r[f"{b_name}_dH_meV"] for r in pts], s=70,
                       c=color, marker=marker, edgecolors=SURFACE, linewidths=1.5, label=label, zorder=3,
                       clip_on=False)
    for r in rows[:3]:  # label the three most stable structures in run B
        ax.annotate(f"{r['id']} ({r['space_group']})", (r[f"{a_name}_dH_meV"], r[f"{b_name}_dH_meV"]),
                    xytext=(7, -3), textcoords="offset points", fontsize=8, color=INK)
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yscale("symlog", linthresh=10)
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_xlabel(f"DFT enthalpy above best, {a_name} settings (meV/atom)", color=INK)
    ax.set_ylabel(f"DFT enthalpy above best, {b_name} settings (meV/atom)", color=INK)
    ax.set_title(f"Do {b_name} DFT settings change the picture? ({len(rows)} structures)",
                 loc="left", fontsize=11, color=INK)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, labelcolor=INK, loc="lower right")
    fig.tight_layout()
    fig.savefig(out_dir / f"{stem}.png", dpi=200)
    print(f"wrote {out_dir / stem}.csv and .png")


if __name__ == "__main__":
    main()
