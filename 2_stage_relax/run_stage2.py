"""Stage 2: relax structures at a target pressure with a machine-learning model.

Run (settings come from ../config.toml; command-line options override them):
    ~/miniconda3/envs/osi/bin/python run_stage2.py
    ~/miniconda3/envs/osi/bin/python run_stage2.py --pressure 30
    ~/miniconda3/envs/osi/bin/python run_stage2.py --pressure 0 15 30 --input my_structure.cif
    ~/miniconda3/envs/osi/bin/python run_stage2.py --model mace_mp_small

Outputs (in outputs/):
    relaxed.extxyz   all relaxed structures with energy and enthalpy; stage 3 reads this
    results.csv      one row per structure and pressure, ranked by enthalpy
    run_info.json    the settings used
    traj/            every relaxation step, only if save_trajectories = true
"""
import argparse
import csv
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from ase.calculators.singlepoint import SinglePointCalculator
from ase.filters import FrechetCellFilter
from ase.io import read, write
from ase.io.trajectory import Trajectory
from ase.optimize import BFGS, FIRE
from ase.units import GPa
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

STAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from hp_common import get_logger, load_config, save_run_info, stage_dirs  # noqa: E402
from hp_models import load_model  # noqa: E402

OPTIMIZERS = {"FIRE": FIRE, "BFGS": BFGS}
DEFAULT_INPUT = PROJECT_ROOT / "1_stage_create_structure" / "outputs" / "structures.extxyz"
STRUCTURE_FILES = ("*.cif", "*.vasp", "POSCAR*", "CONTCAR*", "*.extxyz", "*.xyz")


def read_structures(path):
    """Read one structure file or every structure file in a folder; give each structure an id."""
    path = Path(path)
    files = sorted(f for pattern in STRUCTURE_FILES for f in path.glob(pattern)) if path.is_dir() else [path]
    if not files:
        raise FileNotFoundError(f"No structure files found in {path}")
    structures = []
    for f in files:
        for i, atoms in enumerate(read(f, index=":")):
            atoms.info.setdefault("id", f.stem if i == 0 else f"{f.stem}_{i}")
            structures.append(atoms)
    return structures


def space_group(atoms):
    """Space group symbol and number after relaxation (loose tolerance, so small distortions are ignored)."""
    try:
        sga = SpacegroupAnalyzer(AseAtomsAdaptor.get_structure(atoms), symprec=0.1)
        return f"{sga.get_space_group_symbol()} ({sga.get_space_group_number()})"
    except Exception:
        return "unknown"


def relax(atoms, calc, pressure_gpa, settings, traj_file=None):
    """Relax atoms and cell at a fixed pressure. Returns the relaxed atoms and a result dictionary."""
    atoms = atoms.copy()
    atoms.calc = calc
    cell_filter = FrechetCellFilter(atoms, scalar_pressure=pressure_gpa * GPa)
    opt = OPTIMIZERS[settings["optimizer"]](cell_filter, logfile=None)
    if traj_file:
        opt.attach(Trajectory(traj_file, "w", atoms))
    start = time.time()
    converged = opt.run(fmax=settings["fmax"], steps=settings["max_steps"])

    n = len(atoms)
    energy = atoms.get_potential_energy()
    volume = atoms.get_volume()
    # Enthalpy H = E + PV decides which structure is most stable at a given pressure.
    enthalpy = energy + pressure_gpa * GPa * volume
    result = {
        "converged": bool(converged),
        "steps": opt.nsteps,
        "energy_eV_per_atom": energy / n,
        "enthalpy_eV_per_atom": enthalpy / n,
        "volume_A3_per_atom": volume / n,
        "max_force_eV_A": float(np.abs(atoms.get_forces()).max()),
        "space_group_after": space_group(atoms),
        "time_s": round(time.time() - start, 1),
    }
    # A "relaxed" volume far outside normal solids means the model broke down.
    if not np.isfinite(enthalpy) or not 2.0 < result["volume_A3_per_atom"] < 200.0:
        result["status"] = "exploded"
    else:
        result["status"] = "ok" if converged else "not_converged"
    atoms.info.update(pressure_gpa=pressure_gpa, enthalpy_eV_per_atom=result["enthalpy_eV_per_atom"],
                      status=result["status"])
    # Freeze this structure's own results; the shared model object moves on to the next structure.
    atoms.calc = SinglePointCalculator(atoms, energy=energy, forces=atoms.get_forces(),
                                       stress=atoms.get_stress())
    return atoms, result


def main():
    parser = argparse.ArgumentParser(description="Stage 2: relax structures at pressure.")
    parser.add_argument("--config", help="settings file (default: ../config.toml)")
    parser.add_argument("--input", help="structure file or folder (default: stage 1 output)")
    parser.add_argument("--pressure", type=float, nargs="+", help="pressure(s) in GPa")
    parser.add_argument("--model", help="model name from hp_models.py")
    args = parser.parse_args()

    cfg = load_config(args.config)
    settings = cfg["stage2"]
    model_name = args.model or settings["model"]
    pressures = args.pressure or settings["pressures_gpa"] or [cfg["project"]["pressure_gpa"]]
    input_path = Path(args.input or settings["input"] or DEFAULT_INPUT)

    out_dir, log_dir = stage_dirs(STAGE_DIR)
    log, log_file = get_logger("stage2", log_dir)

    import torch
    torch.set_num_threads(settings["n_threads"])

    structures = read_structures(input_path)
    log.info("Stage 2 start | %d structures from %s | model %s | pressures %s GPa | %d threads",
             len(structures), input_path, model_name, pressures, settings["n_threads"])
    calc = load_model(model_name)

    traj_dir = out_dir / "traj"
    shutil.rmtree(traj_dir, ignore_errors=True)
    if settings["save_trajectories"]:
        traj_dir.mkdir()

    relaxed, rows = [], []
    for p in pressures:
        for atoms in structures:
            sid = atoms.info["id"]
            traj_file = traj_dir / f"{sid}_{p:g}GPa.traj" if settings["save_trajectories"] else None
            try:
                new_atoms, result = relax(atoms, calc, p, settings, traj_file)
            except Exception as err:
                log.warning("FAILED %s at %g GPa: %s", sid, p, err)
                rows.append({"id": sid, "pressure_GPa": p, "model": model_name, "status": "failed"})
                continue
            new_atoms.info["model"] = model_name
            relaxed.append(new_atoms)
            rows.append({"id": sid, "pressure_GPa": p, "model": model_name, **result})
            log.info("%s | %g GPa | %-13s | %3d steps | H %.4f eV/atom | V %.2f A^3/atom | %s",
                     sid, p, result["status"], result["steps"], result["enthalpy_eV_per_atom"],
                     result["volume_A3_per_atom"], result["space_group_after"])

    # Rank by enthalpy at each pressure; dH is the gap to the best structure (in meV/atom).
    for p in pressures:
        good = sorted((r for r in rows if r["pressure_GPa"] == p and r["status"] == "ok"),
                      key=lambda r: r["enthalpy_eV_per_atom"])
        for rank, r in enumerate(good, start=1):
            r["rank"] = rank
            r["dH_meV_per_atom"] = round(1000 * (r["enthalpy_eV_per_atom"] - good[0]["enthalpy_eV_per_atom"]), 1)
        if good:
            log.info("Best at %g GPa: %s, %s, H = %.4f eV/atom", p, good[0]["id"],
                     good[0]["space_group_after"], good[0]["enthalpy_eV_per_atom"])

    rows.sort(key=lambda r: (r["pressure_GPa"], r.get("rank", 10**6)))
    fields = ["rank", "id", "pressure_GPa", "model", "status", "dH_meV_per_atom", "enthalpy_eV_per_atom",
              "energy_eV_per_atom", "volume_A3_per_atom", "space_group_after", "steps", "max_force_eV_A",
              "converged", "time_s"]
    with open(out_dir / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    if relaxed:
        write(out_dir / "relaxed.extxyz", relaxed)

    counts = {s: sum(r["status"] == s for r in rows) for s in ("ok", "not_converged", "exploded", "failed")}
    save_run_info(out_dir, {"stage": 2, "config": cfg, "input": input_path, "model": model_name,
                            "pressures_gpa": pressures, "counts": counts, "log_file": log_file})
    log.info("Stage 2 done | %s | outputs in %s", counts, out_dir)


if __name__ == "__main__":
    main()
