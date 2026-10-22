# Future improvements, stage by stage

Things we noticed or discussed while building, kept here so nothing is forgotten. Add new items as they come up.

**Priority labels**
- **Tonight**: worth doing before the hackathon deadline (23 Oct, 02:00 CEST) if time allows.
- **Soon**: next few days, makes the tool solid for the lab.
- **Later**: bigger features, research directions, or "nice to have".

Each item says where the change would go, so it can be added without touching other stages.

---

## Whole project

| Priority | Improvement | Where |
|---|---|---|
| Done | One command that runs all stages in order: `./hp-pilot run --composition Si --pressure 15 [--submit]` | `hp_pilot.py`, `hp-pilot` |
| Tonight | Evidence figure for the write-up: model disagreement against pressure | stage 3 output |
| Tonight | Put the project in a git repository and publish it, so the hackathon has a code link | root |
| Soon | Save each run in its own folder (e.g. `outputs/run_<date>_<time>/`) instead of overwriting `outputs/` | `hp_common.stage_dirs` |
| Soon | Same command-line options for every stage (stage 1 only takes a settings file so far) | each `run_stageN.py` |
| Soon | Make it pip-installable (`pyproject.toml`) so others install with one command | root |
| Soon | A small automatic test for each stage (runs in seconds on a tiny example) | new `tests/` folder |
| Soon | Record package versions and settings in every `run_info.json` | `hp_common.save_run_info` |
| Later | Agent layer: wrap each stage as a tool (MCP server) so Claude can run the pipeline from a plain-language request | new `agent/` folder |
| Later | marimo notebook to explore results interactively | new `notebook/` folder |
| Done | Literature check through Valency (stage 6), with agent review of every match | `6_stage_literature_check/` |

---

## Stage 6: literature check

| Priority | Improvement | Where |
|---|---|---|
| Soon | Compare structures, not just names: find which known phase each prediction is closest to (e.g. is our Cmcm a distorted Imma?) using pymatgen's StructureMatcher against Materials Project structures | new tool in stage 6 |
| Soon | Read "40 and 93 GPa"-style ranges and TPa values automatically (now only "X GPa" and "X-Y GPa") | `GPA_PATTERN` in `run_stage6.py` |
| Soon | More phase names (Imma, Cmca, BC8, R8, ST12; rocksalt/CsCl for compounds) and Roman-numeral names (Si-II, Si-V) | name dictionaries in `run_stage6.py` |
| Later | Let the pipeline call Valency directly if an API becomes available, so the agent step can also run without Claude | `import_valency.py` |
| Later | Add each paper's reported transition pressure to the DFT comparison plot | stage 5 + 6 |

---

## Stage 0: software and resources

| Priority | Improvement | Where |
|---|---|---|
| Soon | Export the env (`environment.yml` or a lock file) so others can rebuild it exactly | `0_stage_softwares_resources_etc/` |
| Soon | Copy model files into this folder too, for compute nodes without internet | `0_stage_softwares_resources_etc/models/` |
| Later | Install Quantum ESPRESSO as a free alternative to VASP | same folder |
| Later | A GPU version of the env, if GPUs become available | same folder |

---

## Stage 1: create structure

| Priority | Improvement | Where |
|---|---|---|
| Soon | Remove duplicate structures before relaxing (saves time in stage 2) | `run_stage1.py` |
| Soon | Starting volume that matches the target pressure (denser cells at high pressure) | `volume_factor` logic |
| Soon | Check the `min_bond_ratio` filter (0.7) for high pressure and hydrogen-rich systems, where real bonds are shorter | `config.toml`, `run_stage1.py` |
| Soon | Add known structures as seeds (e.g. from Materials Project or the literature) | new generator in `generators.py` |
| Later | More generators: AIRSS (`buildcell`), XtalOpt or USPEX seeds, generative models | `generators.py` |
| Later | Evolutionary search (structures "breed" from the best ones, as in MAGUS/USPEX) instead of only random | new generator + loop between stages 1 and 2 |
| Later | Search over compositions (e.g. all Na-Cl ratios) and build a convex hull | new stage or `[stage1]` option |

---

## Stage 2: relax

| Priority | Improvement | Where |
|---|---|---|
| Tonight | Relax at several pressures (e.g. 0 to 30 GPa) to get enthalpy against pressure and a transition pressure | already possible with `pressures_gpa`; needs a plot |
| Soon | Remove duplicates after relaxing (many structures became the same simple cubic phase) | `run_stage2.py` |
| Soon | Run structures in parallel across cores (48 available; now one at a time on 8 threads) | `run_stage2.py` |
| Soon | Better "exploded" detection: `s010` collapsed to 7.8 Å³/atom but passed the current check (2–200 Å³/atom) | `relax()` in `run_stage2.py` |
| Soon | Check the diamond-to-beta-tin enthalpy gap (~200 meV/atom at 15 GPa with MACE) against DFT | stage 5 comparison |
| Soon | Tighter second relaxation for the best few structures | `run_stage2.py` |
| Later | More foundation models (MACE-MPA, MACE-OMAT, SevenNet, ORB, MatterSim), if they run well on CPU | `hp_models.py` |
| Later | A MACE model fine-tuned on high-pressure data (e.g. HPmat, or the Alexandria pressure dataset below) | `hp_models.py` |
| Soon | Use MACE-MPA-0 as the default relaxer instead of MACE-MP-0: Loew et al. 2026 report it was built with density renormalization for high pressure | `model` in `[stage2]` |
| Later | Phonon check of the best structures (are they dynamically stable?) | new stage after 2 or 3 |

---

## Stage 3: trust check (next to build)

| Priority | Improvement | Where |
|---|---|---|
| Done | First version: three MACE models, six checks, Trusted or Needs DFT with reasons, summary plot | `run_stage3.py` |
| Tonight | Run stage 2 and 3 at several pressures (e.g. 0, 15, 30, 50 GPa) to show disagreement growing with pressure: the evidence figure | `pressures_gpa` in `[stage2]`, a plot in stage 3 |
| Soon | Set the limits from known cases (NaCl B1 to B2 near 30 GPa, Si, Li at 50 GPa) instead of guessing; current limits are first guesses | `config.toml` `[stage3]` |
| Tonight | **Confirmed by DFT on all 20 structures:** every one of the 8 Trusted structures was 100 to 190 meV/atom worse in DFT than ML said. The all-MACE committee shares this blind spot. Mixing families is the most important fix. | — |
| Soon | Recalibrate the stage 3 limits on the 20 DFT results: which signals (spread, pressure deviation, force) actually predict the DFT error? | new analysis in stage 3 or 5 |
| Soon | A "suspicious cluster" check: many different starting structures ending at almost the same ML enthalpy may signal a model artefact | `trust_checks.py` |
| Soon | Mix model families in the committee (now all MACE, which may share blind spots). Loew et al. 2026 show each family fails differently under pressure (ORB over-compresses, M3GNet over-predicts volume) | `hp_models.py` |
| Soon | Install MatterSim in its own env (installing it into `osi` would change ~100 packages, including e3nn which MACE needs) and call it from there | `0_stage_softwares_resources_etc/`, `hp_models.py` |
| Soon | Add the best models from Loew et al. 2026: eSEN-30M-OAM (most accurate untuned under pressure), and the fine-tuned MatterSim-ap-ft-0 and eSEN-ap-ft-0 (free at github.com/hyllios/utils) | `hp_models.py` |
| Soon | Use a fine-tuned high-pressure model as a "referee" in the committee: if it disagrees with the general models, that is a strong DFT signal | `run_stage3.py` |
| Soon | Group duplicate structures in the report (many are the same simple cubic phase) | `run_stage3.py` |
| Later | Use the Alexandria pressure dataset (0 to 150 GPa, 32 million DFT calculations, CC-BY 4.0, alexandria.icams.rub.de) to calibrate the limits and to fine-tune MACE | new benchmark folder |
| Later | Compare our cross-model signal with MAGUS's extrapolation grade on the same cases | separate benchmark |
| Later | Built-in uncertainty methods (multi-head committees, evidential models) | new trust tools |

---

## Stage 4: INCAR build

| Priority | Improvement | Where |
|---|---|---|
| Done | Base INCAR from pymatgen's MPRelaxSet plus PSTRESS, ISIF = 3, ENCUT from ENMAX; quick and standard profiles; five input checks; cluster-aware job plan | `run_stage4.py`, `incar_rules.py` |
| Soon | Skip structures that are duplicates of each other (the XRD plot showed `s015` and `s000` are the same phase) | `select_structures()` in `run_stage4.py`, or earlier in stage 2/3 |
| Soon | Element rule table: f-electron elements flagged for review, +U checked under pressure | `incar_rules.py` |
| Soon | Set KPAR / NCORE from the k-point count and cores, to use the cores better | `build_input()` in `run_stage4.py` |
| Soon | Better cost estimate than k-points × atoms² (use the irreducible k-points and number of bands), and calibrate it from finished runs | `build_input()` |
| Soon | Spread jobs across partitions (defq and G09), and wait for idle nodes when the cluster is busy | `plan_batches()` |
| Later | XRD at a synchrotron wavelength, and compare with measured patterns when available | `plot_xrd()` |
| Soon | Harder or semicore POTCARs where compressed cores may matter | rules file |
| Soon | Small convergence runs (ENCUT and k-point ladders) before the full job | stage 4 + stage 5 |
| Later | LLM review of the INCAR, with every suggested edit checked by the rules | new tool in stage 4 |
| Later | Use INCARBench to pick the best LLM for INCAR writing (check its licence first) | separate benchmark |
| Later | Our own high-pressure INCAR benchmark (10–20 cases with references from convergence studies) | separate benchmark |
| Later | Quantum ESPRESSO input writer | new tool in stage 4 |

---

## Stage 5: VASP run

| Priority | Improvement | Where |
|---|---|---|
| Done | submit / status / collect, using the user's YARGLA SLURM setup (VASP 6.4.2); first 4 test jobs run and compared with ML | `run_stage5.py` |
| Done | Standard rerun of all 20 structures (10 jobs, 1 to 4 min each) and `compare_runs.py`: beta-tin vs simple hexagonal shrinks to 3.5 meV/atom (degenerate); the Trusted blind spot holds (87 to 144 meV/atom) | stage 4 `--profile standard`, `compare_runs.py` |
| Soon | `collect` should write each run's summary to its own folder instead of overwriting `outputs/` | `collect` in `run_stage5.py` |
| Later | Settle near-degenerate phases (beta-tin vs simple hexagonal) with converged k-points, phonons / temperature, or another functional | new stage |
| Done | Quick DFT check on all 20 structures (4 jobs, ~1 min each) | stage 4 `--ids`, stage 5 |
| Soon | Middle-cluster labels in `dft_vs_ml.png` still touch; place labels to avoid overlap | `plot_dft_vs_ml()` |
| Soon | Flag runs whose final pressure is far from the target, or that hit NSW without converging | `collect` in `run_stage5.py` |
| Soon | Watch jobs and restart failed ones, with a limit on retries | stage 5 |
| Soon | Delete large files nobody uses (WAVECAR, CHG, PROCAR) after a run, or switch them off in the INCAR | `slurm_template.sh` or `incar_rules.py` |
| Soon | A `wait` command that blocks until all jobs of a run finish, then runs `collect` automatically | `run_stage5.py` |
| Soon | Feed DFT results back to stage 3: count how often Trusted / Needs DFT was right (here the Trusted control `s009` was off by ~150 meV/atom) | new report in stage 5 |
| Later | Job scripts for other machines (e.g. Adastra) | stage 5 templates |
| Later | Feed DFT results back to improve the model (active learning) | new stage |

---

## Stage 7: compare materials

| Priority | Improvement | Where |
|---|---|---|
| Soon | Calibrate trust limits per chemistry: with the Si-tuned limits, every NaCl and CaSiO₃ structure was flagged | `[stage3]` limits, using the 52 DFT results |
| Soon | Rerun the 6 CaSiO₃ (and 2 NaCl) calculations that hit the quick profile's 60-step limit | stage 4 `--ids`, `NSW` |
| Soon | Standard DFT for NaCl and CaSiO₃, as done for Si | `--profile standard`, archive with `--dft-name dft_standard` |
| Soon | One command for a whole campaign (run, archive, DFT, archive DFT) | `hp-pilot campaign ...` |
| Soon | Perovskite check generalised to other structure families (coordination via pymatgen CrystalNN) | `is_perovskite()` in `run_stage7.py` |
| Later | Transition pressures: run each material at several pressures and plot enthalpy vs pressure (e.g. NaCl B1 to B2 near 27-30 GPa) | new stage 7 figure |
| Later | Compare predicted XRD with measured patterns from the papers found in stage 6 | stage 6 + 7 |

---

## Hackathon materials

| Priority | Improvement | Where |
|---|---|---|
| Tonight | Replace the figure and repository placeholders in the write-up | `hackathon_writeup.md` |
| Tonight | Change any claim in the write-up the code doesn't deliver yet | `hackathon_writeup.md` |
| Tonight | Record the 4-minute video | `video_script.md` |
