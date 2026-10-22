# Stage 5: VASP run

**Job:** run the VASP jobs planned in stage 4, keep an eye on them, then read the results with pymatgen and check whether DFT agrees with the machine-learning ranking and the trust labels.

## Run it (three commands)

```bash
cd /home/abhikeern/project/7_OSI/5_stage_vasp_run
~/miniconda3/envs/osi/bin/python run_stage5.py submit --dry-run   # see what would be sent, send nothing
~/miniconda3/envs/osi/bin/python run_stage5.py submit             # copy stage 4 inputs and sbatch them
~/miniconda3/envs/osi/bin/python run_stage5.py status             # are the jobs done?
~/miniconda3/envs/osi/bin/python run_stage5.py collect            # read results, compare with ML
```

`status` and `collect` use the newest run. For an older one: `--run runs/run_20261022_180635`.

## I want to... (where to change things)

| I want to... | Do this |
|---|---|
| change which structures run, cores, jobs, time | change `[stage4]` in `config.toml` and rerun stage 4, then `submit` |
| check before using cluster time | `submit --dry-run` |
| look at an older run | `--run runs/run_<date>_<time>` |
| cancel jobs | `scancel <job id>` (ids are in the run's `run_state.json` and the log) |
| rerun everything with real-quality settings | `profile = "standard"` in `[stage4]`, rerun stage 4, then `submit` |

## What each command does

- **submit**
  - copies `calcs/` and `jobs/` from stage 4 into a new `runs/run_<date>_<time>/` folder,
  - runs `sbatch` for each job from that folder,
  - saves the SLURM job ids in `run_state.json`.

  Stage 4 can be rerun safely afterwards; it never touches `runs/`.
- **status**: shows each job's SLURM state (`squeue` while running, `sacct` once finished) and each calculation's `status.txt` (start time, exit code, end time).
- **collect**: for each calculation, reads `vasprun.xml` with pymatgen and records:
  - whether it converged,
  - the final enthalpy and energy,
  - the pressure on the cell,
  - the space group after the DFT relaxation.

  It then compares with the ML values and draws `dft_vs_ml.png`.

## Important detail about VASP energies

With `PSTRESS` set, VASP adds PSTRESS × volume to the energies it writes, so the energy in `vasprun.xml` is already the **enthalpy**. `collect` uses it directly and subtracts PV to get the plain energy. (The first version added PV twice; that bug was found by comparing with OUTCAR and fixed.)

## Files

| File | What it is |
|---|---|
| `run_stage5.py` | the stage script (submit, status, collect) |
| `runs/run_<date>_<time>/` | one folder per submission: `calcs/` (VASP files), `jobs/` (scripts and SLURM output), `run_state.json`, `job_plan.md` |
| `outputs/dft_results.csv` | one row per calculation: DFT and ML enthalpy, energy, volume, pressure, space group, trust label |
| `outputs/dft_vs_ml.png` | DFT vs ML enthalpy above the best structure; on the diagonal = ML was right |
| `logs/stage5_<command>_<date>_<time>.log` | log of each command |

## How to read the plot

- Each point is one structure. Across: how far above the best the ML model put it. Up: how far above the best DFT put it.
- On the dashed line: ML and DFT agree.
- Above the line: the structure is worse than ML thought.
- A **green (Trusted) point far from the line** means the trust check missed an ML error.

## Compare two runs

```bash
~/miniconda3/envs/osi/bin/python compare_runs.py runs/run_A runs/run_B --names quick standard
```

Writes `outputs/compare_<A>_vs_<B>.csv` and `.png`: each structure's enthalpy above the best in both runs, the change, rank agreement, and which structure is best in each.

Note: `collect` rewrites `outputs/`. Copy it first if you want to keep a run's summary (as done for `outputs_quick_run_*` and `outputs_standard_run_*`).

## Results with standard settings (all 20 structures)

- All 20 converged, pressure 14.94 to 15.05 GPa.
- Simple hexagonal still lowest; beta-tin now only 3.5 meV/atom above (12 with quick settings), so the two are practically degenerate at 15 GPa.
- The 8 Trusted structures are still 87 to 144 meV/atom above the best, against about 12 from ML: the committee's blind spot is real.
- Quick vs standard: mean change 25 meV/atom, rank agreement 0.91 (`outputs/compare_quick_vs_standard.png`).

## Results on all 20 structures (Si, 15 GPa, quick profile)

All 20 converged. DFT ranks simple hexagonal first and beta-tin 12 meV/atom above it. **All 8 Trusted structures were wrong by about 100 to 190 meV/atom**: MACE put them about 12 meV/atom above the best, DFT 118 to 205. The all-MACE committee agreed on the same mistake. See `../docs/PROGRESS.md` for the full table.

## First results (Si, 15 GPa, quick profile, 4 jobs of 8 cores, under 10 s each)

| Structure | Trust label | ML: above best | DFT: above best |
|---|---|---|---|
| `s015`, `s000` (simple hexagonal) | Needs DFT | 12 meV/atom | 0 (best) |
| `s019` (beta-tin) | Needs DFT | 0 (best) | 12 meV/atom |
| `s009` (simple cubic) | Trusted | 12 meV/atom | 165 meV/atom |

- All 4 converged, symmetry unchanged, pressure on the cell 14.9 to 15.4 GPa (target 15).
- **The ranking flipped.** ML put beta-tin first, DFT puts simple hexagonal first. These were the flagged structures, so flagging them was right. (A 12 meV gap is within the error of quick settings; rerun with `standard` to confirm.)
- **The Trusted control was wrong by about 150 meV/atom.** All three MACE models agreed, and all three were wrong. A committee of one model family can share a blind spot. The fix is to mix model families (see `../docs/future_stage_wise_improvements.md`).
