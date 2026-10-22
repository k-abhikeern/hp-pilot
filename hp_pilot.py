"""HP-Pilot: run the whole pipeline with one command.

    ./hp-pilot run --composition Si --pressure 15                 # stages 1-4 (+ stage 6 prepare)
    ./hp-pilot run --composition NaCl --pressure 30 --n-structures 40
    ./hp-pilot run --composition Si --pressure 15 --submit        # also send the VASP jobs (stage 5)
    ./hp-pilot status                                             # are the VASP jobs done?
    ./hp-pilot collect                                            # compare DFT with ML
    ./hp-pilot literature                                         # literature report (after the agent's Valency search)

Settings not given on the command line come from config.toml. The settings actually used are saved in
last_run_config.toml, so every run can be repeated. Each stage still writes its own logs and outputs.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

STAGES = [
    ("1 create structures", ["1_stage_create_structure/run_stage1.py", "{config}"]),
    ("2 relax at pressure", ["2_stage_relax/run_stage2.py", "--config", "{config}"]),
    ("3 trust check", ["3_stage_trust_check/run_stage3.py", "--config", "{config}"]),
    ("4 build VASP inputs + job plan", ["4_stage_incar_build/run_stage4.py", "--config", "{config}"]),
    ("6 prepare literature queries", ["6_stage_literature_check/run_stage6.py", "prepare", "--config", "{config}"]),
]


def write_run_config(args):
    """Copy config.toml, replacing only the values given on the command line."""
    text = (ROOT / "config.toml").read_text()
    changes = {"composition": f'"{args.composition}"' if args.composition else None,
               "pressure_gpa": args.pressure, "n_structures": args.n_structures, "seed": args.seed,
               "formula_units": f"[{', '.join(map(str, args.formula_units))}]" if args.formula_units else None}
    for key, value in changes.items():
        if value is not None:
            text, n = re.subn(rf"(?m)^({key}\s*=\s*)[^#\n]*?(\s*(#.*)?)$", rf"\g<1>{value}\g<2>", text, count=1)
            if n != 1:
                sys.exit(f"Could not set {key} in config.toml")
    path = ROOT / "last_run_config.toml"
    path.write_text(f"# Written by hp_pilot.py on {time.strftime('%Y-%m-%d %H:%M:%S')}\n" + text)
    return path


def run_step(name, cmd):
    print(f"\n=== Stage {name} ===", flush=True)
    start = time.time()
    result = subprocess.run([PY] + cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"Stage {name} failed (exit code {result.returncode}). See that stage's logs/ folder.")
    print(f"--- stage {name} finished in {time.time() - start:.0f} s", flush=True)


def main():
    parser = argparse.ArgumentParser(description="HP-Pilot: high-pressure structure search with a trust check.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run stages 1-4 (and optionally submit stage 5)")
    run.add_argument("--composition", help='e.g. "Si", "NaCl"')
    run.add_argument("--pressure", type=float, help="target pressure in GPa")
    run.add_argument("--n-structures", type=int, help="number of random candidates")
    run.add_argument("--seed", type=int, help="random seed")
    run.add_argument("--formula-units", type=int, nargs="+", help="cell sizes to try, e.g. 1 2 4")
    run.add_argument("--submit", action="store_true", help="also submit the VASP jobs (stage 5)")
    run.add_argument("--dry-run", action="store_true", help="with --submit: show jobs without sending them")
    sub.add_parser("status", help="state of the newest VASP run")
    sub.add_parser("collect", help="read finished VASP results and compare with ML")
    sub.add_parser("literature", help="build the literature report from the agent's Valency results")
    args = parser.parse_args()

    if args.command == "run":
        config = write_run_config(args)
        print(f"Settings for this run: {config}")
        for name, cmd in STAGES:
            run_step(name, [c.replace("{config}", str(config)) for c in cmd])
        if args.submit:
            run_step("5 submit VASP jobs", ["5_stage_vasp_run/run_stage5.py", "submit"]
                     + (["--dry-run"] if args.dry_run else []))
        print("\nDone. Next: ./hp-pilot status, then ./hp-pilot collect when jobs finish."
              if args.submit else "\nDone. To run DFT: ./hp-pilot run ... --submit, or run stage 5 yourself.")
    elif args.command in ("status", "collect"):
        run_step(f"5 {args.command}", ["5_stage_vasp_run/run_stage5.py", args.command])
    else:
        run_step("6 literature report", ["6_stage_literature_check/run_stage6.py", "report"])


if __name__ == "__main__":
    main()
