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

DFT finished in about a minute per job. The two lowest phases are simple hexagonal and beta-tin, only 12 meV apart, and both were flagged for DFT, correctly. And here is the most important point: all eight structures the committee called Trusted were wrong, by over 100 meV per atom. All three models were MACE models, and they shared the same blind spot. We know this only because the pipeline always sends some Trusted structures to DFT as controls.

**[2:40 to 3:15] Literature check. Screen: `literature_check.png`.**

Finally, the Claude agent searched the literature through Valency: 73 papers. It reviewed every match and threw out false ones, like a paper about silicon oxide. The result: beta-tin and simple hexagonal, our two lowest phases, are exactly what papers report near 15 GPa. Phases papers see only at hundreds of gigapascals came out high in our ranking too.

**[3:15 to 3:45] Honest limits and next steps. Screen: limits list.**

These are quick DFT settings, and our committee used one model family. Next we will mix families, including fine-tuned high-pressure models, and recalibrate the trust limits on these DFT results.

**[3:45 to 4:00] Close. Screen: repository link.**

HP-Pilot is open, runs with one command on a normal CPU cluster, and it is built to show when it is wrong. Thank you.
