# Stage 4: INCAR build (VASP inputs + job plan)

**Job:** for the structures that need DFT, write ready-to-run VASP input folders with high-pressure settings, check every input, and plan how to split the calculations into SLURM jobs based on how busy the cluster is. Nothing is submitted here; stage 5 does that.

## Run it

```bash
cd /home/abhikeern/project/7_OSI/4_stage_incar_build
~/miniconda3/envs/osi/bin/python run_stage4.py
```

By default it takes the 3 best-ranked "high priority" Needs DFT structures from stage 3, plus 1 Trusted structure as a control (to test whether "Trusted" holds up in DFT).

## I want to... (where to change things)

| I want to... | Edit `[stage4]` in `config.toml` | Or on the command line |
|---|---|---|
| prepare more or fewer structures | `max_structures` (0 = all Needs DFT) | `--max-structures 5` |
| prepare exact structures | `ids = ["s019", "s003"]` | `--ids s019 s003` |
| skip the Trusted control | `trusted_controls = 0` | |
| use real-quality settings instead of quick test settings | `profile = "standard"` | `--profile standard` |
| choose the number of SLURM jobs myself | `n_batches = 2` (0 = automatic) | `--n-batches 2` |
| allow more jobs at once | `max_parallel_jobs` | |
| set cores per job myself | `cores_per_job = 24` (0 = automatic) | |
| give jobs more time | `time_limit = "04:00:00"` | |
| use another VASP version | `vasp_dir` | |
| run on another cluster | edit `slurm_template.sh` (modules, srun line) and `partition` | |
| change the XRD wavelength | `xrd_wavelength = "MoKa"` or e.g. `0.4133` (synchrotron) | |
| change INCAR settings | edit `PROFILES` in `incar_rules.py` | |

## What it does, step by step

1. **Choose structures.** Named `ids`, or the best-ranked high-priority Needs DFT structures, plus Trusted controls.
2. **Build each input.**
   - Base settings come from pymatgen's Materials Project relaxation set (sensible POTCARs, +U and magnetic moments for any element).
   - Then the profile's settings (`quick` or `standard`) are applied.
   - Then the high-pressure settings: PSTRESS = 10 × pressure in GPa (VASP uses kBar), ISIF = 3 so the cell can change, and ENCUT = factor × the largest POTCAR ENMAX.
   - Spin polarization stays on only if the structure contains magnetic elements.
   - k-points come from KSPACING, so no KPOINTS file is written.
3. **Check every input.** POTCAR found for every element, ENCUT high enough, PSTRESS matches the pressure, ISIF = 3, ISPIN = 2 when magnetic elements are present. Inputs that fail are not scheduled.
4. **Read the cluster.** `sinfo` and `squeue` give idle cores and waiting jobs.
5. **Plan jobs.**
   - Cores per job come from cell size: 8 cores up to 8 atoms, 16 up to 32, 24 above that, because small cells don't get faster on more cores.
   - Number of jobs = the smallest of: number of calculations, `max_parallel_jobs`, and how many jobs fit in the idle cores right now.
   - Calculations are spread so each job has a similar estimated cost.
6. **Explain the plan** in `job_plan.md`, the log, and `job_plan.png`.

## Accuracy profiles

| Profile | For | ENCUT | k-spacing | Force limit | Max steps |
|---|---|---|---|---|---|
| `quick` | testing the workflow, minutes per job | 1.3 × ENMAX | 0.4 Å⁻¹ | 0.05 eV/Å | 60 |
| `standard` | results you would report | 1.5 × ENMAX | 0.2 Å⁻¹ | 0.01 eV/Å | 200 |

`quick` results are only for checking that everything works, not for conclusions.

## Files

| File | What it is |
|---|---|
| `run_stage4.py` | the stage script |
| `incar_rules.py` | accuracy profiles, high-pressure settings, input checks; extend here |
| `slurm_template.sh` | the job script template (from `run_vasp_yargla.slurm`); edit for other clusters |
| `outputs/calcs/<id>_<P>GPa/` | INCAR, POSCAR, POTCAR, meta.json (ML results and labels) for each calculation |
| `outputs/jobs/batch_NN.slurm` | one SLURM script per job |
| `outputs/job_plan.md` | why the jobs were split this way, in plain words |
| `outputs/job_plan.json` | the same plan, read by stage 5 |
| `outputs/input_summary.csv` | atoms, ENCUT, k-points, batch, check results per calculation |
| `outputs/xrd_patterns.png` | simulated XRD of each structure (pymatgen) |
| `outputs/job_plan.png` | estimated cost per calculation, by job |
| `logs/stage4_<date>_<time>.log` | full log of each run |

POTCARs come from `/home/abhikeern/imp_script/potpaw_PBE`, linked in `0_stage_softwares_resources_etc/potcars/POT_GGA_PAW_PBE`.

## How to add things

- **A new profile:** add an entry to `PROFILES` in `incar_rules.py`.
- **A new input check:** write `my_check(incar, potcar, structure, target_gpa)` in `incar_rules.py`, add it to `CHECKS`, add its name to `checks` in `config.toml`.
- **Element rules** (e.g. harder POTCARs under pressure): change `build_input()` in `run_stage4.py` or pass `user_potcar_settings` to `MPRelaxSet`.

## Results so far (Si, 15 GPa)

- 4 inputs built, all passed the checks: `s019` (beta-tin), `s015` and `s000` (simple hexagonal), and the Trusted control `s009` (simple cubic).
- ENCUT 319 eV (1.3 × 245 eV for Si), k-point grids from 4x4x4 to 8x8x4.
- 200 of 704 cores were idle, so the plan is 4 jobs of 8 cores each.
- The XRD plot shows `s015` and `s000` are the same phase, so one of those runs is redundant. Removing duplicates earlier would avoid that.
