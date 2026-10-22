# Job plan

Profile: **quick** (see `incar_rules.py`).

## Why the jobs were split this way

- 8 cores per job: the largest cell has 8 atoms, and cells this small don't run faster on more cores.
- The defq partition has 200 idle cores of 704 (61 jobs waiting), so 25 job(s) of 8 cores could start right away.
- 4 calculation(s), at most 4 parallel jobs (max_parallel_jobs) -> 4 job(s).
- Calculations were spread so each job has a similar estimated cost (k-points x atoms^2); calculations inside one job run one after another.

## Jobs

| Job | Script | Cores | Calculations |
|---|---|---|---|
| 1 | `batch_01.slurm` | 8 | s000_15GPa |
| 2 | `batch_02.slurm` | 8 | s019_15GPa |
| 3 | `batch_03.slurm` | 8 | s009_15GPa |
| 4 | `batch_04.slurm` | 8 | s015_15GPa |

Submit with stage 5 (it copies these folders first, then runs `sbatch`).
