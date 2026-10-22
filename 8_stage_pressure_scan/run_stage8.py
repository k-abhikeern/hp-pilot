"""Stage 8: enthalpy vs pressure for the best phases of one material, and the 0 K transition pressure.

Takes the most stable phases found for a material (stage 7 campaign), relaxes each at a list of pressures
with the ML model (seconds) and with DFT (SLURM jobs, built by stage 4's tools), then plots
    dH(P) = H(phase) - H(reference phase)
and finds where the lines cross: the transition pressure at 0 K (no temperature or zero-point effects).

    ~/miniconda3/envs/osi/bin/python run_stage8.py submit                       # settings from [stage8]
    ~/miniconda3/envs/osi/bin/python run_stage8.py submit --campaign NaCl_40GPa --pressures 10 20 30 40 50
    ~/miniconda3/envs/osi/bin/python run_stage8.py submit --dry-run             # build everything, submit nothing
    ~/miniconda3/envs/osi/bin/python run_stage8.py collect                      # newest scan: plot + transition
    ~/miniconda3/envs/osi/bin/python run_stage8.py collect --scan runs/scan_<label>_<date>_<time>

Outputs:
    runs/scan_<label>_<date>_<time>/   calcs/ (VASP), jobs/ (SLURM), ml_results.csv, scan_state.json
    outputs/enthalpy_vs_pressure_<label>.png   dH vs P, DFT (solid) and ML (dashed)
    outputs/scan_<label>.csv                   one row per phase and pressure
    outputs/transition_<label>.md              transition pressures from DFT and from ML
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

STAGE_DIR = Path(__file__).resolve().parent
ROOT = STAGE_DIR.parent
for sub in ("", "2_stage_relax", "4_stage_incar_build", "5_stage_vasp_run"):
    sys.path.insert(0, str(ROOT / sub))
from hp_common import get_logger, load_config, stage_dirs  # noqa: E402

CAMPAIGNS = ROOT / "7_stage_compare_materials" / "campaigns"
PHASES = ROOT / "7_stage_compare_materials" / "outputs"
RUNS = STAGE_DIR / "runs"
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#a35bd1"]  # categorical slots 1-4, assigned in fixed order
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"


def safe(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "", text.replace("/", "-"))


def pick_phases(campaign, n_phases, log):
    """The n most stable distinct phases in DFT (from stage 7), each with its DFT-relaxed structure."""
    from ase.io import read
    rows = list(csv.DictReader(open(PHASES / f"phases_{campaign}.csv")))[:n_phases]
    phases = []
    for r in rows:
        first = r["structures"].split()[0]
        pressure = float(re.search(r"_(\d+(?:\.\d+)?)GPa", campaign).group(1))
        contcar = CAMPAIGNS / campaign / "dft" / f"CONTCAR_{first}_{pressure:g}GPa"
        phases.append({"name": r["name"], "space_group": r["space_group"],
                       "tag": safe(f"{r['name']}_{r['space_group']}"), "atoms": read(contcar)})
        log.info("phase %s (%s): start from DFT structure %s", r["name"], r["space_group"], contcar.name)
    return phases


def submit(args, cfg, log):
    from ase.io import write
    from pymatgen.core import SETTINGS
    from hp_models import load_model
    from run_stage2 import relax
    import run_stage4 as s4

    settings = cfg["stage8"]
    campaign = args.campaign or settings["campaign"]
    pressures = args.pressures or settings["pressures_gpa"]
    profile = args.profile or settings["profile"]
    scan_dir = RUNS / f"scan_{campaign}_{time.strftime('%Y%m%d_%H%M%S')}"
    (scan_dir / "calcs").mkdir(parents=True)
    (scan_dir / "jobs").mkdir()
    SETTINGS["PMG_VASP_PSP_DIR"] = str((ROOT / "4_stage_incar_build" / cfg["stage4"]["potcar_dir"]).resolve())

    phases = pick_phases(campaign, args.n_phases or settings["n_phases"], log)
    log.info("Stage 8 start | %s | phases %s | pressures %s GPa | profile %s", campaign,
             [p["name"] for p in phases], pressures, profile)

    # ML: relax each phase at each pressure (seconds); its structure is also the DFT starting point.
    import torch
    torch.set_num_threads(cfg["stage2"]["n_threads"])
    calc = load_model(cfg["stage2"]["model"])
    ml_rows, calcs = [], []
    for ph in phases:
        for p in pressures:
            atoms, res = relax(ph["atoms"], calc, p, cfg["stage2"])
            ml_rows.append({"phase": ph["name"], "space_group": ph["space_group"], "pressure_GPa": p,
                            "ml_enthalpy_eV_per_atom": res["enthalpy_eV_per_atom"], "ml_status": res["status"]})
            atoms.info.update(id=ph["tag"], label="scan", model=cfg["stage2"]["model"])
            summary, _ = s4.build_input(atoms, profile, cfg["stage4"]["checks"],
                                        scan_dir / "calcs" / f"{ph['tag']}_{p:g}GPa")
            if not summary["checks_passed"]:
                log.warning("%s at %g GPa failed input checks: %s", ph["name"], p, summary["check_failures"])
                continue
            calcs.append(summary)
            log.info("%-12s %5.1f GPa | ML H %.4f eV/atom (%s) | DFT input ENCUT %d, k %s", ph["name"], p,
                     res["enthalpy_eV_per_atom"], res["status"], summary["ENCUT"], summary["kpoint_grid"])
    with open(scan_dir / "ml_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ml_rows[0].keys())
        w.writeheader()
        w.writerows(ml_rows)

    # DFT: one SLURM job per pressure (calculations of one pressure run one after another).
    plan_settings = {**cfg["stage4"], "n_batches": len(pressures)}
    batches, cores, why = s4.plan_batches(calcs, plan_settings, s4.cluster_status(cfg["stage4"]["partition"]))
    plan = s4.write_jobs(batches, cores, plan_settings, scan_dir / "jobs")
    for line in why:
        log.info("plan: %s", line)
    jobs = []
    for job in plan:
        if args.dry_run:
            log.info("DRY RUN: would submit %s: %s", job["script"], ", ".join(job["calcs"]))
            continue
        out = subprocess.run(["sbatch", job["script"]], cwd=scan_dir / "jobs", capture_output=True, text=True)
        match = re.search(r"Submitted batch job (\d+)", out.stdout)
        if match:
            jobs.append({**job, "job_id": match.group(1)})
            log.info("submitted %s as job %s: %s", job["script"], match.group(1), ", ".join(job["calcs"]))
        else:
            log.error("sbatch failed for %s: %s", job["script"], (out.stderr or out.stdout).strip())
    state = {"campaign": campaign, "pressures_gpa": pressures, "profile": profile,
             "phases": [{k: v for k, v in p.items() if k != "atoms"} for p in phases], "jobs": jobs,
             "dry_run": args.dry_run, "submitted": time.strftime("%Y-%m-%d %H:%M:%S")}
    (scan_dir / "scan_state.json").write_text(json.dumps(state, indent=2))
    log.info("Stage 8 submit done | %d DFT calculations in %d job(s) | %s", len(calcs), len(jobs), scan_dir)


def crossings(pressures, dh):
    """Pressures where dH changes sign (linear interpolation between neighbouring points)."""
    out = []
    for (p1, h1), (p2, h2) in zip(zip(pressures, dh), zip(pressures[1:], dh[1:])):
        if h1 == 0 or np.sign(h1) != np.sign(h2):
            out.append(p1 if h1 == 0 else p1 + (p2 - p1) * h1 / (h1 - h2))
    return out


def collect(args, log, out_dir):
    from run_stage5 import read_calc
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scan_dir = Path(args.scan) if args.scan else sorted(RUNS.glob("scan_*"))[-1]
    state = json.loads((scan_dir / "scan_state.json").read_text())
    campaign, pressures, phases = state["campaign"], state["pressures_gpa"], state["phases"]
    ml = {(r["phase"], float(r["pressure_GPa"])): float(r["ml_enthalpy_eV_per_atom"])
          for r in csv.DictReader(open(scan_dir / "ml_results.csv"))}
    dft, status = {}, {}
    for ph in phases:
        for p in pressures:
            r = read_calc(scan_dir / "calcs" / f"{ph['tag']}_{p:g}GPa")
            status[(ph["name"], p)] = r["dft_status"]
            if "dft_enthalpy_eV_per_atom" in r:
                dft[(ph["name"], p)] = (r["dft_enthalpy_eV_per_atom"], r["dft_space_group"], r["dft_pressure_GPa"])
    missing = [k for k in status if k not in dft]
    if missing:
        log.warning("no DFT result yet for %s", missing)

    # Reference = the phase with the lowest DFT enthalpy at the lowest pressure.
    p0 = min(pressures)
    ref = min(phases, key=lambda ph: dft.get((ph["name"], p0), (np.inf,))[0])["name"]
    rows, lines = [], [f"# Transition pressures: {campaign} (0 K, {state['profile']} DFT)", "",
                       f"Reference phase: **{ref}** (most stable at {p0:g} GPa). dH = H(phase) - H({ref}).", "",
                       "| Phase | DFT transition from " + ref + " (GPa) | ML transition (GPa) |", "|---|---|---|"]
    fig, ax = plt.subplots(figsize=(7, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.axhline(0, color=MUTED, lw=1)
    for i, ph in enumerate(phases):
        color = COLORS[i % len(COLORS)]
        ps = [p for p in pressures if (ph["name"], p) in dft and (ref, p) in dft]
        dh_dft = [1000 * (dft[(ph["name"], p)][0] - dft[(ref, p)][0]) for p in ps]
        dh_ml = [1000 * (ml[(ph["name"], p)] - ml[(ref, p)]) for p in pressures]
        for p, d, m in zip(pressures, [dict(zip(ps, dh_dft)).get(p) for p in pressures], dh_ml):
            rows.append({"phase": ph["name"], "space_group": ph["space_group"], "pressure_GPa": p,
                         "dft_dH_meV_per_atom": None if d is None else round(d, 1),
                         "ml_dH_meV_per_atom": round(m, 1),
                         "dft_space_group_after": dft.get((ph["name"], p), (None, "-"))[1],
                         "dft_status": status.get((ph["name"], p), "-")})
        label = f"{ph['name']} ({ph['space_group']})"
        ax.plot(ps, dh_dft, "-o", color=color, lw=2, ms=6, label=f"{label}, DFT", zorder=3, clip_on=False)
        ax.plot(pressures, dh_ml, "--o", color=color, lw=1.4, ms=5, mfc=SURFACE, label=f"{label}, ML",
                zorder=2, clip_on=False)
        if ph["name"] == ref:
            continue
        t_dft, t_ml = crossings(ps, dh_dft), crossings(pressures, dh_ml)
        lines.append(f"| {label} | {', '.join(f'{t:.1f}' for t in t_dft) or 'no crossing in range'} | "
                     f"{', '.join(f'{t:.1f}' for t in t_ml) or 'no crossing in range'} |")
        for t in t_dft:
            ax.axvline(t, color=color, lw=1, ls=":")
            ax.text(t, 0.97, f" transition {t:.1f} GPa (DFT)", color=INK, fontsize=8, va="top",
                    transform=ax.get_xaxis_transform())
        log.info("%s vs %s: DFT transition %s GPa | ML transition %s GPa", ph["name"], ref,
                 [round(t, 1) for t in t_dft] or "none in range", [round(t, 1) for t in t_ml] or "none in range")
    ax.set_xlabel("Pressure (GPa)", color=INK)
    ax.set_ylabel(f"H − H({ref}) (meV/atom)", color=INK)
    ax.set_title(f"{campaign.split('_')[0]}: enthalpy vs pressure (0 K, {state['profile']} DFT)",
                 loc="left", fontsize=11, color=INK)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out_dir / f"enthalpy_vs_pressure_{campaign}.png", dpi=200, facecolor=SURFACE)
    plt.close(fig)

    with open(out_dir / f"scan_{campaign}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    lines += ["", f"DFT status per calculation: {sum(s == 'converged' for s in status.values())} converged of "
              f"{len(status)}.", "", "0 K means no temperature or zero-point effects; quick DFT settings, so "
              "treat this as a rough estimate (a few GPa)."]
    (out_dir / f"transition_{campaign}.md").write_text("\n".join(lines) + "\n")
    log.info("Stage 8 collect done | outputs in %s", out_dir)


def main():
    parser = argparse.ArgumentParser(description="Stage 8: enthalpy vs pressure and transition pressure.")
    parser.add_argument("command", choices=["submit", "collect"])
    parser.add_argument("--config", help="settings file (default: ../config.toml)")
    parser.add_argument("--campaign", help="stage 7 campaign, e.g. NaCl_40GPa")
    parser.add_argument("--pressures", type=float, nargs="+", help="pressures in GPa")
    parser.add_argument("--n-phases", type=int, help="how many of the most stable phases to scan")
    parser.add_argument("--profile", help="DFT accuracy profile (quick or standard)")
    parser.add_argument("--dry-run", action="store_true", help="submit: build inputs but send nothing")
    parser.add_argument("--scan", help="collect: scan folder (default: newest)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    out_dir, log_dir = stage_dirs(STAGE_DIR)
    RUNS.mkdir(exist_ok=True)
    log, _ = get_logger(f"stage8_{args.command}", log_dir)
    submit(args, cfg, log) if args.command == "submit" else collect(args, log, out_dir)


if __name__ == "__main__":
    main()
