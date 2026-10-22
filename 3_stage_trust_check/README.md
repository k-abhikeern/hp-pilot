# Stage 3: trust check

**Job:** decide, for every relaxed structure, whether the machine-learning result can be trusted or needs a DFT check.

**The idea in one line:** ask several models ("the committee") about the same structure. If they agree, trust it. If they disagree, or the structure looks physically odd, send it to DFT.

## Run it

```bash
cd /home/abhikeern/project/7_OSI/3_stage_trust_check
~/miniconda3/envs/osi/bin/python run_stage3.py
```

By default it reads stage 2's `relaxed.extxyz`. It doesn't relax anything; each model just evaluates the finished structures, so it's quick (about 12 seconds for 20 structures).

## I want to... (where to change things)

| I want to... | Edit `[stage3]` in `config.toml` | Or on the command line |
|---|---|---|
| use different models in the committee | `models = [...]` (names from `../hp_models.py`) | `--models mace_mp_medium mace_mpa_medium` |
| check my own relaxed structures | `input = "/path/to/file.extxyz"` | `--input /path/to/file.extxyz` |
| be stricter (flag more structures) | lower `max_enthalpy_spread_meV`, `max_pressure_deviation_gpa`, `max_force_eV_A` | |
| be more relaxed (flag fewer) | raise those same limits | |
| switch a check off | remove its name from `checks = [...]` | |
| change what counts as "high priority" for DFT | `dft_window_meV` | |
| skip the plot | `make_plot = false` | |

## The checks

A structure is **Needs DFT** if any check fails. The reasons are written next to it.

| Check | Fails when | Why it matters |
|---|---|---|
| `relax_status` | stage 2 didn't finish cleanly | the relaxed structure itself is unreliable |
| `enthalpy_spread` | models disagree on how stable it is by more than `max_enthalpy_spread_meV` | its ranking might be wrong |
| `pressure_deviation` | another model thinks the structure is at a different pressure | its volume, and so its enthalpy, is uncertain |
| `force` | another model sees large forces on the "relaxed" atoms | it may not be a real minimum |
| `short_bond` | atoms closer than `min_bond_ratio` × normal bond | unphysical squeezing |
| `collapse` | volume below `collapse_fraction` × typical volume | the model may have fallen into a "hole" |

The limits are **first guesses**. They should be tuned on systems with known answers (see `../future_stage_wise_improvements.md`).

## Files

| File | What it is |
|---|---|
| `run_stage3.py` | the stage script |
| `trust_checks.py` | the checks; add new ones here |
| `../hp_models.py` | the committee models (shared with stage 2) |
| `outputs/trust_report.csv` | one row per structure: label, reasons, every check value, each model's numbers |
| `outputs/needs_dft.extxyz` | structures labelled Needs DFT; stage 4 reads this |
| `outputs/trusted.extxyz` | structures labelled Trusted |
| `outputs/trust_plot.png` | the summary figure |
| `outputs/run_info.json` | settings and counts |
| `logs/stage3_<date>_<time>.log` | full log of each run |

`dft_priority` in the report is `high` when a Needs DFT structure is within `dft_window_meV` of the best one. Those are worth DFT time first.

## How to read the plot

- Across: how far above the best structure each one is. Left is more stable.
- Up: how much the models disagree. Above the dashed line means Needs DFT.
- Green circles are Trusted, red triangles are Needs DFT.
- The most useful corner is **top left**: structures that look stable but where the models disagree. These are the ones DFT should check first.

## How to add a new check

1. In `trust_checks.py`, write `def my_check(rec, s):` returning a short reason string if it fails, or `None`.
2. Add it to `CHECKS` at the bottom of that file.
3. Add its name to `checks = [...]` in `config.toml`.

If the check needs a new number (for example a coordination number), compute it in `build_records()` in `run_stage3.py` and store it in the record.

## Results so far (Si, 15 GPa, committee of three MACE models)

- Latest run, with the provisional limits in `config.toml`: 0 Trusted, 20 Needs DFT, 3 of those high priority.
- Earlier run (CaSiO₃ with calibrated limits, which is not the Si case) gave 5 Trusted. Its outputs were replaced by the Si run above.
- Limitation: all three committee models are MACE, so they share an architecture and may share blind spots. Mixing model families is a planned improvement.

## External test: MgVH5 from the HPCSD database (32 to 90 GPa)

Folder: `external_tests/MgVH5_series/`. The database structure was checked at 32 to 90 GPa in 10 GPa steps (`run_series.py`):
ML relaxes it at each pressure, one quick DFT run starts from the database CIF, and `collect` compares the two.
Results and figure are in that folder's `outputs/`.

Only one phase of one material is used here. So it tests how wrong ML is as pressure rises. It is not enough to calibrate the trust limits on its own.

## Calibrating the limits on DFT results

The limits above were first guesses tuned on silicon. Once DFT results exist (stage 7 campaigns), they can be fitted per material:

```bash
cd /home/abhikeern/project/7_OSI/3_stage_trust_check
~/miniconda3/envs/osi/bin/python calibrate_trust.py                    # ML "wrong" = error > 50 meV/atom
~/miniconda3/envs/osi/bin/python run_stage3.py --limits-file calibration/calibrated_limits.toml
```

To use the calibrated limits by default, set `limits_file = "calibration/calibrated_limits.toml"` in `[stage3]`. Stage 3 picks the section for the current material; materials not in the file keep the `config.toml` limits. The log says which limits were used.

For each signal (enthalpy spread, pressure deviation, force), `calibrate_trust.py` tries every limit and keeps the one that best separates "ML right" from "ML wrong". It scores them by balanced accuracy: the average of the share of wrong results caught and the share of right results trusted.

Outputs in `calibration/`:
- `calibrated_limits.toml`: limits per material;
- `calibration_report.md`: per signal and material, how well each limit does;
- `calibration.png`: model disagreement vs real ML error, with old and new limits.

**Results on 52 DFT structures (quick DFT):**

| Material | Old limits: caught / trusted | Calibrated: caught / trusted |
|---|---|---|
| Si (14 of 20 ML results wrong) | 43% / 0% | 79% / 50% |
| NaCl (18 of 18 wrong) | 100% / – | 100% / – (best rule: always DFT) |
| CaSiO₃ (8 of 14 wrong) | 100% / 0% | 100% / 83% |
| One shared limit for all | 80% / 0% | 65% / 100% |

**What this means:**
- **Limits must be set per chemistry.** CaSiO₃'s disagreement limit is about 330 meV/atom, against 20 tuned on Si, and no single limit works for all three materials.
- **For Si, model disagreement points the wrong way.** The ML results that were wrong had the *lowest* disagreement (the all-MACE committee agreed on its mistakes), so only the pressure and force signals help there.
- **Caution:** the limits are fitted and tested on the same few structures. They show what the signals can do, not proven performance on new materials.
