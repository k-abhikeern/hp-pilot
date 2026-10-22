"""Structure generators for stage 1.

Every generator takes the same inputs and returns one ASE Atoms object, or None if it fails.

To add a new tool later (for example AIRSS, XtalOpt seeds or a generative model):
  1. write a function with the same inputs as pyxtal_random below,
  2. add it to GENERATORS at the bottom of this file,
  3. set  generator = "<its name>"  in [stage1] of config.toml.
Nothing else in the project needs to change.
"""
from pyxtal import pyxtal


def pyxtal_random(elements, counts, space_group, volume_factor, random_state):
    """One random crystal with the given space-group symmetry, made by PyXtal."""
    crystal = pyxtal()
    try:
        crystal.from_random(3, space_group, elements, counts,
                            factor=volume_factor, random_state=random_state)
    except Exception:
        # Some atom counts can't be placed in some space groups; the caller just tries again.
        return None
    return crystal.to_ase() if crystal.valid else None


GENERATORS = {
    "pyxtal_random": pyxtal_random,
}
