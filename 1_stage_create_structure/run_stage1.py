"""Stage 1: create random candidate crystal structures for one composition.

Run from anywhere:
    ~/miniconda3/envs/osi/bin/python run_stage1.py            # uses ../config.toml
    ~/miniconda3/envs/osi/bin/python run_stage1.py my.toml    # uses another settings file

Outputs (in outputs/):
    structures.extxyz   all structures in one file; stage 2 reads this
    cif/sNNN.cif        one file per structure, for viewing (e.g. in VESTA)
    summary.csv         one row per structure: id, space group, atoms, volume, shortest bond
    run_info.json       the settings used, so the run can be repeated
"""
import csv
import shutil
import sys
from pathlib import Path

import numpy as np
from ase.data import covalent_radii
from ase.io import write
from pymatgen.core import Composition

STAGE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE_DIR.parent))
from hp_common import get_logger, load_config, save_run_info, stage_dirs  # noqa: E402
from generators import GENERATORS  # noqa: E402


def shortest_distance(atoms):
    """Shortest distance between two atoms, counting neighbouring cells (periodic images)."""
    if len(atoms) < 2:
        return float("nan")
    d = atoms.get_all_distances(mic=True)
    return float(d[np.triu_indices(len(atoms), k=1)].min())


def min_bond_ratio(atoms):
    """Smallest (distance / normal bond length) over all atom pairs; below ~0.7 means atoms overlap."""
    if len(atoms) < 2:
        return float("inf")
    d = atoms.get_all_distances(mic=True)
    r = covalent_radii[atoms.numbers]
    i, j = np.triu_indices(len(atoms), k=1)
    return float((d[i, j] / (r[i] + r[j])).min())


def main():
    cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    project, settings = cfg["project"], cfg["stage1"]
    out_dir, log_dir = stage_dirs(STAGE_DIR)
    log, log_file = get_logger("stage1", log_dir)

    # "NaCl" -> elements ["Na", "Cl"], atoms per formula unit [1, 1]
    formula = Composition(project["composition"]).reduced_composition
    elements = [str(el) for el in formula.elements]
    per_formula_unit = [int(formula[el]) for el in formula.elements]

    generate = GENERATORS[settings["generator"]]
    space_groups = settings["space_groups"] or list(range(2, 231))
    rng = np.random.default_rng(project["seed"])

    log.info("Stage 1 start | composition %s | generator %s | want %d structures",
             formula.reduced_formula, settings["generator"], settings["n_structures"])

    structures, rows, attempts, rejected = [], [], 0, 0
    while len(structures) < settings["n_structures"] and attempts < settings["max_attempts"]:
        attempts += 1
        z = int(rng.choice(settings["formula_units"]))
        sg = int(rng.choice(space_groups))
        counts = [n * z for n in per_formula_unit]
        atoms = generate(elements, counts, sg, settings["volume_factor"], int(rng.integers(1_000_000_000)))
        if atoms is None:
            continue
        if min_bond_ratio(atoms) < settings["min_bond_ratio"]:
            rejected += 1
            log.info("rejected | space group %3d | atoms too close (shortest bond %.2f A)",
                     sg, shortest_distance(atoms))
            continue

        sid = f"s{len(structures):03d}"
        atoms.info.update(id=sid, space_group=sg, formula_units=z)
        structures.append(atoms)
        row = {
            "id": sid,
            "formula": atoms.get_chemical_formula(),
            "space_group": sg,
            "n_atoms": len(atoms),
            "volume_per_atom_A3": round(atoms.get_volume() / len(atoms), 3),
            "shortest_distance_A": round(shortest_distance(atoms), 3),
        }
        rows.append(row)
        log.info("made %s | space group %3d | %2d atoms | %.2f A^3/atom | shortest bond %.2f A",
                 sid, sg, row["n_atoms"], row["volume_per_atom_A3"], row["shortest_distance_A"])

    if not structures:
        log.error("No structures made in %d attempts. Try other formula_units or space_groups.", attempts)
        sys.exit(1)

    # Rewrite outputs from scratch so files from an older run can't get mixed in.
    cif_dir = out_dir / "cif"
    shutil.rmtree(cif_dir, ignore_errors=True)
    cif_dir.mkdir()
    write(out_dir / "structures.extxyz", structures)
    for atoms in structures:
        write(cif_dir / f"{atoms.info['id']}.cif", atoms)
    with open(out_dir / "summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    save_run_info(out_dir, {
        "stage": 1,
        "config": cfg,
        "attempts": attempts,
        "n_made": len(structures),
        "n_rejected_too_close": rejected,
        "log_file": log_file,
    })
    log.info("Stage 1 done | %d structures in %d attempts (%d rejected as too close) | outputs in %s",
             len(structures), attempts, rejected, out_dir)
    if len(structures) < settings["n_structures"]:
        log.warning("Made fewer structures than asked (%d of %d). Raise max_attempts if you need more.",
                    len(structures), settings["n_structures"])


if __name__ == "__main__":
    main()
