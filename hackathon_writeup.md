# HP-Pilot: an open agent that flags when machine-learning models can't be trusted at high pressure

Written for: hackathon judges and materials scientists who run structure searches.

## The problem

Finding new crystal structures under high pressure reveals new materials, from superhard coatings to superconductors and the interiors of giant planets. Machine-learning interatomic potentials make these searches fast enough to be practical. But general-purpose models are trained mostly near ambient conditions, and recent benchmarks show their errors grow sharply at high pressure, sometimes by several eV per atom at 150 GPa. A search that trusts such a model can rank the wrong phase as the most stable.

The accurate method, density functional theory (DFT), is too slow to run on every candidate. Setting up DFT calculations for high pressure also takes expert knowledge: pressure settings, plane-wave cutoffs and magnetic starting values all have to be right.

## What we built

HP-Pilot is an open tool with one command:

    hp-pilot run --composition Si --pressure 15

It works in three stages.

1. **Generate and relax.** It creates random candidate structures with PyXtal and relaxes them at the target pressure with several pretrained machine-learning models.
2. **Check trust.** For each structure it compares the models. If they agree on energy and stress, the structure is marked Trusted. If they disagree, or the structure is strongly compressed, it is marked Needs DFT.
3. **Hand off.** Flagged structures get VASP input files with high-pressure settings and a cluster job script, ready to submit.

An AI agent (Claude, connected through the Model Context Protocol) drives these steps from a plain-language request, and a marimo notebook shows the results.

## Evidence

[Figure placeholder: model disagreement against pressure for NaCl (B1 to B2 transition, about 30 GPa) and Si (diamond to beta-tin, about 11 GPa). The disagreement should rise where the models' accuracy falls. Replace with real results before submission.]

## Why it matters

- **For labs:** it cuts the number of expensive DFT calculations to the structures that actually need them, and it gives a clear reason for each decision.
- **For the community:** it installs with pip, needs no registration, and runs from one command. Researchers can use it without writing code.
- **Novelty:** existing high-pressure search tools such as MAGUS already gate machine-learning results with an internal error estimate. HP-Pilot instead uses agreement between independent pretrained models as the trust signal, and wraps the workflow in an agent that a non-specialist can drive.

## Limitations and next steps

The first version handles ambient-pressure-trained models and a limited set of elements. The next steps are fine-tuning a foundation model on high-pressure data from HPmat, and checking the trust signal against a wider set of known transitions.

## Code

[Repository link placeholder]
