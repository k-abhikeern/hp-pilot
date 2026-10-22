# OSI project progress: HP-Pilot

**Goal:** a command-line tool that makes candidate high-pressure crystal structures, checks whether a machine-learning model can be trusted for each one, and writes VASP inputs for the ones that need DFT.

**Hackathon deadline:** Thu 22 Oct 2026, 7 pm CT (= 23 Oct, 02:00 CEST).

## Stage status

| Stage | Folder | What it does | Status |
|---|---|---|---|
| 0 | `0_stage_softwares_resources_etc` | Check machine, create env, keep install logs | DONE |
| 1 | `1_stage_create_structure` | Make random candidate structures for a composition | DONE |
| 2 | `2_stage_relax` | Relax structures at a target pressure with a machine-learning model | DONE |
| 3 | `3_stage_trust_check` | Compare several models; mark each structure Trusted or Needs DFT | DONE |
| 4 | `4_stage_incar_build` | Build VASP input files for the Needs DFT structures, check them, plan SLURM jobs | DONE |
| 5 | `5_stage_vasp_run` | Submit VASP jobs, check them, compare DFT with ML | DONE (first test run) |
| 6 | `6_stage_literature_check` | Check predicted phases against the literature (Valency), agent-reviewed | DONE |

## How the project is organised

```
7_OSI/
├── README.md            how to run, and what to change for common tasks
├── config.toml          all settings, one [section] per stage. Change settings here, not in code.
├── hp_common.py         shared helpers: read settings, make outputs/ and logs/, write logs
├── hp_models.py         machine-learning models shared by all stages; add new models here
├── PROGRESS.md          this file
├── 0_stage_.../         installs, logs, env check
├── 1_stage_.../         run_stage1.py + generators.py (tools) + outputs/ + logs/ + README.md
├── 2_stage_.../         same pattern
└── ...
```

Every stage folder follows the same pattern, so new tools are easy to attach:

| Piece | Purpose |
|---|---|
| `README.md` | what the stage does, how to run it, how to add a tool |
| `run_stageN.py` | the stage script; reads settings from `config.toml` |
| a tools file, e.g. `generators.py` | a dictionary of interchangeable tools; add a function and one line to attach a new one |
| `outputs/` | results of the latest run; the next stage reads from here |
| `logs/` | one time-stamped log per run; old logs are kept |

Stages pass results forward through files: stage 1 writes `outputs/structures.extxyz`, stage 2 reads it, and so on. Any stage can be rerun on its own.

---

## Stage 0: software and resources (DONE)

**What was done**
- Checked YARGLA: 48 CPU cores (Intel Xeon Silver 4116), 92 GB RAM, about 16 TB free on /home. CPU only.
- Found VASP as cluster modules: `vasp/6.5.0` (default) and `vasp/5.4.4`. Quantum ESPRESSO not found.
- Created a fresh conda env `osi` (Python 3.11) in `~/miniconda3/envs/osi` with ASE 3.29, pymatgen 2026.9, PyXtal 1.1.5, MACE 0.3.16 and torch 2.14 (CPU).
- Saved the install log, an env check script and the versions in the stage folder.
- Wrote the MIRO project card, the one-page write-up and the video script.

**Files:** see `0_stage_softwares_resources_etc/README.md`.

---

## Stage 1: create structure (DONE)

**What was done**
- Added `config.toml` (all settings) and `hp_common.py` (shared logging and folder helpers).
- Wrote `generators.py` with one tool, `pyxtal_random`, in a dictionary so more tools can be added later.
- Wrote `run_stage1.py`: picks random cell sizes and space groups, asks the generator for a crystal, and rejects structures where atoms overlap.
- Ran it for Si: 20 structures in 36 attempts, 8 rejected for overlapping atoms. Shortest bond kept: 1.63 Å. Volume per atom: 8 to 38 Å³.

**Problem found and fixed:** the first run kept structures with bonds as short as 1.32 Å (a normal Si–Si bond is about 2.35 Å). Atoms that close can crash a relaxation, so a `min_bond_ratio` filter was added (default 0.7 × normal bond length).

**Output that stage 2 uses:** `1_stage_create_structure/outputs/structures.extxyz`

**Files:** see `1_stage_create_structure/README.md`.

---

## Stage 2: relax (DONE)

**What was done**
- Added `hp_models.py` at the project root: a dictionary of models (MACE-MP-0 medium and small) shared by stages 2 and 3, so a model added once is available everywhere.
- Added a `[stage2]` section to `config.toml`: input, model, pressures, optimizer, force limit, steps, CPU threads.
- Wrote `run_stage2.py`: reads structures, relaxes atoms and cell together at each pressure, computes enthalpy H = E + PV, checks the space group after relaxing, ranks by enthalpy, and labels each result `ok`, `not_converged`, `exploded` or `failed`.
- Added command-line options (`--pressure`, `--input`, `--model`, `--config`) so a user can change a run without editing files.
- Tested two ways: the 20 stage 1 structures at 15 GPa (about 1.5 min on 8 cores, all `ok`), and a user CIF (diamond Si) at 0 and 15 GPa.

**Problems found and fixed**
- The first run crashed when saving, because all structures shared one model object and each reported the last structure's forces. Each structure now stores its own results.
- Log lines printed twice because another library also echoed them. Fixed in `hp_common.py`.

**Results (Si, 15 GPa, MACE-MP-0 medium)**
- Best structure: `s019`, I4_1/amd (beta-tin), the expected stable form of Si near this pressure. A sensible first result.
- `s010` collapsed to 7.8 Å³/atom (about half the normal volume) and sits 905 meV/atom above the best. It looks like the model breaking down; stage 3 should flag it.
- Diamond Si at 15 GPa is about 200 meV/atom above beta-tin with this model. Whether that gap is right is a question for DFT in stage 5.
- Many structures relaxed to the same answer (several simple cubic). Removing duplicates is a later improvement.

**Output that stage 3 uses:** `2_stage_relax/outputs/relaxed.extxyz` (and `results.csv`)

**Files:** see `2_stage_relax/README.md`.

---

## Stage 3: trust check (DONE)

**What was done**
- Added MACE-MPA-0 to `hp_models.py`. The committee is MACE-MP-0 medium, MACE-MPA-0 medium and MACE-MP-0 small.
- Added a `[stage3]` section to `config.toml`: committee models, which checks to run, and the limit for each check.
- Wrote `trust_checks.py`: six checks in a dictionary, so new checks can be added later. Checks: relaxation status, enthalpy disagreement, pressure disagreement, leftover forces, very short bonds, collapsed volume.
- Wrote `run_stage3.py`: every model evaluates every relaxed structure (no relaxing), the numbers go into one record per structure, the checks give a label and reasons, and a summary plot is drawn.
- Each model has its own energy zero, so enthalpies are compared after removing each model's median. This compares rankings, not absolute energies.

**Decisions**
- MatterSim (a different model family) was not installed: it would change about 100 packages, including ones MACE depends on, and could break the env. Planned for a separate env.
- The plot uses the reserved status colours (green Trusted, red Needs DFT) plus different marker shapes, so colour is never the only signal.

**Problems found and fixed**
- The first plot wasted half its area on negative values and had overlapping labels. The axes now start at 0, only important flagged structures are labelled, and labels of overlapping points are merged.

**Results (Si, 15 GPa)**
- 8 Trusted, 12 Needs DFT (6 high priority, within 100 meV/atom of the best). Runs in about 12 s.
- `s010` caught clearly: the other models put this structure at about 12,000 GPa instead of 15. A model breakdown.
- The best structure `s019` (beta-tin) is flagged: the models agree it's the most stable but disagree by 82 meV/atom on the margin. DFT should confirm it.
- Limits are first guesses, and all committee members are MACE models. Both are noted as limitations.

**Context from the literature (Loew et al., J. Phys. Mater. 9, 015010, 2026)**
- All universal models get worse with pressure, and each family fails differently. This supports using disagreement as the trust signal, and argues for mixing families.
- MACE-MPA-0 energy error: 6.9 meV/atom at 0 GPa, 22.8 at 25 GPa, 163.5 at 150 GPa. Moderate at our 15 GPa.

**Output that stage 4 uses:** `3_stage_trust_check/outputs/needs_dft.extxyz`

**Files:** see `3_stage_trust_check/README.md`.

---

## Stage 4: INCAR build (DONE)

**What was done**
- Linked the user's POTCARs (`/home/abhikeern/imp_script/potpaw_PBE`) into `0_stage_softwares_resources_etc/potcars/POT_GGA_PAW_PBE`, the folder name pymatgen expects. Nothing was copied.
- Wrote `incar_rules.py`: two accuracy profiles (`quick` for testing, `standard` for real results), the high-pressure settings (PSTRESS, ISIF = 3, ENCUT from POTCAR ENMAX), a magnetic-element list, and five input checks, all as dictionaries that can be extended.
- Wrote `slurm_template.sh` from the user's `run_vasp_yargla.slurm` (VASP 6.4.2, Intel MPI, `srun --mpi=pmi2`), with names in curly brackets that stage 4 fills in.
- Wrote `run_stage4.py`: chooses structures, builds inputs with pymatgen's MPRelaxSet plus our rules, checks them, reads cluster load with `sinfo`/`squeue`, plans jobs, explains the plan, and draws two plots.
- Added a `[stage4]` section to `config.toml` and command-line options.

**Decisions**
- Stage 4 only prepares. Stage 5 will copy the inputs into its own folder before submitting, so rerunning stage 4 can never delete a running calculation.
- Gaussian smearing (ISMEAR = 0) instead of MP's tetrahedron method (ISMEAR = -5), because high-pressure phases are often metallic.
- Spin polarization only when magnetic elements are present (saves time for Si).
- Each run adds 1 Trusted structure as a control, so DFT can test whether "Trusted" was right.
- Cores per job from cell size (8 cores for ≤ 8 atoms), since tiny cells don't speed up on 24 cores.

**Problems found and fixed**
- A nested f-string (not allowed in Python 3.11) and a template comment containing curly brackets broke the first runs. Both fixed.

**Results (Si, 15 GPa, quick profile)**
- 4 inputs, all passed the checks: `s019` (beta-tin), `s015`, `s000` (both simple hexagonal) and the Trusted control `s009` (simple cubic). ENCUT 319 eV.
- Cluster had 200 of 704 cores idle, so 4 jobs of 8 cores each were planned; `job_plan.md` explains why.
- The XRD plot shows `s015` and `s000` are the same phase, a duplicate DFT run that earlier duplicate removal would avoid.

**Output that stage 5 uses:** `4_stage_incar_build/outputs/calcs/`, `outputs/jobs/`, `outputs/job_plan.json`

**Files:** see `4_stage_incar_build/README.md`.

---

## Stage 5: VASP run (DONE, first test run)

**What was done**
- Wrote `run_stage5.py` with three commands:
  - `submit`: copies stage 4's inputs into `runs/run_<date>_<time>/` and runs `sbatch`; `--dry-run` shows the jobs without sending them.
  - `status`: shows the SLURM state and each calculation's start, exit code and end.
  - `collect`: reads results with pymatgen, compares with ML, and draws a plot.
- Submitted 4 jobs (8 cores each, quick profile) on YARGLA: jobs 64241 to 64244. All finished in under 10 seconds and converged.

**Problems found and fixed**
- **Enthalpy counted PV twice.** With PSTRESS set, VASP's `vasprun.xml` energies already include PV. First found because DFT energies looked 1.3 eV/atom too high; OUTCAR confirmed the real energy (−5.06 eV/atom) matches MACE. Fixed.
- **Pressure label.** VASP's stress is the full pressure on the cell (about 15 GPa here), not the leftover after PSTRESS. Relabelled.
- Overlapping labels in the plot; merged.

**Results (Si, 15 GPa, quick profile)**
- DFT and ML enthalpies agree within about 15 meV/atom for 3 of 4 structures; symmetry unchanged by DFT.
- **The ranking flipped:** ML put beta-tin (`s019`) first; DFT puts simple hexagonal (`s015`/`s000`) first, beta-tin 12 meV/atom above. These were flagged Needs DFT, so the trust check was right to flag them. A 12 meV gap is within quick-setting error, so this needs a `standard` rerun.
- **The Trusted control `s009` (simple cubic) was wrong:** ML 12 meV/atom above the best, DFT 165. All three MACE models agreed and were wrong together, the shared-blind-spot risk of a one-family committee. This is the main lesson for the next version.

**Files:** see `5_stage_vasp_run/README.md`.

---

## Stage 6: literature check (DONE)

**What was done**
- Wrote `run_stage6.py`:
  - `prepare` turns our predicted phases into common names and search queries;
  - `report` classifies each phase as Known or Not found, extracts the pressures papers report, and writes a report with evidence sentences and links, plus a figure.
- Wrote `import_valency.py` to merge saved Valency results and remove duplicate papers.
- The agent (Claude) ran two Valency searches: a keyword batch (8 queries) and a meaning-based search on silicon's high-pressure phases. 73 unique papers. Raw results are kept in `outputs/raw_valency/`.

**Problems found and fixed**
- The first rule (material and phase anywhere in the abstract) gave false matches: Cmcm **SiO₃**, an **Fe-Si alloy**, a **beryllium** hcp paper, and a nickel-film paper. Now the material and the phase must be in the same sentence.
- The agent then reviewed every evidence sentence and recorded decisions with reasons in `review.json`: 5 exclusions, and 2 additions the sentence rule missed (a silicon paper predicting fcc and simple cubic Si at 2.9 and 3.9 TPa).

**Results (Si, 15 GPa)**
- 5 phases Known, 6 Not found.
- The two lowest phases in DFT, beta-tin and simple hexagonal, are exactly the ones the literature reports around 15 GPa (7.5 to 16 GPa). That's independent support for the pipeline.
- fcc, hcp and simple cubic appear in the literature only at much higher pressures (40 GPa to TPa), consistent with our pipeline ranking them high in enthalpy.
- "Not found" is not "new": most are high in enthalpy; the low-lying Cmcm and P4/nmm may be distorted known phases (e.g. Imma) and deserve a DFT check.

**Files:** see `6_stage_literature_check/README.md`.

---

## Quick DFT check on all 20 structures (DONE)

**What was done:** stage 4 with every structure id, then stage 5: 4 jobs of 8 cores (64245 to 64248), 5 calculations each, about 1 minute per job. All 20 converged at 14.7 to 15.4 GPa.

**Results (quick profile)**

| Group | ML: above best | DFT: above best |
|---|---|---|
| simple hexagonal (`s015`, `s000`), Needs DFT | 12 meV/atom | 0 to 1 (best) |
| beta-tin (`s019`), Needs DFT | 0 (best) | 12 |
| all 8 **Trusted** (simple cubic, Cmcm, P4/nmm) | about 12 | **118 to 205** |
| other Needs DFT | 60 to 182 | 125 to 238 |
| `s010` (collapsed in ML), Needs DFT | 905 | 212 (DFT un-collapsed it) |

**What it means**
- **The trust check failed on every Trusted structure.** MACE-MP-0 put eight different structures in a false cluster about 12 meV/atom above the best, and all three MACE committee members agreed. A committee from one model family cannot see an error all members share.
- **The pipeline's safety net worked:** the Trusted controls sent to DFT exposed the error.
- **The physics is sensible:** DFT puts simple hexagonal and beta-tin within 12 meV/atom at 15 GPa, matching the literature check (both reported near this pressure).
- **Most important next step:** a committee mixing model families (MatterSim, SevenNet, eSEN), then recalibrate the limits on these 20 DFT results.

---

## Standard DFT check on all 20 structures (DONE)

**What was done:** stage 4 with `--profile standard` (ENCUT 368 eV, k-spacing 0.2, forces to 0.01 eV/Å, up to 200 steps), split into 10 jobs of 8 cores (64249 to 64258, 1 to 4 minutes each). All 20 converged in 3 to 42 steps at 14.94 to 15.05 GPa. New script `5_stage_vasp_run/compare_runs.py` compares any two runs. Quick results kept in `outputs_quick_run_20261022_182951/`, standard in `outputs_standard_run_20261022_184759/`.

**Quick vs standard**

| Group | ML | Quick DFT | Standard DFT |
|---|---|---|---|
| simple hexagonal `s015` | 12 | 0 (best) | 0 (best) |
| beta-tin `s019` | 0 (best) | 12 | **3.5** |
| `s000` (sh, distorts to P6₃/mcm in standard) | 12 | 0.8 | 3.9 |
| 8 Trusted (simple cubic, Cmcm, P4/nmm) | about 12 | 118 to 205 | **87 to 144** |
| other Needs DFT | 60 to 182 | 125 to 238 | 117 to 202 |

All values in meV/atom above the best structure.

**What changed and what didn't**
- Mean change from quick to standard: 25 meV/atom, largest 67. Rank agreement (Spearman) 0.91. Quick settings are fine for screening, not for fine ranking.
- **Still true:** simple hexagonal is lowest; the 8 Trusted structures are still 75 to 130 meV/atom worse than ML said. The shared blind spot of the all-MACE committee is confirmed with tight settings.
- **Changed:** beta-tin moved from 12 to 3.5 meV/atom above simple hexagonal. At 15 GPa they are practically degenerate within DFT accuracy, so "which is lowest" is not something this level of theory can settle. That fits the literature, where Si goes beta-tin → Imma → simple hexagonal around 13 to 16 GPa.

---

## The full pipeline now works end to end

composition and pressure → random structures (1) → ML relaxation (2) → trust check (3) → VASP inputs and job plan (4) → VASP runs and DFT vs ML comparison (5) → literature check (6).

One command runs stages 1 to 4 and prepares stage 6: `./hp-pilot run --composition Si --pressure 15` (add `--submit` to send VASP jobs). Tested end to end: about 2 minutes, results identical to the stage-by-stage runs (same seed). `./hp-pilot status`, `./hp-pilot collect` and `./hp-pilot literature` run the later steps. Settings used are saved in `last_run_config.toml`.

---

## Later improvements

All planned improvements, sorted by stage and priority, are in `future_stage_wise_improvements.md`.
