# HP-Pilot

Finds candidate crystal structures at high pressure, checks whether a machine-learning model can be trusted for each one, and prepares VASP inputs for the ones that need DFT.

## Quick start: one command

```bash
cd /home/abhikeern/project/7_OSI
./hp-pilot run --composition Si --pressure 15            # stages 1-4: structures, relax, trust check, VASP inputs
./hp-pilot run --composition Si --pressure 15 --submit   # same, and send the VASP jobs to SLURM
./hp-pilot status                                        # are the jobs done?
./hp-pilot collect                                       # compare DFT with ML
./hp-pilot literature                                    # literature report (after the agent's Valency search)
```

## Stage by stage

```bash
cd /home/abhikeern/project/7_OSI
~/miniconda3/envs/osi/bin/python 1_stage_create_structure/run_stage1.py   # make candidate structures
~/miniconda3/envs/osi/bin/python 2_stage_relax/run_stage2.py              # relax them at pressure
~/miniconda3/envs/osi/bin/python 3_stage_trust_check/run_stage3.py        # label Trusted / Needs DFT
~/miniconda3/envs/osi/bin/python 4_stage_incar_build/run_stage4.py        # VASP inputs + job plan
~/miniconda3/envs/osi/bin/python 5_stage_vasp_run/run_stage5.py submit    # send jobs to SLURM
~/miniconda3/envs/osi/bin/python 5_stage_vasp_run/run_stage5.py status    # check jobs
~/miniconda3/envs/osi/bin/python 5_stage_vasp_run/run_stage5.py collect   # compare DFT with ML
```

All settings are in **`config.toml`**. Each stage folder has a README with an "I want to..." table that says what to change.

## Most common changes

| I want to... | Change in `config.toml` |
|---|---|
| study a different material | `composition` in `[project]`, e.g. `"NaCl"` |
| use a different pressure | `pressure_gpa` in `[project]` |
| make more or fewer candidates | `n_structures` in `[stage1]` |
| relax my own structure instead | `input` in `[stage2]` |
| use a different model | `model` in `[stage2]` (options in `hp_models.py`) |
| change the committee or trust limits | `models` and the `max_...` limits in `[stage3]` |

## Stages

| Folder | What it does |
|---|---|
| `0_stage_softwares_resources_etc` | installs, environment, logs |
| `1_stage_create_structure` | random candidate structures |
| `2_stage_relax` | relax at pressure, rank by enthalpy |
| `3_stage_trust_check` | compare models, label Trusted or Needs DFT, summary plot |
| `4_stage_incar_build` | VASP inputs for flagged structures, input checks, cluster-aware job plan, XRD plot |
| `5_stage_vasp_run` | submit to SLURM, check jobs, compare DFT with ML |
| `6_stage_literature_check` | check predicted phases against the literature via Valency (agent-run, reviewed) |

Progress and decisions are in `PROGRESS.md`. Planned improvements for every stage are in `future_stage_wise_improvements.md`.

## Adding tools

Tools are kept in dictionaries so new ones plug in without changing other stages:

- structure generators: `1_stage_create_structure/generators.py`
- machine-learning models: `hp_models.py` (shared by all stages)
- optimizers: `OPTIMIZERS` in `2_stage_relax/run_stage2.py`
- trust checks: `3_stage_trust_check/trust_checks.py`
- VASP accuracy profiles and input checks: `4_stage_incar_build/incar_rules.py`
- job script for another cluster: `4_stage_incar_build/slurm_template.sh`
