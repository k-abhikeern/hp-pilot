"""Stage 6: check our predicted phases against the published literature (via Valency).

Three steps:
  1. python run_stage6.py prepare   -> outputs/queries.json: every predicted phase, its common name and
                                       the search queries to run
  2. the agent (Claude, with the Valency tool) runs those queries and saves what it finds in
     outputs/valency_results.json   (format below)
  3. python run_stage6.py report    -> for each phase: Known / Related / New, the pressures papers
                                       report for it, the most relevant papers with links, and a figure

valency_results.json format (written by the agent):
    {"source": "...", "searched_at": "...", "queries": ["..."],
     "papers": [{"id": "...", "title": "...", "date": "YYYY-MM-DD", "url": "...", "citation_count": 0,
                 "abstract": "..."}]}

Outputs (in outputs/):
    queries.json             phases and queries (step 1)
    valency_results.json     papers found by the agent (step 2)
    literature_report.csv    one row per phase: status, number of papers, reported pressures
    literature_report.md     the same in words, with links to the papers
    literature_check.png     summary figure
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from pymatgen.core import Composition

STAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = STAGE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
from hp_common import get_logger, load_config, save_run_info, stage_dirs  # noqa: E402

STAGE2 = PROJECT_ROOT / "2_stage_relax" / "outputs" / "results.csv"
STAGE3 = PROJECT_ROOT / "3_stage_trust_check" / "outputs" / "trust_report.csv"
STAGE5 = PROJECT_ROOT / "5_stage_vasp_run" / "outputs" / "dft_results.csv"

# Common names of structure types, so papers can be found by the words authors actually use.
# Extend these dictionaries for other material classes.
ELEMENT_STRUCTURE_NAMES = {
    "Fd-3m": ["diamond"],
    "I4_1/amd": ["beta-tin", "β-tin", "beta-Sn", "β-Sn", "beta tin"],
    "Imma": ["Imma"],
    "P6/mmm": ["simple hexagonal", "simple-hexagonal", "sh phase"],
    "Pm-3m": ["simple cubic", "simple-cubic"],
    "P6_3/mmc": ["hexagonal close-packed", "hexagonal close packed", "hcp"],
    "Fm-3m": ["face-centered cubic", "face-centred cubic", "fcc"],
    "Im-3m": ["body-centered cubic", "body-centred cubic", "bcc"],
    "Cmca": ["Cmca", "Cmce"],
    "Cmcm": ["Cmcm"],
    "Ia-3": ["BC8"],
    "I4/mmm": ["body-centered tetragonal", "body-centred tetragonal", "bct"],
}
BINARY_STRUCTURE_NAMES = {
    "Fm-3m": ["rocksalt", "rock-salt", "B1"],
    "Pm-3m": ["CsCl", "B2"],
    "F-43m": ["zinc blende", "zincblende", "B3"],
    "P6_3/mc": ["wurtzite", "B4"],
}
GPA_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*)?GPa")


def phase_names(space_group, n_elements):
    names = (ELEMENT_STRUCTURE_NAMES if n_elements == 1 else BINARY_STRUCTURE_NAMES).get(space_group, [])
    # The space-group symbol is always a search term too, in the two ways papers write it.
    return names + [space_group, space_group.replace("_", "")]


# ---------- prepare ----------

def prepare(cfg, out_dir, log):
    composition = Composition(cfg["project"]["composition"]).reduced_composition
    elements = [el.long_name.lower() for el in composition.elements]
    material = elements[0] if len(elements) == 1 else composition.reduced_formula

    sg_of = {r["id"]: r["space_group_after"].split(" (")[0] for r in csv.DictReader(open(STAGE2))}
    trust = list(csv.DictReader(open(STAGE3)))
    dft = {r["id"]: r for r in csv.DictReader(open(STAGE5))} if STAGE5.exists() else {}

    phases = defaultdict(lambda: {"structures": [], "labels": [], "ml_dH_meV": []})
    for r in trust:
        sg = sg_of[r["id"]]
        phases[sg]["structures"].append(r["id"])
        phases[sg]["labels"].append(r["label"])
        phases[sg]["ml_dH_meV"].append(float(r["dH_meV_per_atom"]))

    out = []
    for sg, p in sorted(phases.items(), key=lambda kv: min(kv[1]["ml_dH_meV"])):
        terms = phase_names(sg, len(composition.elements))
        dft_rows = [dft[i] for i in p["structures"] if i in dft and dft[i].get("dft_dH_meV")]
        out.append({
            "space_group": sg,
            "name": terms[0] if terms[0] != sg else sg,
            "search_terms": terms,
            "query": f"{material} {terms[0]} phase high pressure",
            "structures": p["structures"],
            "trust_labels": sorted(set(p["labels"])),
            "best_ml_dH_meV": round(min(p["ml_dH_meV"]), 1),
            "dft_dH_meV": round(min(float(d["dft_dH_meV"]) for d in dft_rows), 1) if dft_rows else None,
        })
    data = {"composition": composition.reduced_formula, "material_name": material,
            "pressure_gpa": cfg["project"]["pressure_gpa"],
            "general_query": f"{material} high pressure phase transitions crystal structure",
            "phases": out}
    (out_dir / "queries.json").write_text(json.dumps(data, indent=2))
    log.info("Stage 6 prepare | %s at %g GPa | %d phases", data["composition"], data["pressure_gpa"], len(out))
    for p in out:
        log.info("  %-10s %-20s structures %s | query: %s", p["space_group"], p["name"],
                 ",".join(p["structures"]), p["query"])
    log.info("Next: the agent runs these queries on Valency and saves outputs/valency_results.json, "
             "then run:  run_stage6.py report")


# ---------- report ----------

def mentions(text, terms):
    """True if any search term appears in the text as a whole word (case-insensitive)."""
    return any(re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", text, re.IGNORECASE)
               for t in terms)


def sentences(text):
    return re.split(r"(?<=[.;])\s+", text)


def evidence(paper, material_terms, phase_terms):
    """Sentences (title included) that name both the material and the phase."""
    return [s for s in [paper["title"]] + sentences(paper["abstract"])
            if mentions(s, material_terms) and mentions(s, phase_terms)]


def pressures_in(sentence_list):
    values = []
    for s in sentence_list:
        for low, high in GPA_PATTERN.findall(s):
            values += [float(low)] + ([float(high)] if high else [])
    return values


def classify(data, papers, review):
    """A phase is Known if at least one paper names the material and the phase in the same sentence.
    review.json can, per phase, exclude false matches or include papers the sentence rule missed;
    every review decision carries a reason and is shown in the report."""
    material = data["material_name"]
    material_terms = [material, data["composition"]]
    about_material = [p for p in papers if mentions(p["title"] + " " + p["abstract"], material_terms)]
    by_id = {p["id"]: p for p in papers}
    rows = []
    for ph in data["phases"]:
        excluded = review.get("exclude", {}).get(ph["space_group"], {})
        included = review.get("include", {}).get(ph["space_group"], {})
        hits, pressures, dropped = [], [], []
        for p in about_material:
            found = evidence(p, material_terms, ph["search_terms"])
            if not found or p["id"] in included:
                continue
            if p["id"] in excluded:
                dropped.append({"paper": p, "reason": excluded[p["id"]]})
                continue
            hits.append({**p, "evidence": found[0]})
            pressures += [(v, p["id"]) for v in pressures_in(found)]
        for pid, entry in included.items():
            if pid in by_id:
                hits.append({**by_id[pid], "evidence": f"[added on review] {entry['reason']}"})
                pressures += [(v, pid) for v in entry.get("pressures_gpa", [])]
        if hits:
            status = "Known"
            why = f"{len(hits)} paper(s) name {material} and this phase in the same sentence"
        else:
            status = "Not found"
            why = (f"{len(about_material)} paper(s) study {material}, none names this phase"
                   if about_material else "no papers found for this material")
        top = sorted(hits, key=lambda p: -(p.get("citation_count") or 0))[:3]
        rows.append({**ph, "status": status, "why": why, "n_papers": len(hits), "excluded": dropped,
                     "reported_pressures_GPa": sorted({round(v, 1) for v, _ in pressures}),
                     "pressure_sources": pressures, "top_papers": top})
    return rows, about_material


def plot(rows, data, path):
    """Left: how many papers mention each predicted phase. Right: pressures those papers report for it,
    against the pressure we predicted at. Phases are ordered from most to least stable (ML)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid, surface = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
    color = {"Known": "#2a78d6", "Not found": "#eb6834"}
    rows = rows[::-1]  # most stable at the top
    labels = []
    for r in rows:
        dft = f", DFT +{r['dft_dH_meV']:g}" if r["dft_dH_meV"] is not None else ""
        labels.append(f"{r['name']} ({r['space_group']})\nML +{r['best_ml_dH_meV']:g} meV{dft} · "
                      f"{'/'.join(r['trust_labels'])}")
    y = range(len(rows))

    fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True, figsize=(11, 0.75 * len(rows) + 1.8),
                                   gridspec_kw={"width_ratios": [1, 1.6]}, facecolor=surface)
    for ax in (ax1, ax2):
        ax.set_facecolor(surface)
        ax.grid(axis="x", color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#c3c2b7")
        ax.tick_params(axis="x", colors=muted)

    ax1.barh(list(y), [r["n_papers"] for r in rows], color=[color[r["status"]] for r in rows],
             height=0.6, edgecolor=surface, linewidth=2)
    for yi, r in zip(y, rows):
        ax1.text(r["n_papers"], yi, f" {r['n_papers']} · {r['status']}", va="center", fontsize=8, color=ink)
    ax1.set_yticks(list(y), labels, fontsize=8, color=ink)
    ax1.set_xlabel("Papers mentioning this phase", color=ink)
    ax1.set_xlim(0, max(r["n_papers"] for r in rows) * 1.6 + 1)
    ax1.set_title("Is the predicted phase in the literature?", loc="left", fontsize=10, color=ink)

    for yi, r in zip(y, rows):
        xs = [v for v, _ in r["pressure_sources"]]
        if xs:
            ax2.scatter(xs, [yi] * len(xs), s=40, color=color[r["status"]], alpha=0.8,
                        edgecolors=surface, linewidths=1, zorder=3, clip_on=False)
    target = data["pressure_gpa"]
    ax2.axvline(target, color=ink, lw=1.2, ls="--", zorder=2)
    ax2.text(target, len(rows) - 0.4, f" our prediction: {target:g} GPa", fontsize=8, color=ink, va="bottom")
    ax2.set_xscale("symlog", linthresh=10)
    ax2.set_xlim(left=0)
    ax2.set_xlabel("Pressure mentioned with this phase in the papers (GPa)", color=ink)
    ax2.set_title("At what pressures do papers report it?", loc="left", fontsize=10, color=ink)
    ax2.set_ylim(-0.6, len(rows) - 0.1)

    fig.suptitle(f"Literature check of predicted {data['composition']} phases (Valency, "
                 f"{sum(r['n_papers'] for r in rows)} phase mentions)", x=0.01, ha="left", fontsize=12, color=ink)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def report(cfg, out_dir, log):
    data = json.loads((out_dir / "queries.json").read_text())
    results_file = out_dir / "valency_results.json"
    if not results_file.exists():
        sys.exit("outputs/valency_results.json not found. The agent must run the Valency queries first.")
    found = json.loads(results_file.read_text())
    papers = found["papers"]
    review_file = out_dir / "review.json"
    review = json.loads(review_file.read_text()) if review_file.exists() else {}
    rows, about_material = classify(data, papers, review)

    for r in rows:
        log.info("%-10s %-20s %-9s %2d paper(s) | pressures %s | %s", r["space_group"], r["name"], r["status"],
                 r["n_papers"], r["reported_pressures_GPa"][:8], r["why"])

    with open(out_dir / "literature_report.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["space_group", "name", "structures", "trust_labels", "best_ml_dH_meV", "dft_dH_meV",
                         "status", "n_papers", "reported_pressures_GPa", "top_paper_urls"])
        for r in rows:
            writer.writerow([r["space_group"], r["name"], " ".join(r["structures"]), "/".join(r["trust_labels"]),
                             r["best_ml_dH_meV"], r["dft_dH_meV"], r["status"], r["n_papers"],
                             " ".join(map(str, r["reported_pressures_GPa"])),
                             " ".join(p["url"] for p in r["top_papers"])])

    lines = [f"# Literature check: {data['composition']} at {data['pressure_gpa']:g} GPa", "",
             f"Source: {found['source']}, searched {found['searched_at']}. "
             f"{len(papers)} papers retrieved, {len(about_material)} about {data['material_name']}.", "",
             "**Status** means: *Known* = at least one paper names this material and this phase in the "
             "same sentence. *Not found* = no retrieved paper does (it may be new, named differently, or "
             "simply not among the papers retrieved). A mention is not proof that the phase is stable at our "
             "pressure; the evidence sentence is shown for each paper so it can be checked.", "",
             f"Review ({review.get('reviewed_by', 'none')}): "
             f"{sum(len(r['excluded']) for r in rows)} false match(es) excluded, listed at the end with the "
             "reason; papers added on review are marked [added on review].", "",
             "| Phase | Our structures | Trust label | ML above best | DFT above best | Status | Papers | Pressures in papers (GPa) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        dft = f"{r['dft_dH_meV']:g} meV" if r["dft_dH_meV"] is not None else "not run"
        p = ", ".join(f"{v:g}" for v in r["reported_pressures_GPa"][:10]) or "none stated"
        lines.append(f"| {r['name']} ({r['space_group']}) | {', '.join(r['structures'])} | "
                     f"{'/'.join(r['trust_labels'])} | {r['best_ml_dH_meV']:g} meV | {dft} | {r['status']} | "
                     f"{r['n_papers']} | {p} |")
    lines += ["", "## Most relevant papers per phase", ""]
    for r in rows:
        if r["top_papers"]:
            lines.append(f"**{r['name']} ({r['space_group']})**")
            for p in r["top_papers"]:
                lines.append(f"- [{p['title']}]({p['url']}) ({p['date'][:4]})")
                lines.append(f"  > {p['evidence'][:300]}")
            lines.append("")
    dropped = [(r, d) for r in rows for d in r["excluded"]]
    if dropped:
        lines += ["## Excluded after review", "", "| Phase | Paper | Reason |", "|---|---|---|"]
        lines += [f"| {r['name']} | [{d['paper']['title'][:80]}]({d['paper']['url']}) | {d['reason']} |"
                  for r, d in dropped]
    (out_dir / "literature_report.md").write_text("\n".join(lines) + "\n")

    plot(rows, data, out_dir / "literature_check.png")
    counts = {s: sum(r["status"] == s for r in rows) for s in ("Known", "Not found")}
    save_run_info(out_dir, {"stage": 6, "source": found["source"], "n_papers": len(papers), "counts": counts})
    log.info("Stage 6 report done | %s | outputs in %s", counts, out_dir)


def main():
    parser = argparse.ArgumentParser(description="Stage 6: literature check of predicted phases.")
    parser.add_argument("command", choices=["prepare", "report"])
    parser.add_argument("--config", help="settings file (default: ../config.toml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    out_dir, log_dir = stage_dirs(STAGE_DIR)
    log, _ = get_logger(f"stage6_{args.command}", log_dir)
    (prepare if args.command == "prepare" else report)(cfg, out_dir, log)


if __name__ == "__main__":
    main()
