# HP-Pilot: results across materials

DFT settings: `dft`. An ML error above 50 meV/atom counts as wrong.

| Material | Structures (DFT) | Distinct phases | DFT winner | In literature? | ML winner | ML winner in DFT | Trusted: truly OK | Needs DFT: ML really wrong | Median / max ML error (meV/atom) |
|---|---|---|---|---|---|---|---|---|---|
| Si at 15 GPa | 20 | 15 | simple hexagonal (P6/mmm) | Known (4 papers) | beta-tin (I4_1/amd) | +12 meV/atom | 0 of 8 | 6 of 12 | 76 / 693 |
| NaCl at 40 GPa | 18 | 14 | CsCl (Pm-3m) | Known (10 papers) | P4/mmm (P4/mmm) | +300 meV/atom | 0 of 0 | 18 of 18 | 796 / 1092 |
| CaSiO3 at 30 GPa | 14 | 12 | cubic perovskite (Pm-3m) | Known (12 papers) | cubic perovskite (Pm-3m) | +0 meV/atom | 0 of 0 | 8 of 14 | 54 / 162 |
