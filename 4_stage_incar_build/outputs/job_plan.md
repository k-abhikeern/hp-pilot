# Job plan

Profile: **quick** (see `incar_rules.py`).

## Why the jobs were split this way

- 16 cores per job: the largest cell has 10 atoms, and cells this small don't run faster on more cores.
- 10 job(s), as requested (n_batches = 10).
- Calculations were spread so each job has a similar estimated cost (k-points x atoms^2); calculations inside one job run one after another.

## Jobs

| Job | Script | Cores | Calculations |
|---|---|---|---|
| 1 | `batch_01.slurm` | 16 | s003_30GPa, s012_30GPa |
| 2 | `batch_02.slurm` | 16 | s004_30GPa, s010_30GPa |
| 3 | `batch_03.slurm` | 16 | s011_30GPa, s006_30GPa |
| 4 | `batch_04.slurm` | 16 | s017_30GPa, s013_30GPa |
| 5 | `batch_05.slurm` | 16 | s016_30GPa, s008_30GPa |
| 6 | `batch_06.slurm` | 16 | s001_30GPa, s009_30GPa |
| 7 | `batch_07.slurm` | 16 | s018_30GPa, s002_30GPa |
| 8 | `batch_08.slurm` | 16 | s000_30GPa, s019_30GPa |
| 9 | `batch_09.slurm` | 16 | s014_30GPa, s015_30GPa |
| 10 | `batch_10.slurm` | 16 | s005_30GPa, s007_30GPa |

Submit with stage 5 (it copies these folders first, then runs `sbatch`).
