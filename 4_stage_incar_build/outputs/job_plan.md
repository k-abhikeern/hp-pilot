# Job plan

Profile: **quick** (see `incar_rules.py`).

## Why the jobs were split this way

- 16 cores per job: the largest cell has 10 atoms, and cells this small don't run faster on more cores.
- The defq partition has 200 idle cores of 704 (61 jobs waiting), so 12 job(s) of 16 cores could start right away.
- 3 calculation(s), at most 4 parallel jobs (max_parallel_jobs) -> 3 job(s).
- Calculations were spread so each job has a similar estimated cost (k-points x atoms^2); calculations inside one job run one after another.

## Jobs

| Job | Script | Cores | Calculations |
|---|---|---|---|
| 1 | `batch_01.slurm` | 16 | s003_30GPa |
| 2 | `batch_02.slurm` | 16 | s011_30GPa |
| 3 | `batch_03.slurm` | 16 | s006_30GPa |

Submit with stage 5 (it copies these folders first, then runs `sbatch`).
