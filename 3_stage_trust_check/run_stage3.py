"""Stage 3: decide which relaxed structures the machine-learning model can be trusted on.

Idea: ask several models ("the committee") about the same relaxed structure. Where they agree,
the result is Trusted. Where they disagree, or the structure looks physically odd, it Needs DFT.

Run (settings come from ../config.toml; command-line options override them):
    ~/miniconda3/envs/osi/bin/python run_stage3.py
    ~/miniconda3/envs/osi/bin/python run_stage3.py --models mace_mp_medium mace_mpa_medium
    ~/miniconda3/envs/osi/bin/python run_stage3.py --input my_relaxed.extxyz

Outputs (in outputs/):
    trust_report.csv    one row per structure: label, reasons, all check values, each model's numbers
    needs_dft.extxyz    structures labelled Needs DFT; stage 4 reads this
    trusted.extxyz      structures labelled Trusted
    trust_plot.png      enthalpy above best vs model disagreement, coloured by label
    run_info.json       the settings used
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
from ase.io import read, write
from ase.units import GPa

STAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from hp_common import get_logger, load_config, save_run_info, stage_dirs  # noqa: E402
from hp_models import load_model  # noqa: E402
from trust_checks import CHECKS, min_bond_ratio  # noqa: E402

DEFAULT_INPUT = PROJECT_ROOT / "2_stage_relax" / "outputs" / "relaxed.extxyz"
TRUSTED, NEEDS_DFT = "Trusted", "Needs DFT"


def evaluate(structures, model_name):
    """Energy per atom, pressure and largest force from one model, for every structure (no relaxing)."""
    calc = load_model(model_name)
    results = []
    for atoms in structures:
        a = atoms.copy()
        a.calc = calc
        stress = a.get_stress()  # ASE sign convention: pressure = -mean of the diagonal
        results.append({
            "energy": a.get_potential_energy() / len(a),
            "pressure": float(-stress[:3].mean() / GPa),
            "max_force": float(np.linalg.norm(a.get_forces(), axis=1).max()),
        })
    return results


def build_records(structures, model_names, per_model):
    """Combine every model's numbers into one record per structure, with the values the checks need."""
    records = []
    for i, atoms in enumerate(structures):
        n = len(atoms)
        p_target = float(atoms.info["pressure_gpa"])
        volume = atoms.get_volume() / n
        records.append({
            "id": atoms.info["id"],
            "pressure_GPa": p_target,
            "status": atoms.info.get("status", "ok"),
            "volume_A3_per_atom": volume,
            "min_bond_ratio": min_bond_ratio(atoms),
            "relaxer_enthalpy": float(atoms.info["enthalpy_eV_per_atom"]),
            # Same geometry, same target pressure: H = E + PV for each model.
            "H": {m: per_model[m][i]["energy"] + p_target * GPa * volume for m in model_names},
            "P": {m: per_model[m][i]["pressure"] for m in model_names},
            "F": {m: per_model[m][i]["max_force"] for m in model_names},
        })

    for p in sorted({r["pressure_GPa"] for r in records}):
        group = [r for r in records if r["pressure_GPa"] == p]
        ok = [r for r in group if r["status"] == "ok"] or group
        best = min(r["relaxer_enthalpy"] for r in ok)
        median_volume = float(np.median([r["volume_A3_per_atom"] for r in ok]))
        # Each model has its own energy zero, so compare enthalpies after removing each
        # model's median over the structures. What is left is each model's ranking.
        offset = {m: float(np.median([r["H"][m] for r in ok])) for m in model_names}
        for r in group:
            rel = [1000 * (r["H"][m] - offset[m]) for m in model_names]
            r["H_rel_meV"] = dict(zip(model_names, rel))
            r["enthalpy_spread_meV"] = max(rel) - min(rel)
            r["max_pressure_dev_GPa"] = max(abs(r["P"][m] - p) for m in model_names)
            r["max_force_eV_A"] = max(r["F"].values())
            r["volume_vs_median"] = r["volume_A3_per_atom"] / median_volume
            r["dH_meV_per_atom"] = 1000 * (r["relaxer_enthalpy"] - best)
    return records


def make_plot(records, settings, path):
    """Enthalpy above the best structure vs model disagreement, one point per structure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid, surface = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
    styles = {TRUSTED: ("#0072B2", "o"), NEEDS_DFT: ("#E69F00", "^")}  # status colours + distinct shapes

    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=surface)
    ax.set_facecolor(surface)
    for label, (color, marker) in styles.items():
        pts = [r for r in records if r["label"] == label]
        if pts:
            ax.scatter([r["dH_meV_per_atom"] for r in pts], [r["enthalpy_spread_meV"] for r in pts],
                       s=70, c=color, marker=marker, edgecolors=surface, linewidths=1.5,
                       label=f"{label} ({len(pts)})", zorder=3, clip_on=False)
    # Label only the flagged structures that matter (close to the best, or wildly off), and merge
    # labels of points that sit on top of each other, so the plot stays readable.
    limit = settings["max_enthalpy_spread_meV"]
    to_label = sorted((r for r in records if r["label"] == NEEDS_DFT and
                       (r["dft_priority"] == "high" or r["enthalpy_spread_meV"] > 100 * limit)),
                      key=lambda r: (r["dH_meV_per_atom"], r["enthalpy_spread_meV"]))
    groups = []
    for r in to_label:
        x, y = np.log10(r["dH_meV_per_atom"] + 10), np.log10(r["enthalpy_spread_meV"] + 5)
        if groups and abs(groups[-1]["x"] - x) < 0.05 and abs(groups[-1]["y"] - y) < 0.1:
            groups[-1]["ids"].append(r["id"])
        else:
            groups.append({"x": x, "y": y, "ids": [r["id"]], "r": r})
    for g in groups:
        ax.annotate(", ".join(g["ids"]), (g["r"]["dH_meV_per_atom"], g["r"]["enthalpy_spread_meV"]),
                    xytext=(6, 5), textcoords="offset points", fontsize=8, color=ink)
    ax.axhline(limit, ls="--", lw=1, color=muted, zorder=2)
    ax.text(0.01, limit, f" disagreement limit ({limit:g} meV/atom)", transform=ax.get_yaxis_transform(),
            va="bottom", fontsize=8, color=muted)

    # symlog = linear near zero, logarithmic further out, so 0 and 40,000 fit on one plot.
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yscale("symlog", linthresh=5)
    ax.set_xlim(left=0, right=max(r["dH_meV_per_atom"] for r in records) * 2.5)
    ax.set_ylim(bottom=0, top=max(r["enthalpy_spread_meV"] for r in records) * 3)
    ax.set_xlabel("Enthalpy above best structure (meV/atom)", color=ink)
    ax.set_ylabel("Model disagreement on enthalpy (meV/atom)", color=ink)
    pressures = sorted({r["pressure_GPa"] for r in records})
    ax.set_title(f"Which structures can the ML model be trusted on? ({', '.join(f'{p:g}' for p in pressures)} GPa)",
                 color=ink, fontsize=11, loc="left")
    ax.grid(True, color=grid, lw=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=muted)
    ax.legend(frameon=False, labelcolor=ink, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Stage 3: label relaxed structures Trusted or Needs DFT.")
    parser.add_argument("--config", help="settings file (default: ../config.toml)")
    parser.add_argument("--input", help="relaxed structures file (default: stage 2 output)")
    parser.add_argument("--models", nargs="+", help="committee model names from hp_models.py")
    parser.add_argument("--limits-file", help="per-material limits from calibrate_trust.py (overrides config)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    settings = dict(cfg["stage3"])
    limits_file = args.limits_file or settings.get("limits_file", "")
    limits_note = "limits from config.toml"
    if limits_file:
        # Calibrated limits for this material (from calibrate_trust.py) replace the config limits.
        import tomllib
        from pymatgen.core import Composition
        path = Path(limits_file) if Path(limits_file).is_absolute() else STAGE_DIR / limits_file
        formula = Composition(cfg["project"]["composition"]).reduced_formula
        per_material = tomllib.loads(path.read_text()).get("limits", {})
        if formula in per_material:
            settings.update(per_material[formula])
            limits_note = f"calibrated limits for {formula} from {path.name}"
        else:
            limits_note = f"no calibrated limits for {formula} in {path.name}; using config.toml"
    model_names = args.models or settings["models"]
    input_path = Path(args.input or settings["input"] or DEFAULT_INPUT)
    out_dir, log_dir = stage_dirs(STAGE_DIR)
    log, log_file = get_logger("stage3", log_dir)

    import torch
    torch.set_num_threads(settings["n_threads"])

    structures = read(input_path, index=":")
    log.info("trust limits: %s (spread %.4g meV, pressure %.4g GPa, force %.4g eV/A)", limits_note,
             settings["max_enthalpy_spread_meV"], settings["max_pressure_deviation_gpa"], settings["max_force_eV_A"])
    log.info("Stage 3 start | %d structures from %s | committee: %s | checks: %s",
             len(structures), input_path, ", ".join(model_names), ", ".join(settings["checks"]))

    per_model = {}
    for m in model_names:
        start = time.time()
        per_model[m] = evaluate(structures, m)
        log.info("model %s done in %.1f s", m, time.time() - start)

    records = build_records(structures, model_names, per_model)
    for r in records:
        reasons = [reason for name in settings["checks"] if (reason := CHECKS[name](r, settings))]
        r["label"] = NEEDS_DFT if reasons else TRUSTED
        r["reasons"] = "; ".join(reasons)
        r["dft_priority"] = ("high" if r["dH_meV_per_atom"] <= settings["dft_window_meV"] else "low") \
            if reasons else ""
    records.sort(key=lambda r: (r["pressure_GPa"], r["dH_meV_per_atom"]))

    for r in records:
        log.info("%s | %g GPa | dH %6.1f meV/atom | spread %6.1f meV | dP %5.1f GPa | %-9s %s",
                 r["id"], r["pressure_GPa"], r["dH_meV_per_atom"], r["enthalpy_spread_meV"],
                 r["max_pressure_dev_GPa"], r["label"], f"({r['reasons']})" if r["reasons"] else "")

    # Report: shared columns first, then each model's own numbers.
    fields = ["id", "pressure_GPa", "label", "reasons", "dft_priority", "dH_meV_per_atom",
              "enthalpy_spread_meV", "max_pressure_dev_GPa", "max_force_eV_A", "min_bond_ratio",
              "volume_A3_per_atom", "volume_vs_median", "status"]
    fields += [f"H_rel_meV_{m}" for m in model_names] + [f"P_GPa_{m}" for m in model_names]
    with open(out_dir / "trust_report.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            row = {k: r[k] for k in fields if k in r}
            row.update({f"H_rel_meV_{m}": r["H_rel_meV"][m] for m in model_names})
            row.update({f"P_GPa_{m}": r["P"][m] for m in model_names})
            writer.writerow({k: round(v, 3) if isinstance(v, float) else v for k, v in row.items()})

    # Structure files for the next stage, rewritten from scratch every run.
    by_id = {(a.info["id"], float(a.info["pressure_gpa"])): a for a in structures}
    for label, name in ((NEEDS_DFT, "needs_dft.extxyz"), (TRUSTED, "trusted.extxyz")):
        (out_dir / name).unlink(missing_ok=True)
        chosen = []
        for r in records:
            if r["label"] == label:
                atoms = by_id[(r["id"], r["pressure_GPa"])]
                atoms.info.update(label=label, reasons=r["reasons"] or "none",
                                  dft_priority=r["dft_priority"] or "none")
                chosen.append(atoms)
        if chosen:
            write(out_dir / name, chosen)

    if settings["make_plot"]:
        make_plot(records, settings, out_dir / "trust_plot.png")

    counts = {TRUSTED: sum(r["label"] == TRUSTED for r in records),
              NEEDS_DFT: sum(r["label"] == NEEDS_DFT for r in records),
              "needs_dft_high_priority": sum(r["dft_priority"] == "high" for r in records)}
    save_run_info(out_dir, {"stage": 3, "config": cfg, "input": input_path, "models": model_names,
                            "counts": counts, "log_file": log_file})
    log.info("Stage 3 done | %s | outputs in %s", counts, out_dir)


if __name__ == "__main__":
    main()
