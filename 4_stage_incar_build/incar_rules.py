"""Rules for building VASP inputs in stage 4.

Three parts, each a dictionary or function you can extend:
  PROFILES          accuracy levels ("quick" for testing, "standard" for real results)
  pressure_settings the high-pressure settings every input gets
  CHECKS            hard checks every input must pass before a job is planned

Base settings come from pymatgen's Materials Project relaxation set (MPRelaxSet), which already
knows sensible POTCARs, magnetic moments and +U values for every element. These rules only
change what matters for high pressure and for speed.

To add a profile: add an entry to PROFILES and set  profile = "<its name>"  in [stage4] of config.toml.
To add a check:   write  my_check(incar, potcar, structure, target_gpa) -> reason or None,
                  add it to CHECKS, and add its name to  checks = [...]  in [stage4].
"""

# Accuracy levels. enmax_factor sets ENCUT = factor x the largest ENMAX of the POTCARs in the cell.
PROFILES = {
    # Light settings to test the workflow: runs in minutes, NOT publication quality.
    "quick": {
        "enmax_factor": 1.3,
        "incar": {"PREC": "Normal", "EDIFF": 1e-5, "EDIFFG": -0.05, "NSW": 60,
                  "KSPACING": 0.4, "ISMEAR": 0, "SIGMA": 0.1, "LREAL": False},
    },
    # Tighter settings for results you would report.
    "standard": {
        "enmax_factor": 1.5,
        "incar": {"PREC": "Accurate", "EDIFF": 1e-6, "EDIFFG": -0.01, "NSW": 200,
                  "KSPACING": 0.2, "ISMEAR": 0, "SIGMA": 0.05, "LREAL": False},
    },
}

# Elements that may carry a magnetic moment; only these switch on spin polarization (ISPIN = 2).
MAGNETIC_ELEMENTS = {
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu",
    "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd",
    "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt",
    "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "U", "Np", "Pu",
}


def pressure_settings(target_gpa):
    """Settings every high-pressure relaxation needs."""
    return {
        "PSTRESS": round(10.0 * target_gpa, 3),  # VASP wants kBar; 1 GPa = 10 kBar
        "ISIF": 3,                               # let the cell shape and volume change
        "IBRION": 2,                             # conjugate-gradient relaxation
        "LWAVE": False, "LCHARG": False,         # don't write big files we won't reuse
    }


def check_potcars(incar, potcar, structure, target_gpa):
    elements = {str(el) for el in structure.composition.elements}
    found = {p.element for p in potcar}
    if elements - found:
        return f"no POTCAR for {sorted(elements - found)}"


def check_encut(incar, potcar, structure, target_gpa):
    need = 1.3 * max(p.enmax for p in potcar)
    if incar.get("ENCUT", 0) < need:
        return f"ENCUT {incar.get('ENCUT')} below 1.3 x ENMAX ({need:.0f} eV)"


def check_pstress(incar, potcar, structure, target_gpa):
    if abs(incar.get("PSTRESS", 0) - 10.0 * target_gpa) > 1e-6:
        return f"PSTRESS {incar.get('PSTRESS')} kBar does not match {target_gpa} GPa"


def check_isif(incar, potcar, structure, target_gpa):
    if incar.get("ISIF") != 3:
        return f"ISIF is {incar.get('ISIF')}, needs 3 to relax the cell under pressure"


def check_spin(incar, potcar, structure, target_gpa):
    magnetic = {str(el) for el in structure.composition.elements} & MAGNETIC_ELEMENTS
    if magnetic and incar.get("ISPIN", 1) != 2:
        return f"magnetic elements {sorted(magnetic)} but ISPIN is not 2"


CHECKS = {
    "potcars": check_potcars,
    "encut": check_encut,
    "pstress": check_pstress,
    "isif": check_isif,
    "spin": check_spin,
}
