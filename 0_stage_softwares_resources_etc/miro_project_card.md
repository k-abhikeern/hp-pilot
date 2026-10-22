Project name: HP-Pilot (High-Pressure Pilot)

Team members: [Your name], [teammate name if any]

Motivation: Searching for new crystal structures under high pressure is how scientists find new materials for superhard coatings, superconductors and planetary-interior models. Machine-learning models make this search fast, but the general-purpose ones are known to become unreliable at high pressure, and the accurate quantum calculations (DFT) are too slow to run on everything. Setting up those calculations correctly for pressure is also error-prone and needs expert knowledge.

Problem definition:
- General-purpose machine-learning potentials lose accuracy as pressure rises, and nothing flags the structures where that happens.
- Existing structure-search tools need manual setup, and some need registration to get the code.
- Preparing high-pressure DFT input files (pressure settings, cutoffs, magnetism) is tedious and easy to get wrong.

Hackathon target (proof of concept):
A simple command-line tool. You give it a composition and a pressure, for example: hp-pilot run --composition Si --pressure 15
It does three things:
1. Generates candidate crystal structures and relaxes them with several machine-learning models.
2. Gives each structure a trust status: "Trusted" if the models agree, "Needs DFT" if they disagree.
3. Writes ready-to-run VASP input files for the "Needs DFT" structures, and a plot of model disagreement against pressure.
A marimo notebook shows the same results interactively.

Contacts: [your email]
Open to anyone interested in materials science, machine learning or high-performance computing who wants to build this together.
