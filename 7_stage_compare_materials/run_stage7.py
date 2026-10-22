"""Stage 7: compare materials. Combines archived campaigns (one per material) into summary figures and tables.

    ~/miniconda3/envs/osi/bin/python run_stage7.py                    # all campaigns, quick DFT ("dft" folders)
    ~/miniconda3/envs/osi/bin/python run_stage7.py --dft-name dft_standard --campaigns Si_15GPa

For each material it uses pymatgen to
  - group DFT-relaxed structures that are the same crystal (StructureMatcher), so each phase appears once,
  - find each phase's symmetry and standard cell (SpacegroupAnalyzer),
  - simulate the X-ray diffraction pattern of the most stable phase (XRDCalculator),
and ASE to draw that phase.

Outputs (in outputs/):
    overview.png          per material: ML vs DFT ranking of phases, picture and XRD of the DFT winner
    ml_vs_dft_all.png     every structure of every material: ML vs DFT enthalpy, by trust label
    summary.md / .csv     one row per material: winner in ML and DFT, literature, trust-check scorecard
    phases_<label>.csv    one row per phase for each material
"""
import argparse
import csv
import json
import sys
import tomllib
from pathlib import Path

import numpy as np

STAGE_DIR = Path(__file__).resolve().parent
ROOT = STAGE_DIR.parent
sys.path.insert(0, str(ROOT / "6_stage_literature_check"))
from run_stage6 import phase_names  # noqa: E402  (common names of structure types)

INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
STATUS = {"Trusted": "#0ca30c", "Needs DFT": "#d03b3b"}
MATERIAL_MARKERS = ["o", "s", "D", "^", "v", "P"]
ERROR_LIMIT_MEV = 50  # an ML error above this counts as "ML was wrong" in the scorecard


def load_campaign(folder, dft_name):
    """DFT rows (converged only) with each structure's final DFT geometry, plus settings and literature."""
    from pymatgen.core import Structure
    cfg = tomllib.loads((folder / "last_run_config.toml").read_text())
    rows = []
    for r in csv.DictReader(open(folder / dft_name / "dft_results.csv")):
        contcar = folder / dft_name / f"CONTCAR_{r['name']}"
        if r.get("dft_status") != "converged" or not contcar.exists():
            continue
        s = Structure.from_file(contcar)
        s.properties["name"] = r["name"]
        rows.append({**r, "structure": s, "ml_H": float(r["ml_enthalpy_eV_per_atom"]),
                     "dft_H": float(r["dft_enthalpy_eV_per_atom"])})
    skipped = sum(1 for _ in csv.DictReader(open(folder / dft_name / "dft_results.csv"))) - len(rows)
    ml0, dft0 = min(r["ml_H"] for r in rows), min(r["dft_H"] for r in rows)
    for r in rows:
        r["ml_dH"], r["dft_dH"] = 1000 * (r["ml_H"] - ml0), 1000 * (r["dft_H"] - dft0)
    lit = {}
    lit_file = folder / "literature" / "literature_report.csv"
    if lit_file.exists():
        lit = {r["space_group"]: r for r in csv.DictReader(open(lit_file))}
    return cfg, rows, skipped, lit


def is_perovskite(structure):
    """A perovskite ABX3 has its smaller cation (B) surrounded by 6 anions (an octahedron)."""
    from ase.data import atomic_numbers, covalent_radii
    els = sorted(structure.composition.elements, key=lambda e: e.X)  # least to most electronegative
    if len(els) != 3:
        return False
    anion = els[-1]
    b_site = min(els[:2], key=lambda e: covalent_radii[atomic_numbers[str(e)]])
    cutoff = 1.25 * (covalent_radii[atomic_numbers[str(b_site)]] + covalent_radii[atomic_numbers[str(anion)]])
    counts = [sum(1 for nb in structure.get_neighbors(site, cutoff) if nb.specie == anion)
              for site in structure if site.specie == b_site]
    return bool(counts) and all(c == 6 for c in counts)


def group_phases(rows, n_elements, lit):
    """Group structures that DFT relaxed into the same crystal; one entry per phase, best first."""
    from pymatgen.analysis.structure_matcher import StructureMatcher
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    by_name = {r["name"]: r for r in rows}
    matched = StructureMatcher(ltol=0.2, stol=0.3, angle_tol=5).group_structures([r["structure"] for r in rows])
    # The matcher's geometric tolerance can join different small cells; also require (almost) the same
    # DFT enthalpy, so a group really is one phase.
    groups = []
    for g in matched:
        for r in sorted((by_name[s.properties["name"]] for s in g), key=lambda r: r["dft_H"]):
            if groups and groups[-1][0] is g and abs(r["dft_H"] - groups[-1][1][0]["dft_H"]) < 0.005:
                groups[-1][1].append(r)
            else:
                groups.append((g, [r]))
    phases = []
    for _, members in groups:
        best = members[0]
        sga = SpacegroupAnalyzer(best["structure"], symprec=0.1)
        sg = sga.get_space_group_symbol()
        names = phase_names(sg, n_elements)
        # Literature is matched by the DFT symmetry only: a structure DFT changed is a different phase.
        lit_row = lit.get(sg)
        if "perovskite" in names[0] and not is_perovskite(best["structure"]):
            # Perovskite symmetry but no octahedra: not a perovskite, so the name-based literature match is void.
            names, lit_row = [sg], None
        phases.append({
            "space_group": sg,
            "name": names[0] if names[0] != sg else sg,
            "members": [m["id"] for m in members],
            "labels": sorted({m["label"] for m in members}),
            "ml_dH": min(m["ml_dH"] for m in members),
            "dft_dH": best["dft_dH"],
            "literature": lit_row["status"] if lit_row else "not checked",
            "n_papers": int(lit_row["n_papers"]) if lit_row else 0,
            "structure": sga.get_conventional_standard_structure(),
        })
    return sorted(phases, key=lambda p: p["dft_dH"])


def scorecard(rows):
    """How well did the trust check do? An ML error > ERROR_LIMIT_MEV means the ML ranking was wrong."""
    err = lambda r: abs(r["dft_dH"] - r["ml_dH"])  # noqa: E731
    trusted = [r for r in rows if r["label"] == "Trusted"]
    flagged = [r for r in rows if r["label"] == "Needs DFT"]
    return {"n": len(rows), "n_trusted": len(trusted), "n_flagged": len(flagged),
            "trusted_ok": sum(err(r) <= ERROR_LIMIT_MEV for r in trusted),
            "flagged_wrong": sum(err(r) > ERROR_LIMIT_MEV for r in flagged),
            "median_error": float(np.median([err(r) for r in rows])),
            "max_error": float(max(err(r) for r in rows))}


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=8)


def plot_overview(materials, path):
    """One column per material: (a) ML vs DFT for each phase, (b) the DFT winner, (c) its simulated XRD."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ase.visualize.plot import plot_atoms
    from pymatgen.analysis.diffraction.xrd import XRDCalculator
    from pymatgen.io.ase import AseAtomsAdaptor

    n = len(materials)
    fig = plt.figure(figsize=(5.2 * n, 13), facecolor=SURFACE)
    grid = fig.add_gridspec(3, n, height_ratios=[1.35, 1.0, 0.75], hspace=0.42, wspace=0.95)
    xrd = XRDCalculator(wavelength="CuKa")

    for col, m in enumerate(materials):
        phases = m["phases"][:8]  # the 8 most stable phases in DFT

        # (a) dumbbell: hollow = ML, filled = DFT, joined by a line; colour = trust label
        ax = fig.add_subplot(grid[0, col])
        style(ax)
        y = np.arange(len(phases))[::-1]
        for yi, p in zip(y, phases):
            color = STATUS["Needs DFT"] if "Needs DFT" in p["labels"] else STATUS["Trusted"]
            ax.plot([p["ml_dH"], p["dft_dH"]], [yi, yi], color=GRID, lw=2.5, zorder=1, solid_capstyle="round")
            ax.scatter(p["ml_dH"], yi, s=55, facecolors=SURFACE, edgecolors=color, linewidths=1.8, zorder=3,
                       clip_on=False)
            ax.scatter(p["dft_dH"], yi, s=55, color=color, edgecolors=SURFACE, linewidths=1, zorder=4,
                       clip_on=False)
        labels = [f"{p['name']} ({p['space_group']})" + ("  ✓ lit." if p["literature"] == "Known" else "")
                  for p in phases]
        ax.set_yticks(y, labels, fontsize=8, color=INK)
        ax.set_xscale("symlog", linthresh=10)
        top = max(max(p["ml_dH"], p["dft_dH"]) for p in phases)
        ax.set_xlim(0, top * 2)
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("Enthalpy above best (meV/atom)", fontsize=9, color=INK)
        ax.set_title(f"{m['title']}\n(a) phases: ML ○ vs DFT ●", loc="left", fontsize=11, color=INK)

        # (b) the DFT winner, drawn from its standard cell (repeated if tiny)
        win = m["phases"][0]
        ax = fig.add_subplot(grid[1, col])
        ax.set_facecolor(SURFACE)
        atoms = AseAtomsAdaptor.get_atoms(win["structure"])
        if len(atoms) < 6:
            atoms = atoms.repeat((2, 2, 2))
        plot_atoms(atoms, ax, radii=0.38, rotation="15x,25y,0z", show_unit_cell=2)
        ax.set_axis_off()
        from ase.data import atomic_numbers
        from ase.data.colors import jmol_colors
        for k, el in enumerate(sorted(set(atoms.get_chemical_symbols()), key=lambda e: atomic_numbers[e])):
            ax.scatter([], [], s=60, color=jmol_colors[atomic_numbers[el]], edgecolors=INK, linewidths=0.5, label=el)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right", handletextpad=0.2)
        ax.set_title(f"(b) DFT winner: {win['name']} ({win['space_group']})\n"
                     f"ML ranked it +{win['ml_dH']:.0f} meV/atom · literature: {win['literature']}"
                     f" ({win['n_papers']} papers)", loc="left", fontsize=9, color=INK)

        # (c) simulated powder XRD of the winner, strongest peaks labelled with hkl
        ax = fig.add_subplot(grid[2, col])
        style(ax)
        pattern = xrd.get_pattern(win["structure"], two_theta_range=(10, 90))
        ax.vlines(pattern.x, 0, pattern.y, color=STATUS["Needs DFT"] if "Needs DFT" in win["labels"]
                  else STATUS["Trusted"], lw=1.8)
        for i in np.argsort(pattern.y)[::-1][:4]:
            hkl = "".join(str(v) for v in pattern.hkls[i][0]["hkl"])
            ax.text(pattern.x[i], pattern.y[i] + 3, hkl, ha="center", fontsize=7, color=INK2)
        ax.set_xlim(10, 90)
        ax.set_ylim(0, 118)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_xlabel("2θ (degrees, Cu Kα)", fontsize=9, color=INK)
        ax.set_title("(c) simulated XRD of the winner", loc="left", fontsize=9, color=INK)

    handles = [plt.Line2D([], [], marker="o", ls="", markersize=7, markerfacecolor=SURFACE,
                          markeredgecolor=INK2, label="ML (machine-learning model)"),
               plt.Line2D([], [], marker="o", ls="", markersize=7, color=INK2, label="DFT"),
               plt.Line2D([], [], marker="o", ls="", markersize=7, color=STATUS["Trusted"], label="Trusted"),
               plt.Line2D([], [], marker="o", ls="", markersize=7, color=STATUS["Needs DFT"], label="Needs DFT"),
               plt.Line2D([], [], ls="", label="✓ lit. = phase found in the literature (Valency)")]
    fig.legend(handles=handles, loc="upper center", ncol=5, frameon=False, fontsize=9, labelcolor=INK,
               bbox_to_anchor=(0.5, 0.955))
    fig.suptitle("HP-Pilot results: which phase wins under pressure, and could the ML model be trusted?",
                 x=0.01, y=0.975, ha="left", fontsize=14, color=INK)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def plot_all(materials, path):
    """Every structure of every material: ML vs DFT enthalpy above the best. Shape = material, colour = label."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 6), facecolor=SURFACE)
    style(ax)
    top = max(max(r["ml_dH"], r["dft_dH"]) for m in materials for r in m["rows"]) * 1.6
    ax.plot([0, top], [0, top], ls="--", lw=1, color=MUTED, zorder=1)
    for i, m in enumerate(materials):
        for label, color in STATUS.items():
            pts = [r for r in m["rows"] if r["label"] == label]
            if pts:
                ax.scatter([r["ml_dH"] for r in pts], [r["dft_dH"] for r in pts], s=45, color=color,
                           marker=MATERIAL_MARKERS[i], edgecolors=SURFACE, linewidths=1, alpha=0.9, zorder=3,
                           clip_on=False)
    ax.set_xscale("symlog", linthresh=10)
    ax.set_yscale("symlog", linthresh=10)
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("ML enthalpy above best (meV/atom)", color=INK)
    ax.set_ylabel("DFT enthalpy above best (meV/atom)", color=INK)
    ax.set_title(f"ML vs DFT for all {sum(len(m['rows']) for m in materials)} structures", loc="left",
                 fontsize=11, color=INK)
    ax.text(top * 0.6, top * 0.75, "ML = DFT", color=MUTED, fontsize=8, rotation=45, ha="center")
    handles = [plt.Line2D([], [], marker=MATERIAL_MARKERS[i], ls="", color=INK2, label=m["title"])
               for i, m in enumerate(materials)]
    handles += [plt.Line2D([], [], marker="o", ls="", color=c, label=l) for l, c in STATUS.items()]
    ax.legend(handles=handles, frameon=False, fontsize=8, labelcolor=INK, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Stage 7: compare materials.")
    parser.add_argument("--campaigns", nargs="+", help="campaign folder names (default: all with DFT results)")
    parser.add_argument("--dft-name", default="dft", help="which DFT results to use (dft = quick, dft_standard)")
    args = parser.parse_args()
    out = STAGE_DIR / "outputs"
    out.mkdir(exist_ok=True)

    folders = [STAGE_DIR / "campaigns" / c for c in args.campaigns] if args.campaigns else \
        sorted(f for f in (STAGE_DIR / "campaigns").iterdir() if (f / args.dft_name / "dft_results.csv").exists())
    materials = []
    for folder in folders:
        cfg, rows, skipped, lit = load_campaign(folder, args.dft_name)
        comp = cfg["project"]["composition"]
        from pymatgen.core import Composition
        n_el = len(Composition(comp).elements)
        phases = group_phases(rows, n_el, lit)
        ml_best = min(phases, key=lambda p: p["ml_dH"])
        m = {"label": folder.name, "title": f"{comp} at {cfg['project']['pressure_gpa']:g} GPa",
             "rows": rows, "phases": phases, "skipped": skipped, "score": scorecard(rows), "ml_best": ml_best}
        materials.append(m)
        with open(out / f"phases_{folder.name}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["name", "space_group", "structures", "trust_labels", "ml_dH_meV", "dft_dH_meV",
                        "literature", "n_papers"])
            for p in phases:
                w.writerow([p["name"], p["space_group"], " ".join(p["members"]), "/".join(p["labels"]),
                            round(p["ml_dH"], 1), round(p["dft_dH"], 1), p["literature"], p["n_papers"]])
        s = m["score"]
        print(f"== {m['title']}: {len(rows)} converged ({skipped} skipped), {len(phases)} distinct phases")
        print(f"   DFT winner: {phases[0]['name']} ({phases[0]['space_group']}), literature {phases[0]['literature']}"
              f" | ML winner: {ml_best['name']} ({ml_best['space_group']}), DFT +{ml_best['dft_dH']:.0f} meV/atom")
        print(f"   trust check: {s['n_trusted']} Trusted ({s['trusted_ok']} truly OK), {s['n_flagged']} Needs DFT "
              f"({s['flagged_wrong']} where ML was off by > {ERROR_LIMIT_MEV} meV/atom); "
              f"median ML error {s['median_error']:.0f}, max {s['max_error']:.0f} meV/atom")

    # Order by complexity: element, binary, ternary, ...
    materials.sort(key=lambda m: (len(m["rows"][0]["structure"].composition.elements), m["title"]))
    lines = ["# HP-Pilot: results across materials", "",
             f"DFT settings: `{args.dft_name}`. An ML error above {ERROR_LIMIT_MEV} meV/atom counts as wrong.", "",
             "| Material | Structures (DFT) | Distinct phases | DFT winner | In literature? | ML winner | ML winner in DFT | "
             "Trusted: truly OK | Needs DFT: ML really wrong | Median / max ML error (meV/atom) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for m in materials:
        s, w, mb = m["score"], m["phases"][0], m["ml_best"]
        lines.append(f"| {m['title']} | {s['n']} | {len(m['phases'])} | {w['name']} ({w['space_group']}) | "
                     f"{w['literature']} ({w['n_papers']} papers) | {mb['name']} ({mb['space_group']}) | "
                     f"+{mb['dft_dH']:.0f} meV/atom | {s['trusted_ok']} of {s['n_trusted']} | "
                     f"{s['flagged_wrong']} of {s['n_flagged']} | {s['median_error']:.0f} / {s['max_error']:.0f} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    with open(out / "summary.json", "w") as f:
        json.dump([{"material": m["title"], "score": m["score"], "dft_winner": m["phases"][0]["name"],
                    "dft_winner_sg": m["phases"][0]["space_group"], "ml_winner": m["ml_best"]["name"],
                    "literature": m["phases"][0]["literature"]} for m in materials], f, indent=2)

    plot_overview(materials, out / "overview.png")
    plot_all(materials, out / "ml_vs_dft_all.png")
    print(f"wrote {out}/overview.png, ml_vs_dft_all.png, summary.md")


if __name__ == "__main__":
    main()
