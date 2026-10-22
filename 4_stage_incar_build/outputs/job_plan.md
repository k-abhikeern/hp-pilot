# Job plan

Profile: **standard** (see `incar_rules.py`).

## Why the jobs were split this way

- 8 cores per job: the largest cell has 8 atoms, and cells this small don't run faster on more cores.
- 10 job(s), as set in config.toml (n_batches = 10).
- Calculations were spread so each job has a similar estimated cost (k-points x atoms^2); calculations inside one job run one after another.

## Jobs

| Job | Script | Cores | Calculations |
|---|---|---|---|
| 1 | `batch_01.slurm` | 8 | s000_15GPa |
| 2 | `batch_02.slurm` | 8 | s018_15GPa |
| 3 | `batch_03.slurm` | 8 | s011_15GPa, s015_15GPa |
| 4 | `batch_04.slurm` | 8 | s008_15GPa, s017_15GPa |
| 5 | `batch_05.slurm` | 8 | s001_15GPa, s012_15GPa |
| 6 | `batch_06.slurm` | 8 | s014_15GPa, s019_15GPa |
| 7 | `batch_07.slurm` | 8 | s002_15GPa, s006_15GPa |
| 8 | `batch_08.slurm` | 8 | s003_15GPa, s013_15GPa |
| 9 | `batch_09.slurm` | 8 | s005_15GPa, s016_15GPa, s010_15GPa |
| 10 | `batch_10.slurm` | 8 | s009_15GPa, s007_15GPa, s004_15GPa |

Submit with stage 5 (it copies these folders first, then runs `sbatch`).
