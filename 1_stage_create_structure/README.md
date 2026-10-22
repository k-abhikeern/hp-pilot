# Stage 1: create structure

**Job:** make random candidate crystal structures for one composition. These are the starting guesses for the search.

## Run it

```bash
cd /home/abhikeern/project/7_OSI/1_stage_create_structure
~/miniconda3/envs/osi/bin/python run_stage1.py
```

Settings come from the `[project]` and `[stage1]` sections of `../config.toml`. To try another composition, change `composition` there, for example `"NaCl"`.

## What it does, step by step

1. Reads the composition, e.g. `Si`, and works out the elements and atoms per formula unit.
2. Repeats until it has `n_structures` structures:
   - picks a random cell size from `formula_units`,
   - picks a random space group (symmetry) from 2 to 230,
   - asks the generator (PyXtal by default) for a random crystal with that symmetry,
   - rejects it if any two atoms overlap (closer than `min_bond_ratio` × normal bond length).
3. Saves every kept structure, a summary table, a log and the settings used.

The same `seed` always gives the same structures, so runs can be repeated.

## Files

| File | What it is |
|---|---|
| `run_stage1.py` | the stage script |
| `generators.py` | the structure-making tools; add new ones here |
| `outputs/structures.extxyz` | all kept structures in one file; stage 2 reads this |
| `outputs/cif/sNNN.cif` | one file per structure, to open in VESTA or similar |
| `outputs/summary.csv` | id, space group, number of atoms, volume per atom, shortest bond |
| `outputs/run_info.json` | settings and counts for this run |
| `logs/stage1_<date>_<time>.log` | full log of each run; old logs are kept |

`outputs/` is rewritten on every run. `logs/` keeps every run.

## How to add a new structure tool

1. In `generators.py`, write a function with the same inputs as `pyxtal_random`, returning an ASE `Atoms` object or `None`.
2. Add it to the `GENERATORS` dictionary at the bottom of that file.
3. Set `generator = "<its name>"` in `[stage1]` of `config.toml`.

## Known limits

- Starting volumes vary a lot (about 8 to 38 Å³ per atom for Si). That's expected: stage 2 relaxes the volume at the target pressure.
- Composition is fixed per run. Searching over different compositions is a later feature.
