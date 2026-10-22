"""Calibrate the stage 3 trust limits on DFT results (from the stage 7 campaigns).

For every structure that has DFT, we know (a) the trust signals stage 3 computed and (b) how wrong the ML model
really was: error = |DFT enthalpy above best - ML enthalpy above best|. ML is "wrong" if error > --error-limit.
For each signal we try every possible limit ("Needs DFT if signal > limit") and keep the one that best separates
wrong from right (balanced accuracy = average of: share of wrong ones caught, share of right ones trusted).

    ~/miniconda3/envs/osi/bin/python calibrate_trust.py                 # all campaigns with DFT
    ~/miniconda3/envs/osi/bin/python calibrate_trust.py --error-limit 30

Outputs (in calibration/):
    calibrated_limits.toml   limits per material; set  limits_file = "calibration/calibrated_limits.toml"  in [stage3]
    calibration_report.md    how well each signal predicts the ML error, before and after calibration
    calibration.png          per material: model disagreement vs real ML error, with old and new limits

Caution: the limits are fitted on the same structures they are tested on (few structures per material), so they
show what the signals CAN do, not how well they will work on new materials.
"""
import argparse
import csv
import sys
import tomllib
from pathlib import Path

import numpy as np

STAGE_DIR = Path(__file__).resolve().parent
ROOT = STAGE_DIR.parent
CAMPAIGNS = ROOT / "7_stage_compare_materials" / "campaigns"
# signal column in trust_report.csv -> its limit name in [stage3] of config.toml
SIGNALS = {"enthalpy_spread_meV": "max_enthalpy_spread_meV",
           "max_pressure_dev_GPa": "max_pressure_deviation_gpa",
           "max_force_eV_A": "max_force_eV_A"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
WRONG, RIGHT = "#E69F00", "#0072B2"


def load(folder):
    """Trust signals and real ML error for every converged DFT structure of one campaign."""
    trust = {r["id"]: r for r in csv.DictReader(open(folder / "trust_report.csv"))}
    dft = [r for r in csv.DictReader(open(folder / "dft" / "dft_results.csv"))
           if r.get("dft_status") == "converged" and r["id"] in trust]
    ml0 = min(float(r["ml_enthalpy_eV_per_atom"]) for r in dft)
    dft0 = min(float(r["dft_enthalpy_eV_per_atom"]) for r in dft)
    rows = []
    for r in dft:
        t = trust[r["id"]]
        err = abs(1000 * (float(r["dft_enthalpy_eV_per_atom"]) - dft0) - 1000 * (float(r["ml_enthalpy_eV_per_atom"]) - ml0))
        rows.append({"id": r["id"], "error": err, **{s: float(t[s]) for s in SIGNALS}})
    cfg = tomllib.loads((folder / "last_run_config.toml").read_text())
    return cfg["project"]["composition"], rows


def score(rows, flags, error_limit):
    wrong = np.array([r["error"] > error_limit for r in rows])
    flags = np.array(flags)
    tp, fn = int((flags & wrong).sum()), int((~flags & wrong).sum())
    fp, tn = int((flags & ~wrong).sum()), int((~flags & ~wrong).sum())
    caught = tp / (tp + fn) if tp + fn else None      # share of wrong ML results sent to DFT
    trusted = tn / (tn + fp) if tn + fp else None     # share of right ML results trusted
    parts = [x for x in (caught, trusted) if x is not None]
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "caught": caught, "trusted": trusted,
            "balanced": float(np.mean(parts)) if parts else None}


def best_limit(rows, signal, error_limit):
    """Limit on one signal that best separates wrong from right ML results."""
    values = sorted({r[signal] for r in rows})
    candidates = [0.0] + [(a + b) / 2 for a, b in zip(values, values[1:])] + [values[-1] * 1.01 + 1e-9]
    scored = [(score(rows, [r[signal] > c for r in rows], error_limit), c) for c in candidates]
    # Best balanced accuracy; on ties, the lower limit (safer: sends more to DFT).
    return max(scored, key=lambda sc: (sc[0]["balanced"] or 0, -sc[1]))


def fmt(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def main():
    parser = argparse.ArgumentParser(description="Calibrate stage 3 trust limits on DFT results.")
    parser.add_argument("--error-limit", type=float, default=50.0, help="ML error (meV/atom) that counts as wrong")
    args = parser.parse_args()
    out = STAGE_DIR / "calibration"
    out.mkdir(exist_ok=True)
    current = tomllib.loads((ROOT / "config.toml").read_text())["stage3"]

    data = [load(f) for f in sorted(CAMPAIGNS.iterdir()) if (f / "dft" / "dft_results.csv").exists()]
    data.sort(key=lambda d: len(d[0]))
    pooled = [r for _, rows in data for r in rows]
    report = [f"# Trust-limit calibration on DFT results", "",
              f"ML counts as **wrong** when |DFT − ML| enthalpy above best > {args.error_limit:g} meV/atom. "
              "*Caught* = share of wrong ML results sent to DFT; *trusted* = share of right ML results let through. "
              "Limits are fitted and tested on the same structures, so read them as what the signals can do.", ""]
    toml = ["# Trust limits per material, fitted by calibrate_trust.py on DFT results.",
            "# Use with:  limits_file = \"calibration/calibrated_limits.toml\"  in [stage3] of config.toml.", ""]
    results = {}
    for comp, rows in data + [("all materials (one shared limit)", pooled)]:
        n_wrong = sum(r["error"] > args.error_limit for r in rows)
        old = score(rows, [any(r[s] > current[l] for s, l in SIGNALS.items()) for r in rows], args.error_limit)
        report += [f"## {comp}: {len(rows)} structures, {n_wrong} with a wrong ML result", "",
                   f"Current limits (tuned on Si): caught {fmt(old['caught'])}, trusted {fmt(old['trusted'])}.", "",
                   "| Signal | Best limit | Caught | Trusted | Balanced |", "|---|---|---|---|---|"]
        best = {}
        for s, lname in SIGNALS.items():
            sc, lim = best_limit(rows, s, args.error_limit)
            best[lname] = lim
            report.append(f"| {s} | {lim:.3g} | {fmt(sc['caught'])} | {fmt(sc['trusted'])} | {fmt(sc['balanced'])} |")
        new = score(rows, [any(r[s] > best[l] for s, l in SIGNALS.items()) for r in rows], args.error_limit)
        report += ["", f"All three calibrated limits together: caught {fmt(new['caught'])}, "
                   f"trusted {fmt(new['trusted'])}.", ""]
        results[comp] = {"rows": rows, "best": best, "old": old, "new": new}
        print(f"{comp:32s} n={len(rows):2d} wrong={n_wrong:2d} | current: caught {fmt(old['caught'])}, "
              f"trusted {fmt(old['trusted'])} | calibrated: caught {fmt(new['caught'])}, trusted {fmt(new['trusted'])}"
              f" | limits {', '.join(f'{k}={v:.3g}' for k, v in best.items())}")
        if comp in [c for c, _ in data]:
            toml += [f"[limits.{comp}]"] + [f"{k} = {v:.4g}" for k, v in best.items()] + [""]
    (out / "calibration_report.md").write_text("\n".join(report) + "\n")
    (out / "calibrated_limits.toml").write_text("\n".join(toml))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(data), figsize=(4.6 * len(data), 4.2), facecolor=SURFACE, sharey=True)
    for ax, (comp, rows) in zip(np.atleast_1d(axes), data):
        ax.set_facecolor(SURFACE)
        for r in rows:
            wrong = r["error"] > args.error_limit
            ax.scatter(r["enthalpy_spread_meV"], r["error"], s=45, color=WRONG if wrong else RIGHT,
                       marker="^" if wrong else "o", edgecolors=SURFACE, linewidths=1, zorder=3, clip_on=False)
        ax.set_xscale("symlog", linthresh=1)
        ax.set_yscale("symlog", linthresh=10)
        ax.set_xlim(0, max(r["enthalpy_spread_meV"] for r in rows) * 2)
        ax.set_ylim(0, max(max(r["error"] for r in rows) for _, rows in data) * 2)
        cut, old_cut = results[comp]["best"]["max_enthalpy_spread_meV"], current["max_enthalpy_spread_meV"]
        xmax = ax.get_xlim()[1]
        # Shaded regions: left of the calibrated limit = trusted, right of it = send to DFT (this rule only).
        ax.axvspan(0, cut, color=RIGHT, alpha=0.08, lw=0, zorder=0)
        ax.axvspan(cut, xmax, color=WRONG, alpha=0.08, lw=0, zorder=0)
        if cut > 0:
            ax.text(0.02, 0.03, "trusted\n(no DFT)", transform=ax.transAxes, fontsize=7.5, color=RIGHT, va="bottom")
        ax.text(0.98, 0.03, "send to\nDFT", transform=ax.transAxes, fontsize=7.5, color=WRONG, ha="right", va="bottom")
        ax.axhline(args.error_limit, color=MUTED, lw=1, ls="--")
        ax.axvline(old_cut, color=INK, lw=1, ls=":")
        ax.axvline(cut, color=INK, lw=1.4)
        ax.text(old_cut, 0.98, " current limit", transform=ax.get_xaxis_transform(), rotation=90, ha="left",
                va="top", fontsize=7.5, color=INK)
        ax.text(cut, 0.98, "calibrated limit ", transform=ax.get_xaxis_transform(), rotation=90,
                ha="right" if cut > 0.5 * xmax else "left", va="top", fontsize=7.5, color=INK)
        old, new = results[comp]["old"], results[comp]["new"]
        ax.set_title(f"{comp}\nold limits: caught {fmt(old['caught'])}, trusted {fmt(old['trusted'])}\n"
                     f"calibrated: caught {fmt(new['caught'])}, trusted {fmt(new['trusted'])}",
                     loc="left", fontsize=9, color=INK)
        ax.set_xlabel("Model disagreement on enthalpy (meV/atom)", fontsize=9, color=INK)
        ax.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8)
    np.atleast_1d(axes)[0].set_ylabel("Real ML error vs DFT (meV/atom)", color=INK)
    handles = [plt.Line2D([], [], marker="^", ls="", color=WRONG, label=f"ML wrong (> {args.error_limit:g} meV/atom)"),
               plt.Line2D([], [], marker="o", ls="", color=RIGHT, label="ML right"),
               plt.Line2D([], [], color=INK, ls=":", label="current limit (tuned on Si)"),
               plt.Line2D([], [], color=INK, lw=1.4, label="calibrated limit"),
               plt.Rectangle((0, 0), 1, 1, facecolor=RIGHT, alpha=0.2, lw=0, label="trusted by this rule"),
               plt.Rectangle((0, 0), 1, 1, facecolor=WRONG, alpha=0.2, lw=0, label="send to DFT by this rule")]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=8, labelcolor=INK,
               bbox_to_anchor=(0.5, 1.1))
    fig.tight_layout()
    fig.savefig(out / "calibration.png", dpi=200, bbox_inches="tight", facecolor=SURFACE)
    print(f"wrote {out}/calibrated_limits.toml, calibration_report.md, calibration.png")


if __name__ == "__main__":
    main()
