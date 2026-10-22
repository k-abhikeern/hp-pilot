"""Stage 4: build VASP inputs for the structures that need DFT, and plan how to run them.

Run (settings come from ../config.toml; command-line options override them):
    ~/miniconda3/envs/osi/bin/python run_stage4.py
    ~/miniconda3/envs/osi/bin/python run_stage4.py --max-structures 5 --profile standard
    ~/miniconda3/envs/osi/bin/python run_stage4.py --ids s019 s003 --n-batches 1

Outputs (in outputs/):
    calcs/<id>_<P>GPa/     one folder per calculation: INCAR, POSCAR, POTCAR, meta.json
    jobs/batch_NN.slurm    one SLURM job per batch; stage 5 submits these
    job_plan.md            plain-language explanation of how and why jobs were split
    job_plan.json          the same plan, for stage 5
    input_summary.csv      one row per calculation: atoms, ENCUT, k-points, cores, batch, checks
    xrd_patterns.png       simulated X-ray diffraction of each structure (pymatgen)
    job_plan.png           estimated cost of each calculation, grouped by batch
    run_info.json          the settings used

This stage does NOT submit anything. Stage 5 copies calcs/ and jobs/ into its own folder and submits
from there, so rerunning stage 4 can never delete a running calculation.
"""
import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
from ase.io import read
from pymatgen.core import SETTINGS
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.io.vasp.sets import MPRelaxSet
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

STAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from hp_common import get_logger, load_config, save_run_info, stage_dirs  # noqa: E402
from incar_rules import CHECKS, MAGNETIC_ELEMENTS, PROFILES, pressure_settings  # noqa: E402

STAGE3_OUT = PROJECT_ROOT / "3_stage_trust_check" / "outputs"
INK, MUTED, GRID, SURFACE, SERIES = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb", "#2a78d6"
STATUS_COLOR = {"Trusted": "#0ca30c", "Needs DFT": "#d03b3b"}

warnings.filterwarnings("ignore", message=".*POTCAR.*")  # pymatgen warns that our POTCAR copies aren't MP's exact hashes


# ---------- choose structures ----------

def select_structures(settings, input_path, ids, max_structures, log):
    """Pick which structures get DFT: named ids, or the best high-priority Needs DFT ones, plus Trusted controls."""
    needs = read(input_path, index=":") if input_path.exists() else []
    trusted_file = STAGE3_OUT / "trusted.extxyz"
    trusted = read(trusted_file, index=":") if trusted_file.exists() else []

    if ids:
        pool = {a.info["id"]: a for a in needs + trusted}
        missing = [i for i in ids if i not in pool]
        if missing:
            log.warning("ids not found in stage 3 outputs: %s", missing)
        return [pool[i] for i in ids if i in pool]

    # Stage 3 already sorted structures from most to least stable; keep that order, high priority first.
    ordered = [a for a in needs if a.info.get("dft_priority") == "high"] + \
              [a for a in needs if a.info.get("dft_priority") != "high"]
    chosen = ordered[:max_structures] if max_structures > 0 else ordered
    controls = trusted[:settings["trusted_controls"]]
    for a in controls:
        a.info["label"] = "Trusted"
    if controls:
        log.info("adding %d Trusted control(s) %s, to test whether the Trusted label holds up in DFT",
                 len(controls), [a.info["id"] for a in controls])
    return chosen + controls


# ---------- build one input ----------

def kpoint_grid(structure, kspacing):
    """The k-point grid VASP will build from KSPACING (pymatgen's reciprocal lattice already includes 2*pi)."""
    return [max(1, math.ceil(np.linalg.norm(b) / kspacing)) for b in structure.lattice.reciprocal_lattice.matrix]


def auto_cores(n_atoms):
    """Small cells don't get faster on many cores, so use fewer and leave room for other jobs."""
    return 8 if n_atoms <= 8 else 16 if n_atoms <= 32 else 24


def build_input(atoms, profile_name, checks, calc_dir):
    """Write INCAR/POSCAR/POTCAR for one structure and run the hard checks. Returns a summary dict."""
    structure = AseAtomsAdaptor.get_structure(atoms)
    target = float(atoms.info["pressure_gpa"])
    profile = PROFILES[profile_name]
    elements = {str(el) for el in structure.composition.elements}

    incar = {**profile["incar"], **pressure_settings(target)}
    if not elements & MAGNETIC_ELEMENTS:
        incar.update(ISPIN=1, MAGMOM=None)  # no magnetic elements: spin polarization only costs time
    enmax = max(p.enmax for p in MPRelaxSet(structure, user_potcar_functional="PBE").potcar)
    incar["ENCUT"] = round(profile["enmax_factor"] * enmax)

    vis = MPRelaxSet(structure, user_incar_settings=incar, user_potcar_functional="PBE")
    failed = [reason for name in checks
              if (reason := CHECKS[name](vis.incar, vis.potcar, structure, target))]
    vis.write_input(calc_dir)

    grid = kpoint_grid(structure, vis.incar["KSPACING"])
    try:
        sg = SpacegroupAnalyzer(structure, symprec=0.1).get_space_group_symbol()
    except Exception:
        sg = "?"
    summary = {
        "name": calc_dir.name,
        "id": atoms.info["id"],
        "pressure_GPa": target,
        "label": atoms.info.get("label", "Needs DFT"),
        "reasons": atoms.info.get("reasons", ""),
        "ml_model": atoms.info.get("model", ""),
        "ml_enthalpy_eV_per_atom": float(atoms.info["enthalpy_eV_per_atom"]),
        "space_group": sg,
        "n_atoms": len(structure),
        "potcars": " ".join(vis.potcar.symbols),
        "ENCUT": vis.incar["ENCUT"],
        "kpoint_grid": "x".join(map(str, grid)),
        # Rough relative cost: k-points x atoms^2. Only used to balance batches.
        "est_cost": int(np.prod(grid) * len(structure) ** 2),
        "checks_passed": not failed,
        "check_failures": "; ".join(failed),
    }
    with open(calc_dir / "meta.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary, structure


# ---------- plan jobs ----------

def cluster_status(partition):
    """Ask SLURM how busy the partition is right now."""
    try:
        cores = subprocess.run(["sinfo", "-h", "-p", partition, "-o", "%C"],
                               capture_output=True, text=True, timeout=30).stdout.strip()
        allocated, idle, other, total = map(int, cores.split("/"))
        pending = subprocess.run(["squeue", "-h", "-p", partition, "-t", "PD"],
                                 capture_output=True, text=True, timeout=30).stdout.splitlines()
        return {"available": True, "partition": partition, "idle_cores": idle, "allocated_cores": allocated,
                "unavailable_cores": other, "total_cores": total, "pending_jobs": len(pending)}
    except Exception as err:
        return {"available": False, "partition": partition, "error": str(err)}


def plan_batches(calcs, settings, status):
    """Split calculations into SLURM jobs. Returns (batches, cores per job, list of reasons in plain words)."""
    why = []
    largest = max(c["n_atoms"] for c in calcs)
    if settings["cores_per_job"] > 0:
        cores = settings["cores_per_job"]
        why.append(f"{cores} cores per job, as set in config.toml.")
    else:
        cores = auto_cores(largest)
        why.append(f"{cores} cores per job: the largest cell has {largest} atoms, and cells this small "
                   f"don't run faster on more cores.")

    if settings["n_batches"] > 0:
        n = min(settings["n_batches"], len(calcs))
        why.append(f"{n} job(s), as requested (n_batches = {settings['n_batches']}).")
    else:
        if status["available"]:
            fit_now = max(1, status["idle_cores"] // cores)
            why.append(f"The {status['partition']} partition has {status['idle_cores']} idle cores of "
                       f"{status['total_cores']} ({status['pending_jobs']} jobs waiting), so {fit_now} job(s) "
                       f"of {cores} cores could start right away.")
        else:
            fit_now = 1
            why.append(f"Could not read cluster load ({status['error']}), so planning 1 job to be safe.")
        n = max(1, min(len(calcs), settings["max_parallel_jobs"], fit_now))
        why.append(f"{len(calcs)} calculation(s), at most {settings['max_parallel_jobs']} parallel jobs "
                   f"(max_parallel_jobs) -> {n} job(s).")

    # Balance the load: biggest calculation first, always into the job with the least work so far.
    batches = [[] for _ in range(n)]
    for c in sorted(calcs, key=lambda c: -c["est_cost"]):
        min(batches, key=lambda b: sum(x["est_cost"] for x in b)).append(c)
    batches = [b for b in batches if b]
    why.append("Calculations were spread so each job has a similar estimated cost "
               "(k-points x atoms^2); calculations inside one job run one after another.")
    return batches, cores, why


def write_jobs(batches, cores, settings, jobs_dir):
    template = (STAGE_DIR / "slurm_template.sh").read_text()
    plan = []
    for i, batch in enumerate(batches, start=1):
        name = f"hp_b{i:02d}"
        script = template.format(job_name=name, partition=settings["partition"], ntasks=cores,
                                 time_limit=settings["time_limit"], vasp_dir=settings["vasp_dir"],
                                 vasp_exe=settings["vasp_exe"],
                                 calc_dirs=" ".join(f"../calcs/{c['name']}" for c in batch))
        path = jobs_dir / f"batch_{i:02d}.slurm"
        path.write_text(script)
        for c in batch:
            c["batch"] = i
        plan.append({"batch": i, "job_name": name, "script": path.name, "cores": cores,
                     "calcs": [c["name"] for c in batch], "est_cost": sum(c["est_cost"] for c in batch)})
    return plan


# ---------- plots ----------

def plot_xrd(structures, calcs, wavelength, path):
    """Simulated powder X-ray diffraction for each structure, stacked. XRD is the main way
    high-pressure phases are identified in experiments, so this links predictions to measurements."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pymatgen.analysis.diffraction.xrd import XRDCalculator

    calculator = XRDCalculator(wavelength=wavelength)
    fig, ax = plt.subplots(figsize=(8, 1.2 + 1.1 * len(calcs)), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for row, (structure, c) in enumerate(zip(structures, calcs)):
        base = len(calcs) - 1 - row
        pattern = calculator.get_pattern(structure, two_theta_range=(10, 90))
        color = STATUS_COLOR.get(c["label"], SERIES)
        ax.vlines(pattern.x, base, base + 0.85 * pattern.y / 100, color=color, lw=2)
        ax.axhline(base, color=GRID, lw=0.8)
        ax.text(10.5, base + 0.88, f"{c['id']}  {c['space_group']}  ({c['label']})",
                fontsize=9, color=INK, va="bottom")
    ax.set_xlim(10, 90)
    ax.set_ylim(-0.1, len(calcs) + 0.15)
    ax.set_yticks([])
    ax.set_xlabel(f"2θ (degrees), wavelength {wavelength}", color=INK)
    pressures = ", ".join(f"{p:g}" for p in sorted({c["pressure_GPa"] for c in calcs}))
    ax.set_title(f"Simulated X-ray diffraction of the structures sent to DFT ({pressures} GPa)",
                 loc="left", fontsize=11, color=INK)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_job_plan(plan, calcs, path):
    """Estimated cost of each calculation, grouped by the SLURM job it was put in."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_name = {c["name"]: c for c in calcs}
    labels, costs = [], []
    for job in plan:
        for name in job["calcs"]:
            c = by_name[name]
            labels.append(f"job {job['batch']} · {c['id']} ({c['n_atoms']} atoms, k {c['kpoint_grid']})")
            costs.append(c["est_cost"])
    fig, ax = plt.subplots(figsize=(8, 1.0 + 0.45 * len(labels)), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    y = np.arange(len(labels))[::-1]
    ax.barh(y, costs, color=SERIES, height=0.6, edgecolor=SURFACE, linewidth=2)
    for yi, cost in zip(y, costs):
        ax.text(cost, yi, f" {cost:,}", va="center", fontsize=8, color=INK)
    ax.set_yticks(y, labels, fontsize=9, color=INK)
    ax.set_xlabel("Estimated relative cost (k-points × atoms²)", color=INK)
    ax.set_title(f"How the {len(labels)} calculations are split into {len(plan)} job(s), "
                 f"{plan[0]['cores']} cores each", loc="left", fontsize=11, color=INK)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(axis="x", colors=MUTED)
    ax.set_xlim(0, max(costs) * 1.2)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser(description="Stage 4: build VASP inputs and plan jobs.")
    parser.add_argument("--config", help="settings file (default: ../config.toml)")
    parser.add_argument("--input", help="structures needing DFT (default: stage 3 needs_dft.extxyz)")
    parser.add_argument("--ids", nargs="+", help="exact structure ids to prepare")
    parser.add_argument("--max-structures", type=int, help="how many Needs DFT structures (0 = all)")
    parser.add_argument("--profile", choices=sorted(PROFILES), help="accuracy level")
    parser.add_argument("--n-batches", type=int, help="number of SLURM jobs (0 = automatic)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    settings = dict(cfg["stage4"])
    if args.n_batches is not None:
        settings["n_batches"] = args.n_batches
    profile = args.profile or settings["profile"]
    ids = args.ids or settings["ids"]
    max_structures = settings["max_structures"] if args.max_structures is None else args.max_structures
    input_path = Path(args.input or settings["input"] or STAGE3_OUT / "needs_dft.extxyz")

    out_dir, log_dir = stage_dirs(STAGE_DIR)
    log, log_file = get_logger("stage4", log_dir)
    SETTINGS["PMG_VASP_PSP_DIR"] = str((STAGE_DIR / settings["potcar_dir"]).resolve())

    chosen = select_structures(settings, input_path, ids, max_structures, log)
    if not chosen:
        log.error("No structures selected. Check stage 3 outputs, ids or max_structures.")
        sys.exit(1)
    log.info("Stage 4 start | %d structure(s): %s | profile %s", len(chosen),
             [a.info["id"] for a in chosen], profile)

    calcs_dir, jobs_dir = out_dir / "calcs", out_dir / "jobs"
    for d in (calcs_dir, jobs_dir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()

    calcs, structures = [], []
    for atoms in chosen:
        calc_dir = calcs_dir / f"{atoms.info['id']}_{float(atoms.info['pressure_gpa']):g}GPa"
        summary, structure = build_input(atoms, profile, settings["checks"], calc_dir)
        log.info("built %s | %s | %d atoms | ENCUT %d eV | k-points %s | checks %s",
                 summary["name"], summary["space_group"], summary["n_atoms"], summary["ENCUT"],
                 summary["kpoint_grid"], "passed" if summary["checks_passed"] else
                 "FAILED: " + summary["check_failures"])
        calcs.append(summary)
        structures.append(structure)

    ready = [c for c in calcs if c["checks_passed"]]
    if len(ready) < len(calcs):
        log.warning("%d input(s) failed the checks and will not be scheduled.", len(calcs) - len(ready))
    if not ready:
        log.error("No inputs passed the checks.")
        sys.exit(1)

    status = cluster_status(settings["partition"])
    batches, cores, why = plan_batches(ready, settings, status)
    plan = write_jobs(batches, cores, settings, jobs_dir)
    for line in why:
        log.info("plan: %s", line)
    for job in plan:
        log.info("job %d (%s): %s", job["batch"], job["script"], ", ".join(job["calcs"]))

    with open(out_dir / "job_plan.json", "w") as f:
        json.dump({"cluster_status": status, "cores_per_job": cores, "jobs": plan,
                   "time_limit": settings["time_limit"], "profile": profile}, f, indent=2)
    lines = ["# Job plan", "", f"Profile: **{profile}** (see `incar_rules.py`).", "",
             "## Why the jobs were split this way", ""] + [f"- {w}" for w in why] + \
            ["", "## Jobs", "", "| Job | Script | Cores | Calculations |", "|---|---|---|---|"] + \
            [f"| {j['batch']} | `{j['script']}` | {j['cores']} | {', '.join(j['calcs'])} |" for j in plan] + \
            ["", "Submit with stage 5 (it copies these folders first, then runs `sbatch`)."]
    (out_dir / "job_plan.md").write_text("\n".join(lines) + "\n")

    fields = ["name", "id", "pressure_GPa", "label", "space_group", "n_atoms", "potcars", "ENCUT",
              "kpoint_grid", "est_cost", "batch", "checks_passed", "check_failures", "ml_model",
              "ml_enthalpy_eV_per_atom", "reasons"]
    with open(out_dir / "input_summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(calcs)

    if settings["make_plots"]:
        plot_xrd(structures, calcs, settings["xrd_wavelength"], out_dir / "xrd_patterns.png")
        plot_job_plan(plan, ready, out_dir / "job_plan.png")

    save_run_info(out_dir, {"stage": 4, "config": cfg, "profile": profile, "input": input_path,
                            "n_calcs": len(calcs), "n_ready": len(ready), "jobs": len(plan),
                            "cluster_status": status, "log_file": log_file})
    log.info("Stage 4 done | %d input(s) built, %d ready, %d job(s) planned | outputs in %s",
             len(calcs), len(ready), len(plan), out_dir)


if __name__ == "__main__":
    main()
