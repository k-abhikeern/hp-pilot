# Stage 8: pressure scan (enthalpy vs pressure, transition pressure)

**Job:** follow the most stable phases of a material over a range of pressures, with the ML model and with DFT, and find the pressure where one phase takes over from another: the **transition pressure at 0 K**.

## Run it

```bash
cd /home/abhikeern/project/7_OSI/8_stage_pressure_scan
~/miniconda3/envs/osi/bin/python run_stage8.py submit --dry-run   # build everything, send nothing
~/miniconda3/envs/osi/bin/python run_stage8.py submit             # ML relaxations now + DFT jobs to SLURM
~/miniconda3/envs/osi/bin/python run_stage8.py collect            # when jobs finish: plot + transition pressure
```

It needs a stage 7 campaign of the material (its DFT results tell stage 8 which phases are most stable).

## I want to... (where to change things)

| I want to... | Edit `[stage8]` in `config.toml` | Or on the command line |
|---|---|---|
| scan another material | `campaign = "CaSiO3_30GPa"` | `--campaign CaSiO3_30GPa` |
| use other pressures | `pressures_gpa = [0, 10, 20, 30]` | `--pressures 0 10 20 30` |
| follow more phases | `n_phases = 3` | `--n-phases 3` |
| tighter DFT | `profile = "standard"` | `--profile standard` |
| look at an older scan | | `collect --scan runs/scan_<label>_<date>_<time>` |

## What it does

1. Takes the `n_phases` most stable phases from stage 7 (`phases_<campaign>.csv`) and their DFT-relaxed structures.
2. For each phase and pressure:
   - **ML:** relaxes it with the stage 2 model (seconds).
   - **DFT:** builds a VASP input from the ML-relaxed structure with stage 4's builder and checks (same profiles, PSTRESS, ISIF = 3).
3. Plans one SLURM job per pressure with stage 4's planner and submits them.
4. `collect` reads the DFT results with stage 5's reader and computes **dH = H(phase) − H(reference)**. The reference is the phase most stable at the lowest pressure. It then finds where dH changes sign (linear interpolation between neighbouring pressures).

**0 K** means no temperature and no zero-point vibration: a static-lattice estimate. Quick settings give a rough value (a few GPa).

## Files

| File | What it is |
|---|---|
| `run_stage8.py` | submit and collect |
| `runs/scan_<label>_<date>_<time>/` | `calcs/` (VASP), `jobs/` (SLURM), `ml_results.csv`, `scan_state.json` |
| `outputs/enthalpy_vs_pressure_<label>.png` | dH vs pressure: DFT solid, ML dashed |
| `outputs/scan_<label>.csv` | one row per phase and pressure |
| `outputs/transition_<label>.md` | transition pressures from DFT and ML |
| `logs/` | one log per command |

## Result: NaCl, rocksalt (B1) vs CsCl-type (B2), quick DFT

- 14 DFT calculations at 10 to 50 GPa, all converged, symmetry kept, each under 20 s.
- **DFT transition: 24.6 GPa.** ML (MACE-MP-0) transition: 23.5 GPa.
- ML gets the crossing close, but badly underestimates how fast B2 gains with pressure:

  | | at 30 GPa | at 50 GPa |
  |---|---|---|
  | DFT, B2 below B1 by | 25 meV/atom | 111 meV/atom |
  | ML, B2 below B1 by | 11 meV/atom | 19 meV/atom |

  This is the systematic underestimation under pressure reported for universal ML potentials.
- The abstracts retrieved in stage 6 confirm the B1→B2 transition in NaCl but do not state its pressure. Compare 24.6 GPa with a reference value before quoting it.
