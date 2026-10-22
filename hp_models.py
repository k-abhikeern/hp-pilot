"""Machine-learning models (ASE calculators) shared by all stages.

Stage 2 relaxes structures with one of these; stage 3 will compare several of them.

To add a model:
  1. write a function that returns an ASE calculator (see the examples below),
  2. add it to MODELS at the bottom,
  3. use its name in config.toml (e.g. model = "<its name>" in [stage2]).
Each model is only loaded when it is used, so a missing package only matters if you pick that model.
"""


def mace_mp_medium():
    """MACE-MP-0 medium: general-purpose model trained on Materials Project data (mostly near 0 GPa)."""
    from mace.calculators import mace_mp
    return mace_mp(model="medium", device="cpu", default_dtype="float64")


def mace_mp_small():
    """MACE-MP-0 small: faster, a bit less accurate."""
    from mace.calculators import mace_mp
    return mace_mp(model="small", device="cpu", default_dtype="float64")


def mace_mpa_medium():
    """MACE-MPA-0 medium: newer, trained on MPtrj + Alexandria; better under pressure (Loew et al. 2026)."""
    from mace.calculators import mace_mp
    return mace_mp(model="medium-mpa-0", device="cpu", default_dtype="float64")


MODELS = {
    "mace_mp_medium": mace_mp_medium,
    "mace_mp_small": mace_mp_small,
    "mace_mpa_medium": mace_mpa_medium,
}


def load_model(name):
    """Return the ASE calculator for a model name from MODELS."""
    if name not in MODELS:
        raise KeyError(f"Unknown model '{name}'. Available: {', '.join(MODELS)}")
    return MODELS[name]()
