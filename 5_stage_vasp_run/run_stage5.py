"""Stage 5: run the VASP jobs planned in stage 4, then read and compare the results.

Three commands:
    ~/miniconda3/envs/osi/bin/python run_stage5.py submit             # copy stage 4 inputs to a new run folder, sbatch
    ~/miniconda3/envs/osi/bin/python run_stage5.py submit --dry-run   # same, but only show what would be submitted
    ~/miniconda3/envs/osi/bin/python run_stage5.py status             # how are the jobs doing?
    ~/miniconda3/envs/osi/bin/python run_stage5.py collect            # read finished results, compare DFT with ML

status and collect use the newest run folder unless you give  --run runs/run_<date>_<time>.

Outputs:
    runs/run_<date>_<time>/calcs/, jobs/   the copied inputs; VASP writes its files here
    runs/run_<date>_<time>/run_state.json  SLURM job ids and submission time
    outputs/dft_results.csv                one row per calculation: DFT enthalpy, pressure, symmetry, ML values
    outputs/dft_vs_ml.png                  DFT vs ML relative enthalpy, coloured by trust label
    outputs/run_info.json                  which run was collected
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from hp_common import get_logger, load_config, save_run_info, stage_dirs  # noqa: E402

STAGE4_OUT = PROJECT_ROOT / "4_stage_incar_build" / "outputs"
RUNS_DIR = STAGE_DIR / "runs"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
STYLES = {"Trusted": ("#0ca30c", "o"), "Needs DFT": ("#d03b3b", "^")}
EV_PER_A3_PER_KBAR = 1 / 1602.1766  # 1 eV/A^3 = 1602.18 kBar


def latest_run():
    runs = sorted(RUNS_DIR.glob("run_*"))
    if not runs:
        sys.exit("No run folders yet. Run:  run_stage5.py submit")
    return runs[-1]


# ---------- submit ----------

def submit(args, log):
    plan = json.loads((STAGE4_OUT / "job_plan.json").read_text())
    run_dir = RUNS_DIR / time.strftime("run_%Y%m%d_%H%M%S")
    for part in ("calcs", "jobs"):
        shutil.copytree(STAGE4_OUT / part, run_dir / part)
    shutil.copy(STAGE4_OUT / "job_plan.md", run_dir / "job_plan.md")
    log.info("copied stage 4 inputs to %s", run_dir)

    jobs = []
    for job in plan["jobs"]:
        if args.dry_run:
            log.info("DRY RUN: would submit %s (%d cores): %s", job["script"], job["cores"], ", ".join(job["calcs"]))
            continue
        result = subprocess.run(["sbatch", job["script"]], cwd=run_dir / "jobs",
                                capture_output=True, text=True, timeout=60)
        match = re.search(r"Submitted batch job (\d+)", result.stdout)
        if not match:
            log.error("sbatch failed for %s: %s", job["script"], (result.stderr or result.stdout).strip())
            continue
        jobs.append({**job, "job_id": match.group(1)})
        log.info("submitted %s as job %s (%d cores): %s", job["script"], match.group(1), job["cores"],
                 ", ".join(job["calcs"]))

    with open(run_dir / "run_state.json", "w") as f:
        json.dump({"submitted": time.strftime("%Y-%m-%d %H:%M:%S"), "dry_run": args.dry_run,
                   "profile": plan["profile"], "jobs": jobs}, f, indent=2)
    log.info("Stage 5 submit done | %d job(s) | run folder %s", len(jobs), run_dir)


# ---------- status ----------

def job_states(job_ids):
    """SLURM state of each job: from squeue while running, from sacct once finished."""
    states = {}
    out = subprocess.run(["squeue", "-h", "-j", ",".join(job_ids), "-o", "%i %T %M"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        jid, state, elapsed = line.split()
        states[jid] = f"{state} ({elapsed})"
    for jid in set(job_ids) - set(states):
        out = subprocess.run(["sacct", "-n", "-X", "-P", "-j", jid, "-o", "State,Elapsed"],
                             capture_output=True, text=True).stdout.strip()
        states[jid] = out.replace("|", " (") + ")" if out else "unknown"
    return states


def status(args, log):
    run_dir = Path(args.run) if args.run else latest_run()
    state = json.loads((run_dir / "run_state.json").read_text())
    states = job_states([j["job_id"] for j in state["jobs"]]) if state["jobs"] else {}
    log.info("run %s (submitted %s)", run_dir.name, state["submitted"])
    for job in state["jobs"]:
        log.info("job %s %-22s %s", job["job_id"], states.get(job["job_id"], "?"), ", ".join(job["calcs"]))
        for name in job["calcs"]:
            status_file = run_dir / "calcs" / name / "status.txt"
            text = status_file.read_text().replace("\n", " ").strip() if status_file.exists() else "not started"
            log.info("    %s: %s", name, text)


# ---------- collect ----------

def read_calc(calc_dir):
    """Read one finished VASP relaxation with pymatgen. Returns a dict, or None if there is no result."""
    from pymatgen.io.vasp import Vasprun
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

    meta = json.loads((calc_dir / "meta.json").read_text())
    row = {k: meta[k] for k in ("name", "id", "pressure_GPa", "label", "space_group", "ml_enthalpy_eV_per_atom")}
    row["formula"] = meta.get("formula", "")
    row["ml_space_group"] = row.pop("space_group")
    if not (calc_dir / "vasprun.xml").exists():
        return {**row, "dft_status": "no vasprun.xml"}
    try:
        vr = Vasprun(calc_dir / "vasprun.xml", parse_dos=False, parse_eigen=False, parse_potcar_file=False)
    except Exception as err:
        return {**row, "dft_status": f"unreadable ({str(err)[:60]})"}

    final = vr.ionic_steps[-1]
    structure = vr.final_structure
    n = len(structure)
    volume = structure.volume / n
    # With PSTRESS set, VASP adds PSTRESS x V to the energies it writes, so e_0_energy is already the
    # enthalpy H = E + PV (checked against OUTCAR). Take PV off again to get the plain energy.
    enthalpy = final["e_0_energy"] / n
    energy = enthalpy - 10 * row["pressure_GPa"] * EV_PER_A3_PER_KBAR * volume
    # VASP's stress tensor (kBar) is the full pressure on the cell; converged runs sit near the target.
    pressure_gpa = sum(final["stress"][i][i] for i in range(3)) / 3 / 10
    try:
        sg = SpacegroupAnalyzer(structure, symprec=0.1).get_space_group_symbol()
    except Exception:
        sg = "?"
    return {**row,
            "dft_status": "converged" if vr.converged else "not converged",
            "ionic_steps": len(vr.ionic_steps),
            "dft_space_group": sg,
            "dft_energy_eV_per_atom": energy,
            "dft_enthalpy_eV_per_atom": enthalpy,
            "dft_volume_A3_per_atom": volume,
            "dft_pressure_GPa": pressure_gpa}


def plot_dft_vs_ml(rows, path):
    """Each structure's enthalpy relative to the best, from DFT (up) and from the ML model (across).
    Points on the diagonal: the ML model ranked them right. Far from it: the ML model was wrong."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    good = [r for r in rows if "dft_enthalpy_eV_per_atom" in r]
    ml0 = min(r["ml_enthalpy_eV_per_atom"] for r in good)
    dft0 = min(r["dft_enthalpy_eV_per_atom"] for r in good)
    for r in good:
        r["ml_dH_meV"] = 1000 * (r["ml_enthalpy_eV_per_atom"] - ml0)
        r["dft_dH_meV"] = 1000 * (r["dft_enthalpy_eV_per_atom"] - dft0)
    top = max(max(r["ml_dH_meV"], r["dft_dH_meV"]) for r in good) * 1.15 + 5

    fig, ax = plt.subplots(figsize=(5.5, 5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.plot([0, top], [0, top], ls="--", lw=1, color=MUTED, zorder=1)
    ax.text(top * 1.05, top * 1.2, "ML = DFT", color=MUTED, fontsize=8, ha="left", va="top", rotation=45,
            rotation_mode="anchor", transform_rotates_text=True)
    for label, (color, marker) in STYLES.items():
        pts = [r for r in good if r["label"] == label]
        if pts:
            ax.scatter([r["ml_dH_meV"] for r in pts], [r["dft_dH_meV"] for r in pts], s=80, c=color,
                       marker=marker, edgecolors=SURFACE, linewidths=1.5, label=label, zorder=3, clip_on=False)
    # Group points that sit close together (on the log-style axes), and label only the groups that
    # matter: the most stable structures and the big ML misses (> 50 meV/atom). Keeps the plot readable.
    def pos(v):
        return np.log10(v + 10)
    groups = []
    for r in sorted(good, key=lambda r: (r["ml_dH_meV"], r["dft_dH_meV"])):
        g = next((g for g in groups if abs(g["x"] - pos(r["ml_dH_meV"])) < 0.08
                  and abs(g["y"] - pos(r["dft_dH_meV"])) < 0.08), None)
        if g:
            g["rows"].append(r)
        else:
            groups.append({"x": pos(r["ml_dH_meV"]), "y": pos(r["dft_dH_meV"]), "rows": [r]})
    for g in groups:
        rs = g["rows"]
        best = any(r["dft_dH_meV"] < 5 or r["ml_dH_meV"] < 5 for r in rs)
        miss = max(abs(r["dft_dH_meV"] - r["ml_dH_meV"]) for r in rs) > 50
        if not (best or miss):
            continue
        sgs = sorted({r["dft_space_group"] for r in rs})
        labels = {r["label"] for r in rs}
        who = f"{len(rs)} {labels.pop()}" if len(rs) > 3 and len(labels) == 1 else ", ".join(r["id"] for r in rs)
        anchor = min(rs, key=lambda r: r["dft_dH_meV"])
        ax.annotate(f"{who} ({', '.join(sgs)})", (anchor["ml_dH_meV"], anchor["dft_dH_meV"]),
                    xytext=(7, -3), textcoords="offset points", fontsize=8, color=INK)
    # symlog = linear near zero, logarithmic further out, so 0 and 900 meV fit on one plot.
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yscale("symlog", linthresh=10)
    ax.set_xlim(0, top * 1.5)
    ax.set_ylim(0, top * 1.5)
    ax.set_xlabel("ML enthalpy above best (meV/atom)", color=INK)
    ax.set_ylabel("DFT enthalpy above best (meV/atom)", color=INK)
    pressures = ", ".join(f"{p:g}" for p in sorted({r["pressure_GPa"] for r in good}))
    ax.set_title(f"Does DFT agree with the ML ranking? ({pressures} GPa)", loc="left", fontsize=11, color=INK)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, labelcolor=INK, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def collect(args, log, out_dir):
    run_dir = Path(args.run) if args.run else latest_run()
    rows = [read_calc(d) for d in sorted((run_dir / "calcs").iterdir()) if d.is_dir()]
    for r in rows:
        if "dft_enthalpy_eV_per_atom" in r:
            log.info("%s | %-13s | %2d steps | %s -> %s | H %.4f eV/atom | DFT pressure %.2f GPa",
                     r["name"], r["dft_status"], r["ionic_steps"], r["ml_space_group"], r["dft_space_group"],
                     r["dft_enthalpy_eV_per_atom"], r["dft_pressure_GPa"])
        else:
            log.warning("%s | %s", r["name"], r["dft_status"])

    fields = ["name", "id", "pressure_GPa", "label", "dft_status", "ionic_steps", "ml_space_group",
              "dft_space_group", "ml_enthalpy_eV_per_atom", "dft_enthalpy_eV_per_atom",
              "dft_energy_eV_per_atom", "dft_volume_A3_per_atom", "dft_pressure_GPa", "ml_dH_meV", "dft_dH_meV"]
    finished = [r for r in rows if "dft_enthalpy_eV_per_atom" in r]
    if len(finished) >= 2:
        plot_dft_vs_ml(finished, out_dir / "dft_vs_ml.png")
        best_dft = min(finished, key=lambda r: r["dft_enthalpy_eV_per_atom"])
        best_ml = min(finished, key=lambda r: r["ml_enthalpy_eV_per_atom"])
        log.info("Most stable in DFT: %s (%s). Most stable in ML: %s. %s", best_dft["id"],
                 best_dft["dft_space_group"], best_ml["id"],
                 "They agree." if best_dft["id"] == best_ml["id"] else "They DISAGREE.")
    with open(out_dir / "dft_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()})
    save_run_info(out_dir, {"stage": 5, "run": run_dir, "n_calcs": len(rows), "n_finished": len(finished)})
    log.info("Stage 5 collect done | %d of %d finished | outputs in %s", len(finished), len(rows), out_dir)


def main():
    parser = argparse.ArgumentParser(description="Stage 5: submit VASP jobs, check them, collect results.")
    parser.add_argument("command", choices=["submit", "status", "collect"])
    parser.add_argument("--run", help="run folder for status/collect (default: newest)")
    parser.add_argument("--dry-run", action="store_true", help="submit: only show what would be submitted")
    parser.add_argument("--config", help="settings file (default: ../config.toml)")
    args = parser.parse_args()

    load_config(args.config)  # not used yet; keeps the same interface as the other stages
    out_dir, log_dir = stage_dirs(STAGE_DIR)
    RUNS_DIR.mkdir(exist_ok=True)
    log, _ = get_logger(f"stage5_{args.command}", log_dir)
    {"submit": lambda: submit(args, log),
     "status": lambda: status(args, log),
     "collect": lambda: collect(args, log, out_dir)}[args.command]()


if __name__ == "__main__":
    main()
