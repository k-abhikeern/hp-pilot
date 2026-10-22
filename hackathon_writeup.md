# HP-Pilot: an agent-driven pipeline that checks when machine-learning potentials can be trusted at high pressure

## Problem

Machine-learning potentials make crystal-structure searches at high pressure fast, but they are trained mostly near ambient conditions and their errors grow with pressure. A search that trusts them can pick the wrong phase. DFT is accurate but too slow to run on every candidate, and setting it up for high pressure takes expertise.

## What we built

HP-Pilot is an open, eight-stage pipeline run with one command (`./hp-pilot run --composition NaCl --pressure 40 --submit`) on a standard CPU cluster:

1. random symmetric candidates (PyXtal);
2. relaxation at the target pressure with a MACE foundation model;
3. a trust check: a committee of models plus physics checks labels each structure Trusted or Needs DFT, with reasons;
4. VASP inputs with high-pressure settings (pymatgen), hard input checks, and a job plan that reads the cluster load and explains itself;
5. SLURM submission and a DFT-versus-ML comparison;
6. a literature check: the Claude agent searches Valency, reviews every match (excluding false ones with written reasons), and reports which predicted phases are known and at what pressures;
7. a cross-material comparison with pymatgen structure matching, symmetry analysis and simulated XRD;
8. a pressure scan: enthalpy vs pressure for the best phases and the 0 K transition pressure.

A calibration tool fits the trust limits per material on the DFT results.

## Results: three test materials with known answers (60 structures, all checked with DFT)

| | Si, 15 GPa | NaCl, 40 GPa | CaSiO₃, 30 GPa |
|---|---|---|---|
| DFT winner | simple hexagonal | CsCl-type (B2) | cubic perovskite |
| Reported in literature (Valency) | yes, 4 papers | yes, 10 papers | yes, 12 papers |
| ML-only winner | beta-tin (+12 meV/atom in DFT) | wrong phase (+300 meV/atom) | correct |
| Median ML error | 76 meV/atom | 796 meV/atom | 54 meV/atom |

- In all three materials, the pipeline's DFT step lands on the phase the literature reports. For silicon, standard DFT puts simple hexagonal and beta-tin 3.5 meV/atom apart, a tie, as expected near their transition.
- Used alone, the ML model would have picked the wrong NaCl phase, off by more than 1 eV/atom. The trust check flagged every NaCl structure, so this error never went unchecked.
- **Honest failure:** for Si, the 8 structures the all-MACE committee called Trusted were 75 to 130 meV/atom off. The committee shared a blind spot. It was caught because the pipeline always sends Trusted controls to DFT.
- **Transition pressure:** the NaCl rocksalt → CsCl-type transition comes out at **24.6 GPa** in DFT (0 K, quick settings); the ML model gives 23.5 GPa but underestimates how fast CsCl-type gains with pressure (19 vs 111 meV/atom at 50 GPa).
- **Calibration:** fitting the trust limits per material on the DFT results raises the share of wrong ML results caught for Si from 43% to 79%, and the share of right CaSiO₃ results trusted from 0% to 83%. No single limit works for all three materials, and for Si the models agree most where ML is most wrong, so limits must be set per chemistry (fitted and tested on the same small set, so indicative only).

[Figure: `7_stage_compare_materials/outputs/overview.png`. Per material: ML vs DFT ranking of phases, the DFT winner's structure, and its simulated XRD.]

## Why it matters

- **Labs:** DFT time goes where it is needed; every decision (trust labels, job split, literature matches) is logged with a reason.
- **Community:** one command on a CPU cluster; each stage has a plug-in socket for new generators, models, checks and job templates.
- **Built to show when it is wrong:** DFT controls, input checks and a reviewed literature check caught real errors in the model and in our own code.

## Next steps

Mix model families in the committee (MatterSim, eSEN, fine-tuned high-pressure models from Loew et al. 2026); test the calibrated limits on new materials; standard DFT and pressure scans for all materials; temperature effects on transition pressures.

Code: https://github.com/k-abhikeern/hp-pilot
