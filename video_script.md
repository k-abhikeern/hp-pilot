# HP-Pilot: 4-minute video script

Speak at normal pace (the rules forbid speeding up the voice). One screen per section.

---

**[0:00 to 0:25] Hook. Screen: pressure-temperature diagram or a diamond anvil cell.**

Under high pressure, atoms form structures that never exist at home, the kind found inside planets and in new superhard or superconducting materials. Computers search for them, and machine-learning models make that search fast.

**[0:25 to 0:50] Problem. Screen: error-vs-pressure table from Loew et al. 2026.**

But these models are trained mostly near normal pressure, and their errors grow as pressure rises. If you trust them blindly, you can pick the wrong structure. DFT is accurate, but too slow to run on everything.

**[0:50 to 1:20] The idea. Screen: the six-stage diagram.**

HP-Pilot asks one question for each candidate: can I trust the fast model here? It generates candidates, relaxes them at pressure, and a committee of models votes. If they agree, Trusted. If not, Needs DFT, with the reason written down.

**[1:20 to 2:00] Demo. Screen: terminal.**

One command: `./hp-pilot run --composition Si --pressure 15 --submit`. In two minutes it makes 20 silicon structures, relaxes them, labels them, writes VASP inputs with the right pressure settings, reads how busy the cluster is, explains how it split the jobs, and submits them.

*(Show `job_plan.md` and `trust_plot.png`.)*

**[2:00 to 2:40] Results. Screen: `dft_vs_ml.png`.**

We ran DFT on all twenty, first with quick settings, then with tight ones; each job took a few minutes. The two lowest phases are simple hexagonal and beta-tin, only 3.5 meV apart, practically a tie, and both were flagged for DFT, correctly. And here is the most important point: all eight structures the committee called Trusted were wrong, by 75 to 130 meV per atom, even with tight settings. All three models were MACE models, and they shared the same blind spot. We know this only because the pipeline always sends some Trusted structures to DFT as controls.

**[2:40 to 3:20] Three materials and the literature. Screen: `7_stage_compare_materials/outputs/overview.png`.**

We then tested two more materials with known answers: table salt at 40 gigapascals, and calcium silicate perovskite, a key mineral of Earth's mantle. The Claude agent checked every prediction against the literature through Valency, and threw out false matches, for example papers that use "NaCl-type" for other compounds. In all three cases, the DFT step lands on the phase the literature reports: simple hexagonal silicon, CsCl-type salt, and cubic perovskite. The ML model alone would have picked the wrong salt structure, off by more than one electronvolt per atom; the trust check flagged all of those structures.

**[3:20 to 3:45] Transition pressure and calibration. Screens: `8_stage_pressure_scan/outputs/enthalpy_vs_pressure_NaCl_40GPa.png`, then `3_stage_trust_check/calibration/calibration.png`.**

Over pressure, DFT puts salt's transition at about 25 gigapascals; the ML model gets close but underestimates how fast the new phase wins. Tuning the trust check on the DFT results lifts silicon's catch rate from 43 to 79 percent. The lesson: settings must be per material, and the committee needs different model families. That's our next step.

**[3:45 to 4:00] Close. Screen: repository link.**

HP-Pilot is open, runs with one command on a normal CPU cluster, and it is built to show when it is wrong. Thank you.
