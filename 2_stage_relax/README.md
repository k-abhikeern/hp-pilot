# Stage 2: relax

**Job:** squeeze each candidate structure at the target pressure with a machine-learning model, let the atoms and cell settle, and rank the results by enthalpy (the energy that decides which structure is most stable under pressure).

## Run it

```bash
cd /home/abhikeern/project/7_OSI/2_stage_relax
~/miniconda3/envs/osi/bin/python run_stage2.py
```

By default it relaxes the stage 1 structures at the pressure in `config.toml` (15 GPa for Si takes about 1.5 minutes on 8 cores).

## I want to... (where to change things)

| I want to... | Edit `config.toml` | Or on the command line |
|---|---|---|
| use a different pressure | `pressure_gpa` in `[project]` | `--pressure 30` |
| run several pressures | `pressures_gpa = [0, 15, 30]` in `[stage2]` | `--pressure 0 15 30` |
| relax my own structure | `input = "/path/to/file.cif"` in `[stage2]` | `--input /path/to/file.cif` |
| relax a folder of my structures | `input = "/path/to/folder"` | `--input /path/to/folder` |
| use a different model | `model = "mace_mp_small"` | `--model mace_mp_small` |
| make it run faster | `n_threads` (up to 48), or `fmax = 0.1` | |
| relax more tightly | `fmax = 0.01`, `max_steps = 1000` | |
| see every relaxation step | `save_trajectories = true` | |
| use another settings file | | `--config my_settings.toml` |

Command-line options win over `config.toml`. Your own structures can be CIF, POSCAR/CONTCAR, `.vasp`, `.xyz` or `.extxyz` files.

## What it does, step by step

1. Reads the structures (stage 1 output, or your file or folder).
2. Loads the model once.
3. For each pressure and each structure:
   - lets atoms and cell move together under that pressure until all forces are below `fmax`,
   - records energy, enthalpy H = E + PV, volume, space group after relaxing,
   - marks the result `ok`, `not_converged` (ran out of steps), `exploded` (impossible volume) or `failed` (crashed).
4. Ranks the `ok` structures by enthalpy at each pressure. `dH_meV_per_atom` is how far each one is above the best.

## Files

| File | What it is |
|---|---|
| `run_stage2.py` | the stage script |
| `../hp_models.py` | the models (shared with stage 3); add new models here |
| `outputs/results.csv` | one row per structure and pressure, best first |
| `outputs/relaxed.extxyz` | all relaxed structures with their results; stage 3 reads this |
| `outputs/run_info.json` | settings and counts for this run |
| `outputs/traj/` | step-by-step relaxations, only if `save_trajectories = true` |
| `logs/stage2_<date>_<time>.log` | full log of each run; old logs are kept |

`outputs/` is rewritten on every run. If you want to keep a result, copy the folder first.

## How to add a new model

Open `../hp_models.py`, write a function that returns an ASE calculator, add it to `MODELS`, and set `model = "<its name>"`. Stage 3 can then use the same model.

## How to add a new optimizer

Import it in `run_stage2.py` and add it to the `OPTIMIZERS` dictionary near the top.

## Results so far (Si, 15 GPa, MACE-MP-0 medium)

- Best: `s019`, space group I4_1/amd, which is the beta-tin structure. That's the expected stable form of Si around this pressure, so the pipeline finds a sensible answer.
- Several structures relaxed to simple cubic or simple hexagonal, about 12 meV/atom higher.
- `s010` collapsed to 7.8 Å³/atom, about half the normal volume, and sits 905 meV/atom higher. This looks like the model breaking down, which is exactly what stage 3 is meant to catch.
- Several structures ended up the same (e.g. many simple cubic). Removing duplicates is a later improvement.
