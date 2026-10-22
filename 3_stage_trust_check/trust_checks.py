"""Trust checks for stage 3.

Each check looks at one structure's record and returns a short reason if the structure
should NOT be trusted, or None if it passes. A structure is "Needs DFT" if any check fails.

The record (a dictionary) holds, for one structure:
    status                  stage 2 result: ok / not_converged / exploded / failed
    enthalpy_spread_meV     how much the committee models disagree on relative enthalpy
    max_pressure_dev_GPa    largest difference between a model's pressure and the target
    max_force_eV_A          largest force any model sees on the relaxed atoms
    min_bond_ratio          shortest distance / normal bond length
    volume_vs_median        volume per atom / typical volume per atom at this pressure

To add a new check later (for example a built-in model uncertainty, or a coordination check):
  1. write a function  my_check(record, settings) -> reason string or None,
  2. add it to CHECKS at the bottom,
  3. add its name to  checks = [...]  in [stage3] of config.toml.
"""
import numpy as np
from ase.data import covalent_radii


def min_bond_ratio(atoms):
    """Smallest (distance / normal bond length) over all atom pairs."""
    if len(atoms) < 2:
        return float("inf")
    d = atoms.get_all_distances(mic=True)
    r = covalent_radii[atoms.numbers]
    i, j = np.triu_indices(len(atoms), k=1)
    return float((d[i, j] / (r[i] + r[j])).min())


def relax_status(rec, s):
    if rec["status"] != "ok":
        return f"stage 2 relaxation {rec['status']}"


def enthalpy_spread(rec, s):
    if rec["enthalpy_spread_meV"] > s["max_enthalpy_spread_meV"]:
        return f"models disagree on enthalpy by {rec['enthalpy_spread_meV']:.0f} meV/atom"


def pressure_deviation(rec, s):
    if rec["max_pressure_dev_GPa"] > s["max_pressure_deviation_gpa"]:
        return f"models disagree on pressure by {rec['max_pressure_dev_GPa']:.1f} GPa"


def force(rec, s):
    if rec["max_force_eV_A"] > s["max_force_eV_A"]:
        return f"another model sees forces of {rec['max_force_eV_A']:.2f} eV/A"


def short_bond(rec, s):
    if rec["min_bond_ratio"] < s["min_bond_ratio"]:
        return f"atoms very close ({rec['min_bond_ratio']:.2f} of a normal bond)"


def collapse(rec, s):
    if rec["volume_vs_median"] < s["collapse_fraction"]:
        return f"volume collapsed ({rec['volume_vs_median']:.2f} of typical)"


CHECKS = {
    "relax_status": relax_status,
    "enthalpy_spread": enthalpy_spread,
    "pressure_deviation": pressure_deviation,
    "force": force,
    "short_bond": short_bond,
    "collapse": collapse,
}
