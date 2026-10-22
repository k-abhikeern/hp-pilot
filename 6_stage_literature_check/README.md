# Stage 6: literature check (Valency)

**Job:** check every predicted phase against published papers, so readers can see which predictions match known results, at which pressures, and which ones are not in the literature we found.

This is the stage where the **AI agent** does real work: it runs the literature searches (through the Valency tool) and reviews the matches. The Python code prepares the searches and turns the results into a report and a figure.

## Run it

```bash
cd /home/abhikeern/project/7_OSI/6_stage_literature_check
~/miniconda3/envs/osi/bin/python run_stage6.py prepare     # 1. list phases and search queries -> outputs/queries.json
# 2. the agent (Claude with Valency) runs the queries; saved results are merged with:
~/miniconda3/envs/osi/bin/python import_valency.py outputs/raw_valency/*.json
~/miniconda3/envs/osi/bin/python run_stage6.py report      # 3. classify, report, figure
```

To ask the agent for step 2, say for example: *"Run the stage 6 queries in outputs/queries.json on Valency, save the raw results in outputs/raw_valency/, and review the evidence."*

## I want to... (where to change things)

| I want to... | Do this |
|---|---|
| check a different material | change `composition` in `config.toml`, rerun stages 1 to 3, then stage 6 |
| teach it more phase names (e.g. for oxides) | add to `ELEMENT_STRUCTURE_NAMES` or `BINARY_STRUCTURE_NAMES` in `run_stage6.py` |
| remove a false match | add it to `exclude` in `outputs/review.json` under its space group, with a reason |
| add a paper the automatic rule missed | add it to `include` in `outputs/review.json`, with a reason (and pressures if known) |
| add more search results | save another Valency result file in `outputs/raw_valency/`, rerun `import_valency.py` and `report` |

## How a phase is classified

- **Known**: at least one paper names the material and the phase **in the same sentence**. That sentence is saved as evidence in the report.
- **Not found**: none of the retrieved papers does. This does **not** mean "new": the phase may be named differently, be a distorted version of a known phase, or simply not be among the papers retrieved.
- **Review**: the agent read every evidence sentence and recorded decisions in `outputs/review.json`, each with a reason. Excluded papers are still listed in the report.
- **Pressures**: numbers followed by "GPa" in the evidence sentences are collected for the right-hand panel of the figure.

## Files

| File | What it is |
|---|---|
| `run_stage6.py` | prepare and report |
| `import_valency.py` | merges saved Valency result files and removes duplicate papers |
| `outputs/queries.json` | phases, common names, search queries |
| `outputs/raw_valency/` | the agent's raw search results, kept for checking |
| `outputs/valency_results.json` | merged papers (title, date, link, abstract) |
| `outputs/review.json` | the agent's review decisions, each with a reason |
| `outputs/literature_report.md` | report in words, with evidence sentences and links |
| `outputs/literature_report.csv` | one row per phase |
| `outputs/literature_check.png` | summary figure |

## Results (Si at 15 GPa, 73 papers from Valency)

| Phase | Our result | Literature |
|---|---|---|
| beta-tin (I4₁/amd) | ML best; DFT +12 meV/atom | Known, 12 papers; reported at 7.5 to 16 GPa, around our 15 GPa |
| simple hexagonal (P6/mmm) | DFT best | Known, 4 papers (Si-V, reached from beta-tin via Imma) |
| simple cubic (Pm-3m) | DFT +165 meV/atom | Known only as a prediction above 3.9 TPa |
| fcc, hcp | ML +100 to +116 meV/atom | Known only at about 40 to 390 GPa and above |
| Cmcm, P4/nmm, I4/mmm, P6₃/m, P4₂/mmc, P6₃22 | ML +12 to +182 meV/atom | Not found |

**What this says:**
- The two structures DFT finds lowest at 15 GPa, beta-tin and simple hexagonal, are exactly the phases the literature reports around this pressure. That's independent support for the pipeline.
- Phases the literature only sees at much higher pressure (fcc, hcp, simple cubic) are ranked high in enthalpy by our pipeline too.
- The "Not found" phases are mostly high in enthalpy, so they're more likely metastable leftovers than discoveries. The low-lying Cmcm and P4/nmm (+12 meV/atom) may be distorted forms of known phases (for example Imma, which sits between beta-tin and simple hexagonal) and are worth a DFT check.
