"""MgVH5 test series: the HPCSD database structure at 32 GPa, and the numbered files at 40-90 GPa (10 GPa steps).

For each structure:
  1. ML (stage 2 model) relaxes the database structure at its pressure.
  2. One quick DFT run (VASP, SLURM) starts from the database CIF, using the same stage 4 tools as stage 8.
Then collect compares ML and DFT enthalpy at every pressure.

    ~/miniconda3/envs/osi/bin/python run_series.py submit      # ML relax + build inputs + send one SLURM job
    ~/miniconda3/envs/osi/bin/python run_series.py collect     # newest series: table + figure

Outputs (in this folder):
    series_<date>_<time>/         calcs/ (VASP), jobs/ (SLURM), ml_results.csv
    outputs/series_results.csv    one row per pressure: ML and DFT enthalpy, volume, error
    outputs/mgvh5_ml_vs_dft.png   ML error and volumes vs pressure
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "0_stage_softwares_resources_etc" / "data"
OUT = HERE / "outputs"
PROFILE = "quick"
# (file, pressure in GPa). File (1) is 40 GPa; the files go up in 10 GPa steps.
CASES = [("MgVH5.cif", 32)] + [(f"MgVH5 ({i}).cif", 30 + 10 * i) for i in range(1, 7)]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
ML_COLOR, DFT_COLOR = "#E69F00", "#0072B2"  # colourblind-safe: orange = ML, blue = DFT
sys.path[:0] = [str(ROOT / "4_stage_incar_build"), str(ROOT / "2_stage_relax"), str(ROOT),
                str(ROOT / "5_stage_vasp_run")]


def submit(args, cfg):
    import run_stage4 as s4
    from ase.io import read
    from hp_models import load_model
    from pymatgen.core import SETTINGS
    from run_stage2 import relax

    SETTINGS["PMG_VASP_PSP_DIR"] = str((ROOT / "4_stage_incar_build" / cfg["stage4"]["potcar_dir"]).resolve())
    run_dir = HERE / time.strftime("series_%Y%m%d_%H%M%S")
    (run_dir / "calcs").mkdir(parents=True)
    (run_dir / "jobs").mkdir()
    calc = load_model(cfg["stage2"]["model"])

    summaries, ml_rows = [], []
    for name, p in CASES:
        tag = f"MgVH5_{p}GPa"
        ml_atoms, res = relax(read(DATA / name), calc, float(p), cfg["stage2"])
        ml_rows.append({"tag": tag, "file": name, "pressure_GPa": p, "ml_status": res["status"],
                        "ml_steps": res["steps"], "ml_enthalpy_eV_per_atom": res["enthalpy_eV_per_atom"],
                        "ml_volume_A3_per_atom": res["volume_A3_per_atom"]})
        print(f"{tag}: ML {res['status']}, H = {res['enthalpy_eV_per_atom']:.4f} eV/atom, V = {res['volume_A3_per_atom']:.3f}")

        # DFT starts from the database structure itself, not from the ML-relaxed one.
        atoms = read(DATA / name)
        atoms.info.update(id=tag, pressure_gpa=float(p), label="series", model="HPCSD database",
                          enthalpy_eV_per_atom=res["enthalpy_eV_per_atom"], status=res["status"])
        summary, _ = s4.build_input(atoms, PROFILE, cfg["stage4"]["checks"], run_dir / "calcs" / tag)
        if not summary["checks_passed"]:
            print(f"{tag}: input checks failed, skipped: {summary['check_failures']}")
            continue
        summaries.append(summary)

    with open(run_dir / "ml_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ml_rows[0]))
        w.writeheader()
        w.writerows(ml_rows)

    plan_settings = {**cfg["stage4"], "n_batches": 1}
    batches, cores, why = s4.plan_batches(summaries, plan_settings, s4.cluster_status(cfg["stage4"]["partition"]))
    plan = s4.write_jobs(batches, cores, plan_settings, run_dir / "jobs")
    for line in why:
        print("plan:", line)
    jobs = []
    for job in plan:
        if args.dry_run:
            print(f"DRY RUN: would submit {job['script']} ({job['cores']} cores): {', '.join(job['calcs'])}")
            continue
        out = subprocess.run(["sbatch", job["script"]], cwd=run_dir / "jobs", capture_output=True, text=True)
        match = re.search(r"Submitted batch job (\d+)", out.stdout)
        if match:
            jobs.append({**job, "job_id": match.group(1)})
            print(f"submitted {job['script']} as job {match.group(1)}")
        else:
            print(f"sbatch failed: {(out.stderr or out.stdout).strip()}")
    (run_dir / "series_state.json").write_text(json.dumps({"profile": PROFILE, "dry_run": args.dry_run,
                                                          "submitted": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                          "jobs": jobs}, indent=2))
    print(f"run folder: {run_dir}")


def collect(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import run_stage5 as s5

    runs = sorted(HERE.glob("series_*"))
    if not runs:
        sys.exit("No series folder yet. Run:  run_series.py submit")
    run = runs[-1]
    ml = {r["tag"]: r for r in csv.DictReader(open(run / "ml_results.csv"))}
    rows = []
    for calc_dir in sorted((run / "calcs").iterdir(), key=lambda d: float(d.name.split("_")[-1].rstrip("GPa"))):
        r = s5.read_calc(calc_dir)
        m = ml[r["id"]]
        dft_h = r["dft_enthalpy_eV_per_atom"]
        ml_h = float(m["ml_enthalpy_eV_per_atom"])
        rows.append({"pressure_GPa": float(m["pressure_GPa"]), "file": m["file"], "dft_status": r["dft_status"],
                     "dft_pressure_GPa": round(float(r["dft_pressure_GPa"]), 2),
                     "ml_status": m["ml_status"], "ml_H_eV_per_atom": round(ml_h, 5),
                     "dft_H_eV_per_atom": round(dft_h, 5), "error_ML_minus_DFT_meV": round(1000 * (ml_h - dft_h), 1),
                     "ml_volume_A3": round(float(m["ml_volume_A3_per_atom"]), 3),
                     "dft_volume_A3": round(r["dft_volume_A3_per_atom"], 3)})
    OUT.mkdir(exist_ok=True)
    with open(OUT / "series_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['pressure_GPa']:5.0f} GPa | DFT {r['dft_status']} P={r['dft_pressure_GPa']} | "
              f"error ML-DFT {r['error_ML_minus_DFT_meV']:+.1f} meV/atom | V ML {r['ml_volume_A3']} DFT {r['dft_volume_A3']}")

    p = [r["pressure_GPa"] for r in rows]
    err = [r["error_ML_minus_DFT_meV"] for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4), facecolor=SURFACE)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_xlabel("Pressure (GPa)", color=INK)
    ax1.axhspan(-50, 50, color=DFT_COLOR, alpha=0.08, lw=0)
    ax1.axhline(0, color=MUTED, lw=1)
    ax1.plot(p, err, "-o", color=ML_COLOR, lw=2, ms=7, mec=SURFACE)
    for x, y in zip(p, err):
        ax1.annotate(f"{y:+.0f}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8, color=INK)
    ax1.text(p[0], 55, "within 50 meV/atom (ML right)", fontsize=7.5, color=DFT_COLOR)
    ax1.set_ylabel("ML minus DFT enthalpy (meV/atom)", color=INK)
    ax1.set_title("How wrong is ML? (same structure)", loc="left", fontsize=10, color=INK)
    ax2.plot(p, [r["dft_volume_A3"] for r in rows], "-o", color=DFT_COLOR, lw=2, ms=6, label="DFT (VASP)")
    ax2.plot(p, [r["ml_volume_A3"] for r in rows], "--o", color=ML_COLOR, lw=2, ms=6, label="ML (MACE)")
    ax2.set_ylabel("Volume (A$^3$ per atom)", color=INK)
    ax2.set_title("Volume vs pressure", loc="left", fontsize=10, color=INK)
    ax2.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle("MgVH$_5$ (HPCSD structure): ML compared with DFT, 32 to 90 GPa", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / "mgvh5_ml_vs_dft.png", dpi=200, facecolor=SURFACE)

    # Single panel for the video (optional): the same ML error, large enough to read on screen.
    vfig, vax = plt.subplots(figsize=(7, 4.5), facecolor=SURFACE)
    vax.set_facecolor(SURFACE)
    vax.grid(True, color=GRID, lw=0.6)
    vax.set_axisbelow(True)
    for side in ("top", "right"):
        vax.spines[side].set_visible(False)
    vax.tick_params(colors=MUTED, labelsize=11)
    vax.axhspan(-50, 50, color=DFT_COLOR, alpha=0.08, lw=0)
    vax.axhline(0, color=MUTED, lw=1)
    vax.plot(p, err, "-o", color=ML_COLOR, lw=3, ms=9, mec=SURFACE)
    vax.set_xlabel("Pressure (GPa)", fontsize=12, color=INK)
    vax.set_ylabel("ML minus DFT enthalpy (meV/atom)", fontsize=12, color=INK)
    vax.set_title("MgVH$_5$: ML stays wrong from 32 to 90 GPa", loc="left", fontsize=13, color=INK)
    vax.text(p[0], 60, "shaded band: within 50 meV/atom", fontsize=10, color=DFT_COLOR)
    vfig.tight_layout()
    vfig.savefig(OUT / "mgvh5_ml_error_video.png", dpi=200, facecolor=SURFACE)
    print(f"wrote {OUT / 'series_results.csv'}, {OUT / 'mgvh5_ml_vs_dft.png'} and {OUT / 'mgvh5_ml_error_video.png'}")


def main():
    parser = argparse.ArgumentParser(description="MgVH5 test series: ML and DFT at 32 and 40-90 GPa.")
    parser.add_argument("command", choices=["submit", "collect"])
    parser.add_argument("--dry-run", action="store_true", help="submit: build inputs, send nothing")
    args = parser.parse_args()
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    if args.command == "submit":
        submit(args, cfg)
    else:
        collect(args)


if __name__ == "__main__":
    main()
