"""Save one material's results from stages 1-6 into campaigns/<label>/, so the next material can't overwrite them.

    # after ./hp-pilot run ... : save the ML stages (1-3), literature files (6) and settings
    ~/miniconda3/envs/osi/bin/python archive_campaign.py Si_15GPa
    # when the VASP jobs of that material are done: add the DFT results of a stage 5 run folder
    ~/miniconda3/envs/osi/bin/python archive_campaign.py Si_15GPa --dft-run ../5_stage_vasp_run/runs/run_X
    ~/miniconda3/envs/osi/bin/python archive_campaign.py Si_15GPa --dft-run ../5_stage_vasp_run/runs/run_Y --dft-name dft_standard
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

STAGE_DIR = Path(__file__).resolve().parent
ROOT = STAGE_DIR.parent
sys.path.insert(0, str(ROOT / "5_stage_vasp_run"))

ML_FILES = [
    "1_stage_create_structure/outputs/summary.csv",
    "2_stage_relax/outputs/results.csv",
    "2_stage_relax/outputs/relaxed.extxyz",
    "3_stage_trust_check/outputs/trust_report.csv",
    "3_stage_trust_check/outputs/trust_plot.png",
    "last_run_config.toml",
]
LITERATURE_FILES = ["queries.json", "valency_results.json", "review.json", "literature_report.md",
                    "literature_report.csv", "literature_check.png"]


def archive_dft(run_dir, dest):
    """DFT summary of every calculation in a stage 5 run folder, plus each final structure (CONTCAR)."""
    from run_stage5 import read_calc
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    for calc in sorted((run_dir / "calcs").iterdir()):
        if not calc.is_dir():
            continue
        row = read_calc(calc)
        rows.append(row)
        if (calc / "CONTCAR").exists():
            shutil.copy(calc / "CONTCAR", dest / f"CONTCAR_{calc.name}")
    fields = sorted({k for r in rows for k in r})
    with open(dest / "dft_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (dest / "source_run.txt").write_text(str(run_dir.resolve()) + "\n")
    print(f"DFT: {len(rows)} calculations from {run_dir.name} -> {dest}")


def main():
    parser = argparse.ArgumentParser(description="Archive one material's pipeline results.")
    parser.add_argument("label", help="e.g. Si_15GPa")
    parser.add_argument("--dft-run", help="stage 5 run folder whose DFT results to add")
    parser.add_argument("--dft-name", default="dft", help="sub-folder name for the DFT results (default dft)")
    args = parser.parse_args()
    dest = STAGE_DIR / "campaigns" / args.label

    if args.dft_run:
        archive_dft(Path(args.dft_run), dest / args.dft_name)
        return
    dest.mkdir(parents=True, exist_ok=True)
    for rel in ML_FILES:
        src = ROOT / rel
        if src.exists():
            shutil.copy(src, dest / Path(rel).name)
    lit = ROOT / "6_stage_literature_check" / "outputs"
    (dest / "literature").mkdir(exist_ok=True)
    for name in LITERATURE_FILES:
        if (lit / name).exists():
            shutil.copy(lit / name, dest / "literature" / name)
    print(f"ML stages and literature files -> {dest}")


if __name__ == "__main__":
    main()
