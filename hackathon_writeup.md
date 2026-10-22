# HP-Pilot: an agent-driven pipeline that checks when machine-learning potentials can be trusted at high pressure

## Problem

Machine-learning potentials make crystal-structure searches at high pressure fast, but they are trained mostly near ambient conditions and their errors grow with pressure. A search that trusts them can rank the wrong phase as most stable. DFT is accurate but too slow to run on every candidate, and setting it up for high pressure takes expertise.

## What we built

HP-Pilot is an open, six-stage pipeline run with one command (`./hp-pilot run --composition Si --pressure 15 --submit`):

1. random symmetric candidates (PyXtal);
2. relaxation at the target pressure with a MACE foundation model;
3. a trust check: a committee of models plus physics checks labels each structure Trusted or Needs DFT, with reasons;
4. VASP inputs with high-pressure settings (pymatgen), hard input checks, and a job plan that reads the cluster load and explains itself;
5. SLURM submission and a DFT-versus-ML comparison;
6. a literature check: the Claude agent searches Valency, reviews every match, and the pipeline reports which predicted phases are known and at what pressures.

## Results (silicon, 15 GPa, CPU cluster)

- 20 candidates, ML relaxation in about 2 minutes; all 20 then checked with DFT twice, with quick and with standard settings (1 to 4 minutes per job).
- DFT puts simple hexagonal and beta-tin as the lowest phases, only 3.5 meV/atom apart with standard settings, so practically degenerate. The literature check (73 papers via Valency) independently reports exactly these two phases around this pressure (7.5 to 16 GPa). Both were flagged Needs DFT, correctly.
- **Key finding:** all 8 structures the committee called Trusted were wrong by 75 to 130 meV/atom (standard settings; ML put them about 12 meV/atom above the best, DFT 87 to 144). The three committee members were all MACE models and shared the same blind spot. The pipeline caught this because it always sends Trusted controls to DFT.
- Quick and standard DFT agree on the overall ranking (rank correlation 0.91; mean change 25 meV/atom), so quick settings are good enough for screening.

[Figure: `5_stage_vasp_run/outputs/dft_vs_ml.png`. ML vs DFT enthalpy above the best structure; Trusted structures (green) sit far above the ML = DFT line.]

## Why it matters

- **Labs:** DFT time goes where it is needed, and every decision is logged with a reason.
- **Community:** runs from one command on a standard CPU cluster; every stage has a plug-in socket for new generators, models, checks and job templates.
- **Honest validation:** DFT controls and a literature check are built in, so the tool can show when it is wrong.

## Limits and next steps

Committee limited to one model family; trust limits are first guesses; one material at one pressure so far. Next: mix model families (MatterSim, eSEN, fine-tuned high-pressure models from Loew et al. 2026), recalibrate the limits on these DFT results, and test more materials and pressures.

Code: [repository link]
