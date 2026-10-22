# Stage 7: compare materials

**Job:** keep each material's results safe in its own folder, and combine several materials into summary figures and a scorecard: which phase wins in DFT, was it in the literature, and how well did the trust check do?

## Run it

```bash
cd /home/abhikeern/project/7_OSI
# 1. run the pipeline for a material (stages 1-4, stage 6 prepare)
./hp-pilot run --composition NaCl --pressure 40 --formula-units 1 2 4
# 2. save the ML results before the next material overwrites them
~/miniconda3/envs/osi/bin/python 7_stage_compare_materials/archive_campaign.py NaCl_40GPa
# 3. DFT on all structures (quick), then submit
IDS=$(tail -n +2 3_stage_trust_check/outputs/trust_report.csv | cut -d, -f1 | tr '\n' ' ')
~/miniconda3/envs/osi/bin/python 4_stage_incar_build/run_stage4.py --ids $IDS --profile quick --n-batches 10
~/miniconda3/envs/osi/bin/python 5_stage_vasp_run/run_stage5.py submit
# 4. when the jobs are done: save the DFT results of that run folder
~/miniconda3/envs/osi/bin/python 7_stage_compare_materials/archive_campaign.py NaCl_40GPa --dft-run 5_stage_vasp_run/runs/run_<date>_<time>
# 5. literature check on the archived material (the agent runs the Valency searches in between)
~/miniconda3/envs/osi/bin/python 6_stage_literature_check/run_stage6.py prepare --campaign 7_stage_compare_materials/campaigns/NaCl_40GPa
~/miniconda3/envs/osi/bin/python 6_stage_literature_check/run_stage6.py report  --campaign 7_stage_compare_materials/campaigns/NaCl_40GPa
# 6. combine all materials
~/miniconda3/envs/osi/bin/python 7_stage_compare_materials/run_stage7.py
```

## I want to... (where to change things)

| I want to... | Do this |
|---|---|
| add a new material | steps 1 to 5 above with a new label, then step 6 |
| use standard instead of quick DFT | archive with `--dft-name dft_standard`, then `run_stage7.py --dft-name dft_standard` |
| compare only some materials | `run_stage7.py --campaigns Si_15GPa NaCl_40GPa` |
| change what counts as an ML error | `ERROR_LIMIT_MEV` at the top of `run_stage7.py` (default 50 meV/atom) |
| change when two structures count as the same phase | `group_phases()` in `run_stage7.py` (geometry via pymatgen StructureMatcher, plus DFT enthalpy within 5 meV/atom) |

## What it does

- **Same-phase grouping (pymatgen `StructureMatcher`):** many random starts relax to the same crystal; these are grouped so each phase is counted once. Two structures must match geometrically *and* have DFT enthalpies within 5 meV/atom (geometry alone wrongly joined two NaCl structures 300 meV/atom apart).
- **Symmetry and standard cell (pymatgen `SpacegroupAnalyzer`)** for every phase.
- **Simulated XRD (pymatgen `XRDCalculator`)** of each material's DFT winner, with the strongest peaks labelled by Miller indices.
- **Crystal picture (ASE `plot_atoms`)** of each winner with an element key.
- **Literature** from stage 6, matched by the phase's DFT symmetry.
- **Scorecard per material:**
  - How many Trusted structures were truly fine (ML error ≤ 50 meV/atom)?
  - How many Needs DFT structures really had a large ML error?
  - Median and largest ML error.

## Files

| File | What it is |
|---|---|
| `archive_campaign.py` | saves one material's results into `campaigns/<label>/` |
| `run_stage7.py` | combines campaigns into figures and tables |
| `campaigns/<label>/` | per material: settings, ML ranking, trust report, literature check, `dft/` (and `dft_standard/`) with DFT results and final structures |
| `outputs/overview.png` | per material: ML vs DFT for each phase, picture and XRD of the DFT winner |
| `outputs/ml_vs_dft_all.png` | every structure of every material, ML vs DFT |
| `outputs/summary.md` | one row per material: winners, literature, scorecard |
| `outputs/phases_<label>.csv` | one row per phase |
