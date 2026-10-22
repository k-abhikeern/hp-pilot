# HP-Pilot: 4-minute video script

Written for: hackathon judges. Speak at a normal pace, not faster. Target length about 4 minutes.

---

**[0:00 to 0:25] Hook. Show a slide with a pressure-temperature phase diagram.**

Under high pressure, atoms arrange themselves into structures that never form at home. Those structures can make superhard materials, superconductors and the interiors of giant planets. Finding them is a search problem, and computers do most of the work.

**[0:25 to 0:55] The problem. Show a plot of model error rising with pressure.**

The fast tool for this search is a machine-learning model. But general-purpose models are trained mostly near ambient conditions. At 150 gigapascals their errors can reach several electronvolts per atom. A search that trusts such a model can rank the wrong structure as the most stable one, and nothing warns you.

The accurate tool, DFT, is too slow to run on everything.

**[0:55 to 1:25] The idea. Show the three-step diagram.**

HP-Pilot answers one question for every candidate structure: can I trust the fast model here?

It relaxes each structure with several independent pretrained models. If they agree, the structure is marked Trusted. If they disagree, it is marked Needs DFT.

**[1:25 to 2:00] Live demo. Show the terminal, then the notebook.**

Here is the whole tool in one command:

    hp-pilot run --composition Si --pressure 15

The output lists the candidate structures, each with a trust status. For the flagged ones, the tool writes VASP input files with high-pressure settings and a job script, ready to submit to a cluster. A plot shows disagreement against pressure.

**[2:00 to 2:40] How it works. Show the agent and the code.**

An AI agent sits on top of the tool. You can type a plain-language request, such as "find silicon phases at 15 gigapascals", and the agent runs the steps and explains each decision. The tool itself is an ordinary Python package, so the agent is optional.

**[2:40 to 3:15] Why it matters. Show the evidence plot.**

On known transitions, such as sodium chloride going from the B1 to the B2 structure near 30 gigapascals, the disagreement rises at the pressures where the models get it wrong. That is the signal we use to decide when DFT is needed.

For labs, that means fewer expensive calculations and a clear reason for each decision. For the community, it installs with pip, needs no registration, and runs from one command.

**[3:15 to 3:45] Honest limits and next steps. Show the limits slide.**

The first version handles a limited set of elements and uses pretrained models as they are. Next we want to fine-tune a foundation model on high-pressure data and test the trust signal on more transitions. Existing tools such as MAGUS already gate machine-learning results with their own error estimate. Our difference is the cross-model trust signal and the easy-to-use agent layer.

**[3:45 to 4:00] Close. Show the repository link and your name.**

HP-Pilot is open, installs with one command, and is built to be checked. The code and notebook are linked below. Thank you.

---

*Production notes:* record at your own pace, do not speed up your voice (the rules require normal speed). Each slide above should be one screen. Post the video publicly with no login required, for example as a public YouTube video or a public thread.
